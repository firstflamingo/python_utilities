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
#  rest_interface.py
#  firstflamingo/python_utilities
#
#  Created by Berend Schotanus on 06-May-2014.
#

import logging
import random
from datetime import timedelta

import webapp2
from ffe_time import now_utc, utc_from_rfc1123
from ffe_utils import md5_hash, paramslist_from_dict, dict_from_paramslist
from rest_resources import DataType, Catalog, NoValidIdentifierError, InvalidUpdateDataError


class ResourceHandler(webapp2.RequestHandler):
    """
    ResourceHandler handles http requests coupled to a resource class and (optionally) an instance of that class.
    It can find and validate the requested class and instance for further handling by subclasses.
    Class and instance are deduced from the url, following the pattern:
    http://host.com/api/class/identifier

    When implementing a ResourceHandler, a resource_class must be set.

    To be handled by ResourceHandler, a resource must implement:
       - get(identifier): class method, fetches instance with specified identifier
       - valid_identifier(identifier): class method, returning a validated identifier or raising NoValidIdentifierError
    """
    resource_class = None
    _valid_class_url = None
    _valid_resource_id = None
    _resource_id = None
    _resource = None

    # ------------ Translating URL-path into a resource ----------------------------------------------------------------

    @property
    def valid_class_url(self):
        if self._valid_class_url is None:
            self.parse_request_path()
        return self._valid_class_url

    @property
    def valid_resource_id(self):
        if self._valid_resource_id is None:
            self.parse_request_path()
        return self._valid_resource_id

    @property
    def resource_id(self):
        if self.valid_resource_id:
            return self._resource_id

    @property
    def resource(self):
        if self._resource is None and self.valid_resource_id:
            self._resource = self.resource_class.get(self.resource_id)
        return self._resource

    @resource.setter
    def resource(self, value):
        self._resource = value

    def parse_request_path(self):
        self._valid_class_url = False
        self._valid_resource_id = False
        comps = self.request.path.split('/')
        if len(comps) < 3:
            return
        if comps[2] != self.resource_class.url_name:
            return
        if len(comps) == 3:
            self._valid_class_url = True
            return
        if len(comps) == 4:
            identifier = comps[3]
            try:
                self._resource_id = self.resource_class.valid_identifier(identifier)
                self._valid_resource_id = True
            except NoValidIdentifierError:
                self._valid_resource_id = False

    # ------------ Debugging -------------------------------------------------------------------------------------------

    def log_request(self):
        logging.info('IP-address: %s' % self.request.remote_addr)
        logging.info('Resource ID = %s' % self.resource_id)
        for key, value in self.request.environ.iteritems():
            logging.info('environ %s = %s' % (key, value))
        for key, value in self.request.headers.iteritems():
            logging.info('header %s = %s' % (key, value))
        logging.info('Body:\n%s' % self.request.body)


class AgentHandler(ResourceHandler):
    """
    AgentHandler handles http requests addressed to 'agents', agents are resources designed to perform a specific task
    within the protected environment of a web app.
    """
    def post(self):
        if self.valid_resource_id:
            self.resource.execute_request(self.request)


