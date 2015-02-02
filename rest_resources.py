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
#  rest_resources.py
#  firstflamingo/python_utilities
#
#  Created by Berend Schotanus on 18-Apr-2014.
#

import logging, json, re
import xml.sax
from google.appengine.ext import ndb
from google.appengine.api import memcache
from markup import XMLDocument
from ffe_utils import md5_hash
from ffe_time import mark_utc, rfc1123_from_utc


class DataType:
    xml, json = range(2)
    s = ['application/xml', 'application/json']

    @classmethod
    def type_for_string(cls, string):
        data_type = None
        for index in range(len(cls.s)):
            if string == cls.s[index]:
                data_type = index
                break
        return data_type


class Resource(ndb.Model):
    """
    Resource is an abstract superclass for resources conforming to the rest_interface.
    It has subclasses for different kinds of resources:
    1) Catalog
       publishes the list of all objects of a resource class
    2) PublicResource
       for publications with fixed index, readable by everyone
    3) User
       models a user, enables user authentication
    4) UserResource
       for user resources with server generated index and accessible by the specified user
    """
    url_name = None
    last_modified = ndb.DateTimeProperty(auto_now=True)
    identifier_regex = re.compile('[0-9]{1,19}$')
    is_publication = False

    # ------------ Object lifecycle ------------------------------------------------------------------------------------

    @classmethod
    def new(cls, identifier=None):
        self = cls(id=cls.valid_identifier(identifier))
        self.awake_from_create()
        cls.reset_ids()
        return self

    @classmethod
    def get(cls, identifier=None, create=False):
        self = cls.get_by_id(cls.valid_identifier(identifier))
        if self:
            self.awake_from_fetch()
        elif create:
            self = cls.new(identifier=identifier)
        return self

    def delete(self):
        self.key.delete()
        self.__class__.reset_ids()

    def awake_from_create(self):
        pass

    def awake_from_fetch(self):
        pass

    # ------------ Object metadata -------------------------------------------------------------------------------------

    @property
    def last_modified_utc(self):
        return mark_utc(self.last_modified.replace(microsecond=0))

    @property
    def last_modified_http(self):
        return rfc1123_from_utc(self.last_modified)

    @classmethod
    def valid_identifier(cls, identifier):
        if identifier is None or not cls.identifier_regex.match(str(identifier)):
            raise NoValidIdentifierError
        else:
            return identifier

    @property
    def id_(self):
        return self.key.id()

    def id_part(self, index):
        return self.identifier_regex.match(self.id_).group(index)

    @property
    def url(self):
        return '/%s/%s' % (self.url_name, self.id_)

    def __repr__(self):
        return "<%s:%s - %s>" %\
               (self.__class__.__name__, self.id_, self.last_modified_utc.strftime('%H:%M:%S'))

    # ------------ Finding instances -----------------------------------------------------------------------------------

    @classmethod
    def all_ids(cls):
        """
        Provides a list with ids for all instances of this class, in alphabetical order
        :rtype : list
        """
        memcache_key = '%s_ids' % cls.__name__
        ids_list = memcache.get(memcache_key)
        if not ids_list:
            ids_list = []
            for key in cls.query().iter(keys_only=True):
                ids_list.append(key.id())
            memcache.set(memcache_key, ids_list)
        return ids_list

    @classmethod
    def active_ids(cls):
        """
        Provides a list of ids for instances of the class, with a class specific filter and order
        The default implementation returns all_ids()
        :rtype : list
        """
        return cls.all_ids()

    @classmethod
    def reset_ids(cls):
        memcache.delete('%s_ids' % cls.__name__)

    @classmethod
    def dictionary_from_list(cls, the_list):
        dictionary = {}
        for instance in the_list:
            dictionary[instance.id_] = instance
        return dictionary

    @classmethod
    def objects_dictionary(cls):
        return cls.dictionary_from_list(cls.query().fetch(1000))

    @classmethod
    def paginated_objects(cls, page=1, length=20):
        return cls.query().fetch(length, offset=(page - 1) * length)

    # ------------ Reading content -------------------------------------------------------------------------------------

    @classmethod
    def readable_data_types(cls):
        return [DataType.json]

    @classmethod
    def xml_handler(cls):
        return None

    @classmethod
    def update_multi(cls, update_string, data_type):
        if data_type == DataType.xml:
            xml.sax.parseString(update_string, cls.xml_handler())

    def update_with_string(self, update_string, data_type):
        if data_type == DataType.json:
            if self.update_with_dictionary(json.loads(update_string)):
                self.put()
        elif data_type == DataType.xml:
            xml.sax.parseString(update_string, self.__class__.xml_handler())

    def update_with_dictionary(self, dictionary):
        return False

    # ------------ Writing content -------------------------------------------------------------------------------------

    @classmethod
    def writable_data_types(cls):
        return [DataType.json]

    def serialization_of_type(self, data_type):
        if data_type == DataType.xml:
            pass
        elif data_type == DataType.json:
            return json.dumps(self.dictionary_from_object())

    @classmethod
    def xml_catalog(cls):
        document = XMLDocument(cls.__name__)
        for object in cls.query().fetch(1000):
            document.root.add(object.xml)
        return document

    def dictionary_from_object(self):
        return {'id': self.id_}


