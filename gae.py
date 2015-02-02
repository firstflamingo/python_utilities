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
#  gae.py
#  firstflamingo/python_utilities
#
#  Created by Berend Schotanus on 22-Mar-2014.
#

import logging

from google.appengine.api import memcache, taskqueue, urlfetch


# ====== Counters ===========================================================================

def read_counter(identifier):
    value = memcache.get(identifier)
    if value is None:
        value = 0
    return value

def increase_counter(identifier):
    logging.info('increase %s' % identifier)
    memcache.incr(identifier, initial_value=0)

def counter_dict():
    dictionary = {}
    identifiers = ['req_trajectory', 'req_mission', 'req_departures',
                   'req_api_total', 'req_api_success',
                   'req_avt_answered', 'req_avt_denied',
                   'req_prio_answered', 'req_prio_denied',
                   'req_check_confirmed', 'req_check_denied', 'req_check_refetched', 'req_check_revoked',
                   'mission_changes', 'mission_small_changes', 'mission_no_changes']
    for identifier in identifiers:
        dictionary[identifier] = read_counter(identifier)
    return dictionary


# ====== Managing Tasks ===========================================================================

def task_name(issueTime, label):
    return issueTime.strftime('%d_%H%M_%S_') + label

def issue_tasks(tasks):
    if not tasks: return
    batchlength = len(tasks)//100 + 1
    for batch in range(0, batchlength):
        start = batch * 100
        end = start + 100
        try:
            taskqueue.Queue().add(tasks[start:end])
        except taskqueue.TaskAlreadyExistsError:
            logging.warning('Issue tasks raised TaskAlreadyExistsError.')


# ====== Managing Remote Fetch ======================================================================

def remote_fetch(url, headers=None, deadline=5):
    if headers is None:
        headers = {}
    result = urlfetch.fetch(url, headers=headers, deadline=deadline)
    if result.status_code == 200:
        return result.content
    else:
        logging.warning('%s replied with error %d' % (url, result.status_code))
        logging.info(result.headers)

