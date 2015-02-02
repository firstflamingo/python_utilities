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
#  ffe_utils.py
#  firstflamingo/python_utilities
#
#  Created by Berend Schotanus on 06-May-2014.
#

import re
import hashlib


# ====== Utilities for http authentication =============================================================================


def md5_hash(components):
    m = hashlib.md5()
    hashable = ':'.join(components)
    m.update(hashable)
    return m.hexdigest()


def dict_from_paramslist(paramslist):
    reg = re.compile('(\w+)= ?"?([\w.@/]+)"?')
    return dict(reg.findall(paramslist))


def paramslist_from_dict(dictionary):
    components = []
    for key, value in dictionary.iteritems():
        components.append('%s=\"%s\"' % (key, value))
    return ', '.join(components)


def auth_header(method, uri, http_response, user):
    """
    Builds a Digest Authentication header based upon a 401 response and a user
    :param method: the http method
    :param uri: the http uri
    :param http_response: the response object
    :param user: the user (TSUser subclass)
    :return: string that can be used as value for the Authentication header
    """
    auth_params = dict_from_paramslist(http_response.headers.get('WWW-Authenticate'))
    ha2 = md5_hash([method, uri])
    nonce = auth_params['nonce']
    nc = '00000001'
    cnonce = '0a4f113b'
    qop = auth_params['qop']
    response_hash = md5_hash([user.ha1, nonce, nc, cnonce, qop, ha2])
    auth_params['username'] = user.username
    auth_params['uri'] = uri
    auth_params['nc'] = nc
    auth_params['cnonce'] = cnonce
    auth_params['response'] = response_hash
    return 'Digest %s' % paramslist_from_dict(auth_params)
