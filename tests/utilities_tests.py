#!usr/bin/env python3
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
import json
import unittest
import unittest.mock
import werkzeug

from ddt import ddt, data
from unittest.mock import patch
from jsonapi_framework.utilities import (dump_json,
                                         load_json,
                                         link_for_collection,
                                         link_for_resource,
                                         link_for_related,
                                         link_for_relationship,
                                         get_sparse_fields,
                                         get_filter,
                                         get_order_by_fields)


@ddt
class UtilitiesTestCase(unittest.TestCase):
    resource = unittest.mock.MagicMock()
    resource._rels_by_japi_name = ["rel1", "rel2"]
    resource.rel1.mapped_fk_name = "rel1_id"
    resource.rel2.mapped_fk_name = "rel2_id"

    @data(True, False)
    def test_dump_json(self, debug):
        dict1 = {"name": "file", "size": 1024}
        with patch('jsonapi_framework.utilities.DEBUG', debug):
            result = dump_json(dict1)
            dict2 = json.loads(result)
            self.assertDictEqual(dict1, dict2)

    @data(True, False)
    def test_load_json(self, debug):
        json_str = '{"name": "file", "size": 1024}'
        dict1 = {"name": "file", "size": 1024}
        with patch('jsonapi_framework.utilities.DEBUG', debug):
            result = load_json(json_str)
            self.assertDictEqual(dict1, result)

    def test_link_for_collection(self):
        self.assertEqual(link_for_collection("/nar1/nar2", "nar3"),
                         "/nar1/nar2/nar3")

    def test_link_for_resource(self):
        self.assertEqual(link_for_resource("/nar1/nar2", "nar3", "1"),
                         "/nar1/nar2/nar3/1")

    def test_link_for_related(self):
        self.assertEqual(link_for_related("/nar1/nar2", "nar3", "1", "foo"),
                         "/nar1/nar2/nar3/1/foo")

    def test_link_for_relationship(self):
        self.assertEqual(link_for_relationship(
            "/nar1/nar2", "nar3", "1", "foo"),
            "/nar1/nar2/nar3/1/relationships/foo")

    @data
    def test_get_sparse_fields_empty(self):
        args = werkzeug.MultiDict([('fields[foo]', '')])
        args = args.items(multi=True)
        sparse_fields_to_return = []
        sparse_fields_for_query = []
        self.assertCountEqual(get_sparse_fields(args, self.resource),
                              (sparse_fields_to_return,
                               sparse_fields_for_query))

    @data
    def test_get_sparse_fields_one(self):
        args = werkzeug.MultiDict([('fields[foo]', 'col')])
        args = args.items(multi=True)
        sparse_fields_to_return = ["col"]
        sparse_fields_for_query = ["col"]
        self.assertCountEqual(get_sparse_fields(args, self.resource),
                              (sparse_fields_to_return,
                               sparse_fields_for_query))

    @data
    def test_get_sparse_fields_relationship(self):
        args = werkzeug.MultiDict([('fields[foo]', 'rel1')])
        args = args.items(multi=True)
        sparse_fields_to_return = ["rel1"]
        sparse_fields_for_query = ["rel1_id"]
        self.assertCountEqual(get_sparse_fields(args, self.resource),
                              (sparse_fields_to_return,
                               sparse_fields_for_query))

    @data
    def test_get_sparse_fields_multi(self):
        args = werkzeug.MultiDict([('fields[foo]', 'col1,col2'),
                                   ('fields[foo]', 'rel1'),
                                   ('fields[foo]', 'rel2')])
        args = args.items(multi=True)
        sparse_fields_to_return = ["col1", "col2", "rel1", "rel2"]
        sparse_fields_for_query = ["col1", "col2", "rel1_id",
                                   "rel2_id"]
        self.assertCountEqual(get_sparse_fields(args, self.resource),
                              (sparse_fields_to_return,
                               sparse_fields_for_query))

    @data
    def test_get_order_by_fields_empty(self):
        args = werkzeug.MultiDict([('sort', '')])
        order_by = []
        self.assertCountEqual(get_order_by_fields(args, self.resource),
                              order_by)

    @data
    def test_get_order_by_fields_ascending(self):
        args = werkzeug.MultiDict([('sort', 'col')])
        order_by = ["col"]
        self.assertCountEqual(get_order_by_fields(args, self.resource),
                              order_by)

    @data
    def test_get_order_by_fields_descending(self):
        args = werkzeug.MultiDict([('sort', '-col')])
        order_by = ["-col"]
        self.assertCountEqual(get_order_by_fields(args, self.resource),
                              order_by)

    @data
    def test_get_order_by_fields_rel_ascending(self):
        args = werkzeug.MultiDict([('sort', 'rel1')])
        order_by = ["rel1_id"]
        self.assertCountEqual(get_order_by_fields(args, self.resource),
                              order_by)

    @data
    def test_get_order_by_fields_rel_descending(self):
        args = werkzeug.MultiDict([('sort', '-rel1')])
        order_by = ["-rel1_id"]
        self.assertCountEqual(get_order_by_fields(args, self.resource),
                              order_by)

    @data
    def test_get_order_by_fields_multi(self):
        args = werkzeug.MultiDict(
            [('sort', 'col1,-col2,-rel1,rel2')])
        order_by = ["col1", "-col2", "-rel1_id", "rel2_id"]
        self.assertDictEqual(get_order_by_fields(args, self.resource),
                             order_by)

    @data
    def test_get_filter_empty(self):
        args = werkzeug.MultiDict([('filter[col]', '')])
        args = args.items(multi=True)
        filter = [{"field": "col", "op": "==", "value": ""}]
        self.assertDictEqual(get_filter(args, self.resource), filter)

    @data
    def test_get_filter_equal(self):
        args = werkzeug.MultiDict([('filter[col]', 'search_value')])
        args = args.items(multi=True)
        filter = [{"field": "col", "op": "==", "value": "search_value"}]
        self.assertDictEqual(get_filter(args, self.resource), filter)

    @data
    def test_get_filter_like(self):
        args = werkzeug.MultiDict([('filter[col]', '%search_value%')])
        args = args.items(multi=True)
        filter = [{"field": "col", "op": "like", "value": "%search_value%"}]
        self.assertDictEqual(get_filter(args, self.resource), filter)

    @data
    def test_get_filter_multi(self):
        args = werkzeug.MultiDict([('filter[col1]', '%search_value1%'),
                                   ('filter[col2]', 'search_value2')])
        args = args.items(multi=True)
        filter = [{"field": "col1", "op": "like", "value": "%search_value1%"},
                  {"field": "col2", "op": "==", "value": "search_value2"}]
        self.assertDictEqual(get_filter(args, self.resource), filter)
