#    Copyright (C) 2015 Yahoo! Inc. All Rights Reserved.
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

import datetime
import itertools
import sys
import uuid

import netaddr
from oslotest import base as test_base
from pytz import timezone
import six
import six.moves.xmlrpc_client as xmlrpclib
import testtools

from oslo_serialization import msgpackutils

# NOTE(harlowja): itertools.count only started to take a step value
# in python 2.7+ so we can't use it in 2.6...
if sys.version_info[0:2] == (2, 6):
    _PY26 = True
else:
    _PY26 = False


_TZ_FMT = '%Y-%m-%d %H:%M:%S %Z%z'


def _dumps_loads(obj):
    obj = msgpackutils.dumps(obj)
    return msgpackutils.loads(obj)


class MsgPackUtilsTestMixin(test_base.BaseTestCase):
    def test_list(self):
        self.assertEqual(_dumps_loads([1, 2, 3]), [1, 2, 3])

    def test_empty_list(self):
        self.assertEqual(_dumps_loads([]), [])

    def test_tuple(self):
        # Seems like we do lose whether it was a tuple or not...
        #
        # Maybe fixed someday:
        #
        # https://github.com/msgpack/msgpack-python/issues/98
        self.assertEqual(_dumps_loads((1, 2, 3)), [1, 2, 3])

    def test_dict(self):
        self.assertEqual(_dumps_loads(dict(a=1, b=2, c=3)),
                         dict(a=1, b=2, c=3))

    def test_empty_dict(self):
        self.assertEqual(_dumps_loads({}), {})

    def test_complex_dict(self):
        src = {
            'now': datetime.datetime(1920, 2, 3, 4, 5, 6, 7),
            'later': datetime.datetime(1921, 2, 3, 4, 5, 6, 9),
            'a': 1,
            'b': 2.0,
            'c': [],
            'd': set([1, 2, 3]),
            'zzz': uuid.uuid4(),
            'yyy': 'yyy',
            'ddd': b'bbb',
            'today': datetime.date.today(),
        }
        self.assertEqual(_dumps_loads(src), src)

    def test_itercount(self):
        it = itertools.count(1)
        six.next(it)
        six.next(it)
        it2 = _dumps_loads(it)
        self.assertEqual(six.next(it), six.next(it2))

        it = itertools.count(0)
        it2 = _dumps_loads(it)
        self.assertEqual(six.next(it), six.next(it2))

    @testtools.skipIf(_PY26, 'itertools.count step not supported')
    def test_itercount_step(self):
        it = itertools.count(1, 3)
        it2 = _dumps_loads(it)
        self.assertEqual(six.next(it), six.next(it2))

    def test_set(self):
        self.assertEqual(_dumps_loads(set([1, 2])), set([1, 2]))

    def test_empty_set(self):
        self.assertEqual(_dumps_loads(set([])), set([]))

    def test_frozenset(self):
        self.assertEqual(_dumps_loads(frozenset([1, 2])), frozenset([1, 2]))

    def test_empty_frozenset(self):
        self.assertEqual(_dumps_loads(frozenset([])), frozenset([]))

    def test_datetime_preserve(self):
        x = datetime.datetime(1920, 2, 3, 4, 5, 6, 7)
        self.assertEqual(_dumps_loads(x), x)

    def test_datetime(self):
        x = xmlrpclib.DateTime()
        x.decode("19710203T04:05:06")
        self.assertEqual(_dumps_loads(x), x)

    def test_ipaddr(self):
        thing = {'ip_addr': netaddr.IPAddress('1.2.3.4')}
        self.assertEqual(_dumps_loads(thing), thing)

    def test_today(self):
        today = datetime.date.today()
        self.assertEqual(today, _dumps_loads(today))

    def test_datetime_tz_clone(self):
        eastern = timezone('US/Eastern')
        now = datetime.datetime.now()
        e_dt = eastern.localize(now)
        e_dt2 = _dumps_loads(e_dt)
        self.assertEqual(e_dt, e_dt2)
        self.assertEqual(e_dt.strftime(_TZ_FMT), e_dt2.strftime(_TZ_FMT))

    def test_datetime_tz_different(self):
        eastern = timezone('US/Eastern')
        pacific = timezone('US/Pacific')
        now = datetime.datetime.now()

        e_dt = eastern.localize(now)
        p_dt = pacific.localize(now)

        self.assertNotEqual(e_dt, p_dt)
        self.assertNotEqual(e_dt.strftime(_TZ_FMT), p_dt.strftime(_TZ_FMT))

        e_dt2 = _dumps_loads(e_dt)
        p_dt2 = _dumps_loads(p_dt)

        self.assertNotEqual(e_dt2, p_dt2)
        self.assertNotEqual(e_dt2.strftime(_TZ_FMT), p_dt2.strftime(_TZ_FMT))

        self.assertEqual(e_dt, e_dt2)
        self.assertEqual(p_dt, p_dt2)
