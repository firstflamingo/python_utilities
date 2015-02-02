# coding=utf-8
#
#  Copyright (c) 2011-2015 First Flamingo Enterprise B.V.
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
#  markup.py
#  firstflamingo/python_utilities
#
#  Created by Berend Schotanus on 23-Nov-2011.
#

from google.appengine.api import users
import logging
import xml.sax

# ====== Generic XML Classes ===========================================================================================

class XMLElement:
    OPEN_TEMPLATE           = '<%s>'
    CLOSE_TEMPLATE          = '</%s>'
    SELFCLOSING_TEMPLATE    = '<%s/>'
    ATTRIBUTE_TEMPLATE      = '%s="%s"'
    
    def __init__(self, type, attributes=None, content=None):
        self.type = type
        if attributes == None:
            self.attributes = {}
        else:
            self.attributes = attributes
        if content == None:
            self.content = []
        else:
            self.content = content
    
    def set_attribute(self, key, value):
        self.attributes[key] = value
    
    def set_time(self, timeStamp):
        self.set_attribute('time', rfc3339String(timeStamp))
    
    def add(self, newContent):
        self.content.append(newContent)
    
    def write(self, depth=0, lf=False):
        if depth > 10: raise Exception('exceeds max recurse depth %d' % depth)
        list = [self.type]
        for key, value in self.attributes.items():
            list.append(XMLElement.ATTRIBUTE_TEMPLATE % (key, value))
        attributed_type = ' '.join(list)
        list = []
        if self.content:
            list.append(XMLElement.OPEN_TEMPLATE % attributed_type)
            for element in self.content:
                try:
                    theString = element.write(depth + 1, lf=lf)
                    list.append(theString)
                except AttributeError:
                    list.append(unicode(element))
            list.append(XMLElement.CLOSE_TEMPLATE % self.type)
            if lf:
                joinString = '\n' + depth * ' '
            else:
                joinString = ''
            return joinString.join(list)
        else:
            return XMLElement.SELFCLOSING_TEMPLATE % attributed_type

class XMLDocument:
    
    def __init__(self, name):
        self.root = XMLElement(name)
    
    def doctype(self):
        return '<?xml version="1.0" encoding="UTF-8"?>'
    
    def write(self, lf=False):
        if lf:
            joinString = '\n'
        else:
            joinString = ''
        return joinString.join([self.doctype(), self.root.write(lf=lf)])

# ====== Functions creating XML elements ===============================================================================

def element_with_id(name, id):
    return XMLElement(name, {'id': id})

def element_with_content(name, content):
    return XMLElement(name, content=[content])

# ====== XML Parser ====================================================================================================


