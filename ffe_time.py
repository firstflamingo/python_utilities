# coding=utf-8
#
#  Copyright (c) 2014-2015 First Flamingo Enterprise B.V.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
#  ffe_time.py
#  firstflamingo/python_utilities
#
#  Created by Berend Schotanus on 18-Mar-2014.
#

from datetime import time, timedelta, datetime, tzinfo

# ====== String conversion ==========================================================================

DAYS_NL     = ['maandag', 'dinsdag', 'woensdag', 'donderdag', 'vrijdag', 'zaterdag', 'zondag']
MONTHS_NL   = ['januari', 'februari', 'maart', 'april', 'mei', 'juni', 'juli', 'augustus', 'september', 'oktober', 'november', 'december']

def is_nl_day(day):
    if day in DAYS_NL:
        return True
    else:
        return False

def index_for_nl_day(day):
    return index_for_string(day, DAYS_NL)

def nl_day_for_index(index):
    assert index >=0 and index <= 6
    return DAYS_NL[index]

def is_nl_month(month):
    if month in MONTHS_NL:
        return True
    else:
        return False

def number_for_nl_month(month):
    index = index_for_string(month, MONTHS_NL)
    if index is None:
        return None
    else:
        return index + 1

def nl_month_for_number(number):
    assert number > 0 and number <= 12
    return MONTHS_NL[number - 1]

def index_for_string(string, array):
    for index in range(len(array)):
        if string == array[index]:
            return index
    return None

# ====== Time Functions ==========================================================================

def mark_utc(a_time):
    if a_time:
        return a_time.replace(tzinfo=UTC())

def mark_cet(a_time):
    if a_time:
        return a_time.replace(tzinfo=CET())

def cet_from_utc(a_time):
    if a_time:
        labeled_time = a_time.replace(tzinfo=UTC())
        return labeled_time.astimezone(CET())

def utc_from_cet(a_time):
    if a_time:
        labeled_time = a_time.replace(tzinfo=CET())
        return labeled_time.astimezone(UTC())

def cet_from_string(string):
    return mark_cet(datetime.strptime(string[0:19], '%Y-%m-%dT%H:%M:%S'))

def string_from_cet(a_time):
    return a_time.strftime('%Y-%m-%dT%H:%M:%S')

def now_utc():
    return datetime.utcnow().replace(tzinfo=UTC())

def now_cet():
    return cet_from_utc(now_utc())

def minutes_from_string(string):
    components = string.split(':')
    return 60 * int(components[0]) + int(components[1])

def string_from_minutes(minutes):
    return '%d:%02d' % (minutes // 60, minutes % 60)

def minutes_from_time(theTime):
    return 60 * theTime.hour + theTime.minute

def time_from_minutes(minutes):
    return time(minutes // 60, minutes % 60)

def time_from_string(string):
    comps = string.split(':')
    return time(int(comps[0]), int(comps[1]))

def rfc1123_from_utc(dt):
    """
    Return a string representation of a date according to RFC 1123 (HTTP/1.1).
    The supplied date must be in UTC.

    """
    weekday = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][dt.weekday()]
    month = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep",
             "Oct", "Nov", "Dec"][dt.month - 1]
    return "%s, %02d %s %04d %02d:%02d:%02d GMT" % (weekday, dt.day, month,
                                                    dt.year, dt.hour, dt.minute, dt.second)

def utc_from_rfc1123(string):
    dt = datetime.strptime(string, '%a, %d %b %Y %H:%M:%S GMT')
    return mark_utc(dt)

# ====== Timezone Classes ==========================================================================


class UTC(tzinfo):
    
    def tzname(self, dt):
        return "UTC"
    
    def utcoffset(self, dt):
        return timedelta(0)
    
    def dst(self, dt):
        return timedelta(0)


class CET(tzinfo):
    
    def tzname(self,dt):
        return "CET"
    
    def utcoffset(self, dt):
        return timedelta(hours=1) + self.dst(dt)
    
    def dst(self, dt):
        d = datetime(dt.year, 4, 1)    # DST starts last Sunday in March
        self.dston = d - timedelta(days=d.weekday() + 1)
        d = datetime(dt.year, 11, 1)   # ends last Sunday in October
        self.dstoff = d - timedelta(days=d.weekday() + 1)
        if self.dston <=  dt.replace(tzinfo=None) < self.dstoff:
            return timedelta(hours=1)
        else:
            return timedelta(0)


