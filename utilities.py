#!/usr/bin/env python3
#
# Copyright 2017 Petuum, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# The MIT License (MIT)
#
# Copyright (c) 2016 Benedikt Schmitt
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to
# deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.
"""
jsonapi.utilities
=================

This module contains some helpers, which are frequently needed in different
modules and situations.
"""

import json
import re

try:
    import bson
    import bson.json_util
except ImportError:
    bson = None

from jsonapi_framework.errors import BadRequest
from jsonapi_framework.debug import DEBUG


def dump_json(obj):
    """
    Serializes the Python object *obj* to a JSON string.

    The default implementation uses Python's :mod:`json` module with some
    features from :mod:`bson` (if it is available).

    You *can* override this method.
    """
    indent = 4 if DEBUG else None
    default = bson.json_util.default if bson else None
    sort_keys = DEBUG
    return json.dumps(obj, indent=indent, default=default, sort_keys=sort_keys)


def load_json(obj):
    """
    Decodes the JSON string *obj* and returns a corresponding Python object.

    The default implementation uses Python's :mod:`json` module with some
    features from :mod:`bson` (if available).

    You *can* override this method.
    """
    default = bson.json_util.object_hook if bson else None
    return json.loads(obj, object_hook=default)


def link_for_collection(link_prefix, japi_resource_url_component):
    return "{}/{}".format(link_prefix, japi_resource_url_component)


def link_for_resource(link_prefix, japi_resource_url_component, id):
    return "{}/{}/{}".format(link_prefix, japi_resource_url_component, id)


def link_for_related(link_prefix, japi_resource_url_component, id,
                     relationship_name):
    return "{}/{}/{}/{}".format(link_prefix, japi_resource_url_component, id,
                                relationship_name)


def link_for_relationship(link_prefix, japi_resource_url_component, id,
                          relationship_name):
    return "{}/{}/{}/relationships/{}".format(
        link_prefix, japi_resource_url_component, id, relationship_name)


def link_for_pagination(link_prefix, japi_resource_url_component, query):
    return "{}/{}?{}".format(link_prefix, japi_resource_url_component, query)


def get_sparse_fields(args, resource_class):
    """
    This method will get the sparse fields set from args.
    :param args: from request parameters
    :param resource_class: resource class
    :return: sparse_fields_to_return is normal sparse fields set,
    sparse_fields_for_query is for database query
    """
    sparse_fields_to_return = None
    sparse_fields_for_query = None
    fields_re = re.compile(r"fields\[([A-z0-9_]+)\]")
    for key, value in args:
        match = re.fullmatch(fields_re, key)
        if match:
            sparse_fields_to_return = ([] if sparse_fields_to_return is None
                                       else sparse_fields_to_return)
            sparse_fields_for_query = ([] if sparse_fields_for_query is None
                                       else sparse_fields_for_query)
            columns = split_str_on_comma(value)
            for val in columns:
                val = val.strip()
                if val:
                    if val in resource_class._rels_by_japi_name:
                        sparse_fields_for_query.append(
                            getattr(resource_class, val).mapped_fk_name)
                    else:
                        sparse_fields_for_query.append(val)
                    sparse_fields_to_return.append(val)
    return sparse_fields_to_return, sparse_fields_for_query


def get_order_by_fields(args, resource_class):
    """
    This method will get the fields that ordered by through args.
    :param args: from request parameters
    :param resource_class: resource class
    :return: a list of fields
    """
    sort_value = args.get('sort')
    order_by = split_str_on_comma(sort_value) if sort_value else []
    for index, value in enumerate(order_by):
        if value not in resource_class._rels_by_japi_name:
            if value[0] == '-':
                field_name = value[1:]
                if field_name in resource_class._rels_by_japi_name:
                    value = value.replace(field_name, getattr(
                        resource_class, field_name).mapped_fk_name)
                    order_by[index] = value
        else:
            value = getattr(resource_class, value).mapped_fk_name
            order_by[index] = value
    return order_by


def get_filter(args, resource_class):
    """
    This method will return the fields filtered by.
    :param args: from request parameters
    :param resource_class: resource class
    :return: a dictionary that contains filter
    example:
    filters = [
        {
            'and': [
                {
                    'or': [
                        {'field': 'name', 'op': '==', 'value': 'foo'},
                        {'field': 'name', 'op': 'like', 'value': '%abc'},
                    ]
                },
                {
                    'or': [
                        {'field': 'id', 'op': '==', 'value': 1}
                    ]
                }
            ]
        }
    ]
    """
    filters = None
    filter_re = re.compile(r"filter\[([A-z0-9_]+)\]")
    for key, value in args:
        match = re.fullmatch(filter_re, key)
        if match:
            key = key[key.find('[') + 1: key.find(']')]
            if key in resource_class._rels_by_japi_name:
                key = getattr(resource_class, key).mapped_fk_name
            columns = split_str_on_comma(value)
            if not columns:
                continue
            or_filter = []
            or_dic = {}
            or_dic['or'] = or_filter
            if filters is None:
                and_filter = []
                and_filter.append(or_dic)
                filters = []
                filters.append({'and': and_filter})
            else:
                filters[0]['and'].append(or_dic)
            for item in columns:
                dic = {}
                match_like = re.search('%', item)
                if match_like:
                    dic['op'] = 'like'
                else:
                    dic['op'] = '=='
                dic['field'] = key
                dic['value'] = item
                or_filter.append(dic)
    return filters


def check_number(number, name):
    """
    This method converts input to number if
    possible and check if is valid.
    :param number: input number, might be string
    :param name: name of the number
    :return: converted number
    """
    if number:
        try:
            number = int(number)
        except Exception:
            raise BadRequest(
                detail="The '%s' must be an integer." % name,
                source_parameter="%s" % name
            )
        if number < 1:
            raise BadRequest(
                detail="The '%s' must be >= 1." % name,
                source_parameter="%s" % name
            )
    return number


def split_str_on_comma(str):
    """
    This function will split str using comma except
    there is a '\' before it. Meanwhile, '\' if used as
    escaped symbol will be removed.
    example:
    Raw string "hello,world\,hello\\,again\\\,world" will be
    ["hello", "world,hello\", "again\,world"].
    In python format, the str will actually be
    'hello,world\\,hello\\\\,again\\\\\\,world',
    and the list will actually be
    ['hello', 'world,hello\\', 'again\\,world'].
    :param str: input str to parse
    :return: the result list
    """
    length_str = len(str)
    # To check if the current character is escaped.
    is_escaped = False
    result = []
    sub_str = ""
    for i in range(length_str):
        # If this comma is not escaped,
        # separate with this comma.
        if str[i] == "," and not is_escaped:
            # Check if it is an empty string.
            if sub_str:
                result.append(sub_str)
            sub_str = ""
        # If this current character is escaped,
        # it will have no use, and since it is added
        # to sub_str when it is considered as escaped,
        # just continue.
        elif is_escaped:
            is_escaped = False
            continue
        else:
            # If current is escape symbol, and itself is
            # not escaped, put the is_escaped flag to True,
            # and remove this symbol by jumping to next
            # character.
            if str[i] == "\\":
                is_escaped = True
                # Check the string boundary.
                if i < length_str - 1:
                    i = i + 1
            sub_str = sub_str + str[i]
    if sub_str:
        result.append(sub_str)
    return result