class XMLImporter(xml.sax.handler.ContentHandler):
    """
    xml.sax ContentHandler, intended to be subclassed
    Compares an existing data set with imported xml data, creates a dictionary with changed objects
    and a dictionary with objects that don't appear in the xml.
    The actual reading of the data will be done in a subclass implementation of start_xml_element and end_xml_element
    Fetched data must be (temporarily) stored in attributes of the Importer
    Results must be saved in endDocument()
    The following methods must be implemented in subclasses:
    active_xml_tags()
    existing_objects_dictionary()
    key_for_current_object()
    create_new_object(key)
    start_xml_element(name, attrs)
    end_xml_element(name)
    update_object(existing_object)
    """

    data = None
    changes = False
    old_objects = None
    updated_objects = None
    new_objects = None

    def startDocument(self):
        self.old_objects = self.existing_objects_dictionary()
        self.updated_objects = {}
        self.new_objects = {}

    def endDocument(self):
        self.save_objects()

    def startElement(self, name, attrs):
        self.data = []
        self.start_xml_element(name, attrs)

    def endElement(self, name):
        if name in self.active_xml_tags():
            key = self.key_for_current_object()
            if key is not None:
                current_object = self.pop_from_old_objects(key)
                if not current_object:
                    current_object = self.create_new_object(key)
                self.changes = False
                self.update_object(current_object, name)
                self.new_objects[key] = current_object
                if self.changes:
                    self.updated_objects[key] = current_object
        self.end_xml_element(name)

    def characters(self, string):
        self.data.append(string)

    def pop_from_old_objects(self, key):
        current_object = self.old_objects.get(key)
        if current_object:
            del self.old_objects[key]
        else:
            current_object = self.new_objects.get(key)
        return current_object

    def active_xml_tags(self):
        """
        Provides the name of the xml element that encapsulates the objects that must be imported.
        Must be overwritten in subclasses

        """
        return None

    def existing_objects_dictionary(self):
        """
        Provides a dictionary with the objects that will be updated by the import.
        Must be overwritten in subclasses

        """
        return {}

    def key_for_current_object(self):
        """
        Provides the key to store the current object. If 'None' is returned the current object will be ignored.
        Must be overwritten in subclasses

        """
        return None

    def create_new_object(self, key):
        """
        Provides a new blank object, to be filled with the current import.
        Must be overwritten in subclasses

        """
        return None

    def start_xml_element(self, name, attrs):
        """
        Gives subclasses the opportunity to read data from the xml element
        """
        pass

    def end_xml_element(self, name):
        """
        Gives subclasses the opportunity to read data from the xml element
        """
        pass

    def update_object(self, existing_object, name):
        """
        Gives subclasses the opportunity to apply the imported data upon an existing (or newly created) object.
        If changes are applied, self.changes must be set to True, for the changes te be saved.
        Must be overwritten in subclasses
        """
        pass

    def save_objects(self):
        """
        Gives subclasses the opportunity to save the imported objects.
        Must be overwritten in subclasses
        """
        pass

# ====== Generic HTML Classes ==========================================================================================

class HTMLDocument(XMLDocument):
    
    def __init__(self, title, language='en', charset='UTF-8'):
        XMLDocument.__init__(self, 'html')
        self.head = XMLElement('head')
        self.head.add(title_tag(title))
        self.head.add(meta('charset', charset))
        self.root.add(self.head)
        self.body = XMLElement('body')
        self.root.add(self.body)
        self.root.set_attribute('lang', language)
    
    def doctype(self):
        return '<!doctype html>'

class HTMLTable():
    
    def __init__(self, name, columnTitles):
        self.name = name
        self.width = len(columnTitles)
        self.titles = columnTitles
        self.rows = []
    
    def set_title(self, key, name):
        self.titles[key] = name
    
    def add_row(self):
        newRow = HTMLTableRow(self.width)
        self.rows.append(newRow)
        return newRow
    
    def fill_data(self, data):
        if not self.format: return
        for dataRow in data:
            tableRow = self.add_row()
            for col in range(len(dataRow)):
                if col >= len(self.format): break
                tableRow.add_to_cell(col, self.format[col] % dataRow[col])
    
    def write(self, depth, lf=False):
        root = element_with_id('table', self.name)
        colgroup = XMLElement('colgroup')
        table_head = XMLElement('tr')
        i = 0
        while i < self.width:
            colgroup.add(element_with_id('col', self.name + '_col%02d' % i))
            table_head.add(XMLElement('th', {'scope': 'col', 'class': 'C%02d' % i}, [self.titles[i]]))
            i += 1
        root.add(colgroup)
        root.add(XMLElement('thead', {}, [table_head]))
        table_body = XMLElement('tbody')
        for row in self.rows:
            row_object = XMLElement('tr')
            for cell in row.cells:
                row_object.add(cell)
            table_body.add(row_object)
        root.add(table_body)
        return root.write(depth, lf=lf)

