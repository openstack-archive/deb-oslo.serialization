# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# Copyright 2011 Justin Santa Barbara
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

'''
JSON related utilities.

This module provides a few things:

#. A handy function for getting an object down to something that can be
   JSON serialized.  See :func:`.to_primitive`.
#. Wrappers around :func:`.loads` and :func:`.dumps`. The :func:`.dumps`
   wrapper will automatically use :func:`.to_primitive` for you if needed.
#. This sets up ``anyjson`` to use the :func:`.loads` and :func:`.dumps`
   wrappers if ``anyjson`` is available.
'''


import codecs
import datetime
import functools
import inspect
import itertools
import sys
import uuid

is_simplejson = False
if sys.version_info < (2, 7):
    # On Python <= 2.6, json module is not C boosted, so try to use
    # simplejson module if available
    try:
        import simplejson as json
        # NOTE(mriedem): Make sure we have a new enough version of simplejson
        # to support the namedobject_as_tuple argument. This can be removed
        # in the Kilo release when python 2.6 support is dropped.
        if 'namedtuple_as_object' in inspect.getargspec(json.dumps).args:
            is_simplejson = True
        else:
            import json
    except ImportError:
        import json
else:
    import json

from oslo_utils import encodeutils
from oslo_utils import importutils
from oslo_utils import timeutils
import six
import six.moves.xmlrpc_client as xmlrpclib

netaddr = importutils.try_import("netaddr")

_nasty_type_tests = [inspect.ismodule, inspect.isclass, inspect.ismethod,
                     inspect.isfunction, inspect.isgeneratorfunction,
                     inspect.isgenerator, inspect.istraceback, inspect.isframe,
                     inspect.iscode, inspect.isbuiltin, inspect.isroutine,
                     inspect.isabstract]

_simple_types = (six.string_types + six.integer_types
                 + (type(None), bool, float))


def to_primitive(value, convert_instances=False, convert_datetime=True,
                 level=0, max_depth=3):
    """Convert a complex object into primitives.

    Handy for JSON serialization. We can optionally handle instances,
    but since this is a recursive function, we could have cyclical
    data structures.

    To handle cyclical data structures we could track the actual objects
    visited in a set, but not all objects are hashable. Instead we just
    track the depth of the object inspections and don't go too deep.

    Therefore, ``convert_instances=True`` is lossy ... be aware.
    """
    # handle obvious types first - order of basic types determined by running
    # full tests on nova project, resulting in the following counts:
    # 572754 <type 'NoneType'>
    # 460353 <type 'int'>
    # 379632 <type 'unicode'>
    # 274610 <type 'str'>
    # 199918 <type 'dict'>
    # 114200 <type 'datetime.datetime'>
    #  51817 <type 'bool'>
    #  26164 <type 'list'>
    #   6491 <type 'float'>
    #    283 <type 'tuple'>
    #     19 <type 'long'>
    if isinstance(value, _simple_types):
        return value

    # It's not clear why xmlrpclib created their own DateTime type, but
    # for our purposes, make it a datetime type which is explicitly
    # handled
    if isinstance(value, xmlrpclib.DateTime):
        value = datetime.datetime(*tuple(value.timetuple())[:6])

    if isinstance(value, datetime.datetime):
        if convert_datetime:
            return value.strftime(timeutils.PERFECT_TIME_FORMAT)
        else:
            return value

    if isinstance(value, uuid.UUID):
        return six.text_type(value)

    if netaddr and isinstance(value, netaddr.IPAddress):
        return six.text_type(value)

    # value of itertools.count doesn't get caught by nasty_type_tests
    # and results in infinite loop when list(value) is called.
    if type(value) == itertools.count:
        return six.text_type(value)

    if any(test(value) for test in _nasty_type_tests):
        return six.text_type(value)

    # FIXME(vish): Workaround for LP bug 852095. Without this workaround,
    #              tests that raise an exception in a mocked method that
    #              has a @wrap_exception with a notifier will fail. If
    #              we up the dependency to 0.5.4 (when it is released) we
    #              can remove this workaround.
    if getattr(value, '__module__', None) == 'mox':
        return 'mock'

    if level > max_depth:
        return '?'

    # The try block may not be necessary after the class check above,
    # but just in case ...
    try:
        recursive = functools.partial(to_primitive,
                                      convert_instances=convert_instances,
                                      convert_datetime=convert_datetime,
                                      level=level,
                                      max_depth=max_depth)
        if isinstance(value, dict):
            return dict((recursive(k), recursive(v))
                        for k, v in six.iteritems(value))
        elif hasattr(value, 'iteritems'):
            return recursive(dict(value.iteritems()), level=level + 1)
        elif hasattr(value, '__iter__'):
            return list(map(recursive, value))
        elif convert_instances and hasattr(value, '__dict__'):
            # Likely an instance of something. Watch for cycles.
            # Ignore class member vars.
            return recursive(value.__dict__, level=level + 1)
    except TypeError:
        # Class objects are tricky since they may define something like
        # __iter__ defined but it isn't callable as list().
        return six.text_type(value)

    return value


JSONEncoder = json.JSONEncoder
JSONDecoder = json.JSONDecoder


def dumps(obj, default=to_primitive, **kwargs):
    """Serialize ``obj`` to a JSON formatted ``str``.

    :param obj: object to be serialized
    :param default: function that returns a serializable version of an object
    :param kwargs: extra named parameters, please see documentation \
    of `json.dumps <https://docs.python.org/2/library/json.html#basic-usage>`_
    :returns: json formatted string
    """
    if is_simplejson:
        kwargs['namedtuple_as_object'] = False
    return json.dumps(obj, default=default, **kwargs)


def dump(obj, fp, *args, **kwargs):
    """Serialize ``obj`` as a JSON formatted stream to ``fp``

    :param obj: object to be serialized
    :param fp: a ``.write()``-supporting file-like object
    :param default: function that returns a serializable version of an object
    :param args: extra arguments, please see documentation \
    of `json.dump <https://docs.python.org/2/library/json.html#basic-usage>`_
    :param kwargs: extra named parameters, please see documentation \
    of `json.dump <https://docs.python.org/2/library/json.html#basic-usage>`_
    """
    default = kwargs.get('default', to_primitive)
    if is_simplejson:
        kwargs['namedtuple_as_object'] = False
    return json.dump(obj, fp, default=default, *args, **kwargs)


def loads(s, encoding='utf-8', **kwargs):
    """Deserialize ``s`` (a ``str`` or ``unicode`` instance containing a JSON

    :param s: string to deserialize
    :param encoding: encoding used to interpret the string
    :param kwargs: extra named parameters, please see documentation \
    of `json.loads <https://docs.python.org/2/library/json.html#basic-usage>`_
    :returns: python object
    """
    return json.loads(encodeutils.safe_decode(s, encoding), **kwargs)


def load(fp, encoding='utf-8', **kwargs):
    """Deserialize ``fp`` to a Python object.

    :param fp: a ``.read()`` -supporting file-like object
    :param encoding: encoding used to interpret the string
    :param kwargs: extra named parameters, please see documentation \
    of `json.loads <https://docs.python.org/2/library/json.html#basic-usage>`_
    :returns: python object
    """
    return json.load(codecs.getreader(encoding)(fp), **kwargs)


try:
    import anyjson
except ImportError:
    pass
else:
    anyjson._modules.append((__name__, 'dumps', TypeError,
                                       'loads', ValueError, 'load'))
    anyjson.force_implementation(__name__)