class RestHandler(ResourceHandler):
    """
    RestHandler handles http requests to create, read, write or update resources.
    It handles two kinds of resources:
    1) public resources
       public resources have fixed indexes, can be read by everyone and modified by admins only
    2) user resources ("non-publications")
       these resources have server generated indexes, they can be read and modified by their specified owner only

    To be handled by RestHandler, a resource must implement:
    1) Configuration properties
       - is_publication: indicates whether the class is a publication or a user resource
    2) Object lifecycle
       - new(identifier): class method, creates a new instance
       - get(identifier): class method, fetches instance with specified identifier
       - put(): instance method, stores the instance
       - delete(): instance method, removes the instance
    3) Object metadata
       - valid_identifier(identifier): class method, returning a validated identifier or raising NoValidIdentifierError
       - url: property, the url through which the resource can be reached
       - last_modified_utc: property, a datetime object with UTC() as timezone with the last modification time
       - last_modified_http: property, a string conforming to http standards with the last modification time
    4) Access to the content
       - readable_data_types(): class method, returning a list of DataTypes the resource can read
       - update_with_string(string, data_type): updates the instance with a string following the indicated data type
       - writable_data_types(): class method, returning a list of DataTypes the resource can write
       - serialization_of_type(data_type): returns a string with the instances content in the requested data type
    """
    user_class = None
    user = None
    allows_anonymous_post = False

    # ------------ Handling http requests ------------------------------------------------------------------------------

    def post(self):
        """
        Handles http POST request
        """
        if not (self.allows_anonymous_post or self.authenticate()):
            self.require_authentication()
            return

        if not self.valid_class_url:
            self.error(405)  # Method Not Allowed
            return

        if self.resource_class.is_publication:
            self.error(405)  # Method Not Allowed
            return

        data_type = self.input_data_type
        if data_type is None:
            self.error(415)  # Unsupported Media Type
            return

        self.resource = self.resource_class.new()
        try:
            self.resource.update_with_string(self.request.body, data_type)
        except InvalidUpdateDataError:
            self.error(422)  # Unprocessable Entity
            return

        if self.user and hasattr(self.resource, 'owner_key'):
            self.resource.owner_key = self.user.key
        if hasattr(self.resource, 'creation_address'):
            self.resource.creation_address = self.request.remote_addr
        self.resource.put()
        self.response.headers.add('Location', self.resource.url)
        logging.info('Created: %s' % self.resource)
        self.write_output(self.resource, data_type)
        self.response.status_int = 201  # Created

    def get(self):
        """
        Handles http GET request
        """
        if not (self.resource_class.is_publication or self.authenticate()):
            self.require_authentication()
            return

        resource = None
        resource_class = None
        if self.valid_class_url:
            if not self.resource_class.is_publication:
                self.error(405)  # Method Not Allowed
                return
            resource_class = Catalog
            resource = resource_class.get(self.resource_class)

        if self.valid_resource_id:
            resource = self.resource
            resource_class = self.resource_class

        if not resource:
            self.error(404)  # Not Found
            return

        if not (self.resource_class.is_publication or self.resource_is_authorized):
            self.error(401)  # Unauthorized
            return

        modified_since = self.request.headers.get('If-Modified-Since')
        if modified_since and resource.last_modified_utc <= utc_from_rfc1123(modified_since):
            logging.info('Not Modified: %s' % resource)
            self.response.content_type = None
            self.response.status_int = 304  # Not Modified
            return

        data_type = self.output_data_type(resource_class)
        if data_type is None:
            self.error(406)  # Not Acceptable
            return

        self.write_output(resource, data_type)

    def put(self):
        """
        Handles http PUT request
        """
        if not self.authenticate():
            self.require_authentication()
            return

        data_type = self.input_data_type
        if data_type is None:
            self.error(415)  # Unsupported Media Type
            return

        if self.resource:
            if not self.resource_is_authorized:
                logging.info('Resource is not authorized')
                self.error(401)  # Unauthorized
                return

            unmodified_since = self.request.headers.get('If-Unmodified-Since')
            if not unmodified_since:
                self.error(409)  # Conflict
                return

            if self.resource.last_modified_utc <= utc_from_rfc1123(unmodified_since):
                self.resource.update_with_string(self.request.body, data_type)
                self.write_output(self.resource, data_type)
            else:
                self.error(412)  # Precondition Failed
        else:
            if self.resource_class.is_publication:
                if not self.user.has_admin_privileges:
                    logging.info('Admin privilege is required')
                    self.error(401)  # Unauthorized
                    return

                try:
                    self.resource = self.resource_class.new(self.resource_id)
                except NoValidIdentifierError:
                    self.error(400)  # Bad request
                    return

                self.resource.update_with_string(self.request.body, data_type)
                logging.info('Created: %s' % self.resource)
                self.write_output(self.resource, data_type)
                self.response.status_int = 201  # Created
            else:
                self.error(404)  # Not Found

    def delete(self):
        """
        Handles http DELETE request
        """
        if not self.authenticate():
            self.require_authentication()
            return

        if self.resource:
            if not self.resource_is_authorized:
                self.error(401)  # Unauthorized
                return

            self.resource.delete()
            self.response.content_type = None
            self.response.status_int = 204  # No Content
        else:
            self.error(404)  # Not Found

    # ------------ Handling authentication  ----------------------------------------------------------------------------

    @property
    def resource_is_authorized(self):
        if self.user is None:
            return False
        if self.user.has_admin_privileges:
            logging.info('user has admin privileges')
            return True
        if hasattr(self.resource, 'owner_key') and self.resource.owner_key == self.user.key:
            logging.info('user is owner')
            return True
        return False

    def authenticate(self):
        auth_header = self.request.headers.get('Authorization')
        if not auth_header:
            logging.info('No Authorization header')
            return False

        params = dict_from_paramslist(auth_header)
        try:
            username = params['username']
            nonce = params['nonce']
            cnonce = params['cnonce']
            nc = params['nc']
            realm = params['realm']
            qop = params['qop']
            uri = params['uri']
            opaque = params['opaque']
            response = params['response']
        except KeyError:
            logging.info('Missing keys in Authorization header: %s' % auth_header)
            return False

        if realm != self.user_class.realm:
            logging.info('Stated realm %s does not match %s' % (realm, self.user_class.realm))
            return False

        now = now_utc()
        ref_opaque = self.opaque_from_nonce(nonce, now)
        if opaque != ref_opaque:
            now -= timedelta(minutes=5)
            ref_opaque = self.opaque_from_nonce(nonce, now)
            if opaque != ref_opaque:
                logging.info('Nonce has expired')
                return False

        self.user = None
        try:
            self.user = self.user_class.get(username)
        except NoValidIdentifierError:
            logging.info('Not a valid username: %s' % username)
            return False
        if not self.user:
            logging.info('No user with username %s' % username)
            return False

        if uri != self.request.path:
            logging.info('URI \"%s\" does not match path \"%s\"' % (uri, self.request.path))
            return False
        ha2 = md5_hash([self.request.method, uri])

        ref_response = md5_hash([self.user.ha1, nonce, nc, cnonce, qop, ha2])
        if response != ref_response:
            logging.info('Authentication for user %s denied' % self.user.label)
            return False

        logging.info('Authenticated user %s' % self.user.label)
        return True

    def require_authentication(self):
        random.seed()
        nonce = str(random.randint(0, 999999))
        params = {'realm': self.user_class.realm, 'qop': 'auth', 'nonce': nonce,
                  'opaque': self.opaque_from_nonce(nonce, now_utc())}
        auth_header = 'Digest %s' % paramslist_from_dict(params)
        self.response.headers.add('WWW-Authenticate', auth_header)
        self.response.status_int = 401  # Unauthorized

    @staticmethod
    def opaque_from_nonce(nonce, now):
        date_string = now.strftime('%Y%m%d%H') + str(now.minute // 12)
        return md5_hash([date_string, nonce, 'FDhgfliubnw'])

    # ------------ Handling content ------------------------------------------------------------------------------------

    @property
    def input_data_type(self):
        type_string = self.request.headers.get('Content-Type')
        if type_string is not None:
            components = type_string.split(';')
            data_type = DataType.type_for_string(components[0])
            if data_type in self.resource_class.readable_data_types():
                return data_type

    def output_data_type(self, target_class):
        accept_string = self.request.headers.get('Accept')
        acceptable_types = []
        if accept_string is not None:
            accept_list = accept_string.split(',')
            for accept in accept_list:
                components = accept.split(';')
                data_type = DataType.type_for_string(components[0])
                if data_type is not None:
                    acceptable_types.append(data_type)
            for data_type in acceptable_types:
                if data_type in target_class.writable_data_types():
                    return data_type

    def write_output(self, resource, data_type):
        logging.info('Send: %s' % resource)
        self.response.content_type = DataType.s[data_type]
        self.response.headers.add('Last-Modified', resource.last_modified_http)
        self.response.out.write(resource.serialization_of_type(data_type))