class HTMLTableRow():
    
    def __init__(self, width):
        self.cells = [''] * width
        i = 0
        while i < width:
            self.cells[i] = table_cell(i)
            i += 1
    
    def add_to_cell(self, index, content):
        self.cells[index].add(content)
    
    def add_date_to_cell(self, index, value):
        self.cells[index].add(date(value))
    
    def add_time_to_cell(self, index, value):
        self.cells[index].add(time(value))
    
    def add_link_to_cell(self, index, href, text):
        self.cells[index].add(anchor(href, text))

# ====== Functions creating HTML elements ==============================================================================

def title_tag(text):
    return XMLElement('title', {}, [text])

def meta(key, value):
    return XMLElement('meta', {key: value}, [])

def link(rel, href):
    return XMLElement('link', {'rel': rel, 'href': href}, [])

def div(identifier):
    return XMLElement('div', {'id':identifier}, [''])

def anchor(href, content):
    return XMLElement('a', {'href': href}, [content])

def link_to_page(format, page):
    return anchor(format % page, '%d' % page)

def paragraph(text, attributes={}):
    return XMLElement('p', attributes, [text])

def heading(level, text, attributes={}):
    type = 'h%d' % level
    return XMLElement(type, attributes, [text])

def table_cell(column_index):
    return XMLElement('td', {'class': 'C%02d' % column_index}, [])

def form(action, method='get'):
    return XMLElement('form', {'action':action, 'method':method}, [])

def input(type, name=None, value=None, size=None):
    attributes = {'type':type}
    if name: attributes['name'] = name
    if value: attributes['value'] = value
    if size: attributes['size'] = size
    return XMLElement('input', attributes, [])

def date(timeStamp):
    m = timeStamp.month
    if m ==  1: monthName = 'jan'
    if m ==  2: monthName = 'feb'
    if m ==  3: monthName = 'mrt'
    if m ==  4: monthName = 'apr'
    if m ==  5: monthName = 'mei'
    if m ==  6: monthName = 'jun'
    if m ==  7: monthName = 'jul'
    if m ==  8: monthName = 'aug'
    if m ==  9: monthName = 'sep'
    if m == 10: monthName = 'okt'
    if m == 11: monthName = 'nov'
    if m == 12: monthName = 'dec'
    userString = '%d %s.\'%02d' % (timeStamp.day, monthName, timeStamp.year - 2000)
    return XMLElement('time', {'datetime':rfc3339String(timeStamp)}, [userString])

def time(timeStamp):
    userString = '%02d:%02d:%02d' % (timeStamp.hour, timeStamp.minute, timeStamp.second)
    return XMLElement('time', {'datetime':rfc3339String(timeStamp)}, [userString])

def rfc3339String(t):
    return '%04d-%02d-%02dT%02d:%02d:%02dZ' % (t.year, t.month, t.day, t.hour, t.minute, t.second)

# ====== HTML template functions =======================================================================================

def login_link():
    return anchor(users.create_login_url('/'), 'login')

def user_id():
    user = users.get_current_user().nickname()
    logout_link = anchor(users.create_logout_url('/'), 'logout')
    content = '<b>%s</b> | %s' % (user, logout_link.write())
    return XMLElement('div', {'id': 'user_id'}, [content])

def main_menu(menu_list):
    list = XMLElement('ul')
    for item in menu_list:
        list.add(element_with_content('li', anchor(item[1], item[0])))
    return list

def page_navigator(currentPage, lastPage, urlFormat):
    par = paragraph('pagina: ')
    before = currentPage - 1
    after = lastPage - currentPage
    if before > 1:
        par.add(link_to_page(urlFormat, 1))
        par.add(' ')
    if before > 2:
        par.add('... ')
    if before > 0:
        par.add(link_to_page(urlFormat, currentPage - 1))
        par.add(' ')
    par.add('<strong>%d</strong>' % currentPage)
    if after > 0:
        par.add(' ')
        par.add(link_to_page(urlFormat, currentPage + 1))
    if after > 2:
        par.add(' ...')
    if after > 1:
        par.add(' ')
        par.add(link_to_page(urlFormat, lastPage))
    return par