class Catalog(Resource):
    class_module = ndb.TextProperty()
    catalog = ndb.TextProperty()
    identifier_regex = re.compile('[A-Z]\w{1,19}$')

    # ------------ Object lifecycle ------------------------------------------------------------------------------------

    @classmethod
    def new(cls, cataloged_class=None):
        self = cls(id=cataloged_class.__name__)
        self.class_module = cataloged_class.__module__
        self.put()
        return self

    @classmethod
    def get(cls, cataloged_class=None, create=True):
        self = cls.get_by_id(cataloged_class.__name__)
        if self is None and create:
            self = cls.new(cataloged_class=cataloged_class)
        return self

    def invalidate(self):
        if self.catalog is not None:
            logging.info('== invalidate catalog ==')
            self.catalog = None
            self.put()

    # ------------ Object metadata -------------------------------------------------------------------------------------

    @property
    def cataloged_class(self):
        module = __import__(self.class_module)
        return getattr(module, self.id_)

    # ------------ Writing content -------------------------------------------------------------------------------------

    def serialization_of_type(self, data_type):
        if data_type == DataType.json:
            if self.catalog is None:
                array = []
                for entry in self.cataloged_class.query().order(-Resource.last_modified).fetch(1000):
                    array.append({'id': entry.id_, 'lm': entry.last_modified_utc.strftime('%Y-%m-%dT%H:%M:%S')})
                self.catalog = json.dumps(array)
                self.put()
            return self.catalog


class PublicResource(Resource):
    is_publication = True
    identifier_regex = re.compile('\w{1,19}$')

    # ------------ Object lifecycle ------------------------------------------------------------------------------------

    @classmethod
    def new(cls, identifier=None):
        logging.info('Creating new %s with id: %s' % (cls.__name__, identifier))
        cls.invalidate_catalog()
        return super(PublicResource, cls).new(identifier=identifier)

    def put(self):
        super(Resource, self).put()
        self.__class__.invalidate_catalog()

    def delete(self):
        super(PublicResource, self).delete()
        self.__class__.invalidate_catalog()

    @classmethod
    def invalidate_catalog(cls):
        catalog = Catalog.get(cls)
        catalog.invalidate()


class User(Resource):
    ha1 = ndb.StringProperty(indexed=False)
    created = ndb.DateTimeProperty(auto_now_add=True)
    creation_address = ndb.StringProperty(indexed=False)
    name = ndb.StringProperty()
    email = ndb.StringProperty()
    realm = 'tests@firstflamingo.com'
    has_admin_privileges = False

    # ------------ Object metadata -------------------------------------------------------------------------------------

    @property
    def username(self):
        assert self.key is not None
        return str(self.key.id())

    @property
    def password(self):
        return 'protected'

    @password.setter
    def password(self, new_value):
        self.ha1 = md5_hash([self.username, self.realm, new_value])

    def password_equals(self, value):
        check_hash = md5_hash([self.username, self.realm, value])
        return bool(check_hash == self.ha1)

    @property
    def owner_key(self):
        return self.key

    @property
    def label(self):
        """
        Label, used to recognize users in logs
        Default implementation returns the username, subclasses can implement custom behavior
        :return: string
        """
        if self.name:
            return self.name
        return self.username

    @classmethod
    def valid_identifier(cls, identifier):
        if identifier is None:
            return None
        return int(super(User, cls).valid_identifier(str(identifier)))

    # ------------ Reading content -------------------------------------------------------------------------------------

    def update_with_dictionary(self, dictionary):
        changes = False

        if self.ha1 is None:
            user_realm = dictionary.get('realm')
            password = dictionary.get('token')
            if password and user_realm == self.realm:
                self.put()  # Put causes an ndb.key to be created, which is used as username and required for ha1
                self.password = password
            else:
                raise InvalidUpdateDataError
        else:
            old_password = dictionary.get('old-password', '')
            new_password = dictionary.get('new-password')
            if new_password and self.password_equals(old_password):
                self.password = new_password
                changes = True

        name = dictionary.get('name')
        if name:
            self.name = name
            changes = True

        email = dictionary.get('email')
        if email:
            self.email = email
            changes = True

        return changes

    # ------------ Writing content -------------------------------------------------------------------------------------

    def dictionary_from_object(self):
        dictionary = {'username': self.username}
        if self.name:
            dictionary['name'] = self.name
        if self.email:
            dictionary['email'] = self.email
        return dictionary


class UserResource(Resource):
    owner_key = ndb.KeyProperty()

    # ------------ Object lifecycle ------------------------------------------------------------------------------------

    @classmethod
    def new(cls, identifier=None, owner=None):
        if identifier is not None:
            raise NoValidIdentifierError
        logging.info('Creating new %s.' % cls.__name__)
        return super(UserResource, cls).new(identifier=None)

    # ------------ Object metadata -------------------------------------------------------------------------------------

    @classmethod
    def valid_identifier(cls, identifier):
        if identifier is None:
            return None
        return int(super(UserResource, cls).valid_identifier(str(identifier)))


# ====== Exceptions =================================================================================


class NoValidIdentifierError(Exception):
    pass


class InvalidUpdateDataError(Exception):
    pass