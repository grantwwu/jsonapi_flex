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
import unittest

from ddt import ddt, data
from unittest.mock import patch
from jsonapi_framework.japi_format_validators \
    import (assert_resource_object,
            assert_attributes_object,
            assert_meta_object,
            assert_links_object,
            assert_link,
            assert_resource_identifier_object,
            assert_relationship_object,
            assert_to_one_relationship_object,
            assert_to_many_relationship_object,
            assert_to_many_resource_linkage,
            assert_relationships_object,
            assert_to_one_resource_linkage)
from jsonapi_framework.errors import BadRequest


@ddt
class JapiFormatValidatorsTestCase(unittest.TestCase):
    def test_assert_resource_object_correct(self):
        resource = {"type": "foo", "id": "1", "attributes": {"attr": "value"}}
        self.assertEqual(assert_resource_object(
            resource, id_required=True, source_pointer="/"), None)

    def test_assert_resource_object_id_not_required(self):
        resource = {"type": "foo", "attributes": {"attr": "value"}}
        self.assertEqual(assert_resource_object(
            resource, id_required=False, source_pointer="/"), None)

    @data("str",
          {"type": "foo", "id": "1",
           "attributes": {"attr": "value"}, "extra": "val"},
          {"type": "foo", "attributes": {"attr": "value"}},
          {"id": 1, "type": "str", "attributes": {"attr": "value"}},
          {"id": "1", "type": {}, "attributes": {"attr": "value"}},
          {"id": "1", "attributes": {"attr": "value"}},
          {"type": "foo", "id": "1", "links": "val"},
          {"type": "foo", "id": "1", "attributes": "value"},
          {"type": "foo", "id": "1", "relationships": "value"},
          {"type": "foo", "id": "1", "meta": "str"})
    def test_assert_resource_object_bad_request(self, resource):
        with patch('jsonapi_framework.japi_format_validators.'
                   'assert_attributes_object') as attributes_function, \
                patch('jsonapi_framework.japi_format_validators.'
                      'assert_relationships_object') as \
                relationships_function, \
                patch('jsonapi_framework.japi_format_validators.'
                      'assert_links_object') as links_function, \
                patch('jsonapi_framework.japi_format_validators.'
                      'assert_meta_object') as meta_function:
            attributes_function.side_effect, \
                 relationships_function.side_effect, \
                 links_function.side_effect, \
                 meta_function.side_effect = \
                 [BadRequest for _ in range(4)]
            with self.assertRaises(BadRequest):
                assert_resource_object(
                    resource, id_required=True, source_pointer="/")

    def test_assert_attributes_object(self):
        d = "str"
        with self.assertRaises(BadRequest):
            assert_attributes_object(d)

    def test_assert_meta_object(self):
        d = "str"
        with self.assertRaises(BadRequest):
            assert_meta_object(d)

    @data("str",
          {"href": "/", "meta": {}})
    def test_assert_link_str(self, d):
        self.assertEqual(assert_link(d, source_pointer="/"), None)

    @data({},
          {"href": "/", "meta": {}, "extra": "extra_value"},
          {"href": {}, "meta": {}},
          {"href": {}, "meta": "str"})
    def test_assert_link(self, d):
        with patch('jsonapi_framework.japi_format_validators.'
                   'assert_meta_object') as meta_function:
            meta_function.side_effect = BadRequest
            with self.assertRaises(BadRequest):
                assert_link(d, source_pointer="/")

    def test_assert_links_object_wrong(self):
        d = "str"
        with self.assertRaises(BadRequest):
                assert_links_object(d)

    def test_assert_links_object_correct(self):
        d = {}
        with patch('jsonapi_framework.japi_format_validators.'
                   'assert_link') as link_function:
            link_function.side_effect = None
            self.assertEqual(assert_links_object(d), None)

    def test_assert_resource_identifier_object_correct(self):
        resource = {"id": "1", "type": "foo"}
        self.assertEqual(assert_resource_identifier_object(resource), None)

    @data("str",
          {"id": "1", "type": "foo", "extra": "extra_value"},
          {"id": 1, "type": "foo"},
          {"type": "foo"},
          {"id": "1", "type": {}},
          {"id": "1"},
          {"id": "1", "type": "foo", "meta": "str"})
    def test_assert_resource_identifier_object_meta(self, resource):
        with patch('jsonapi_framework.japi_format_validators.'
                   'assert_meta_object') as meta_function:
            meta_function.side_effect = BadRequest
            with self.assertRaises(BadRequest):
                assert_resource_identifier_object(resource)

    def test_assert_relationship_object_correct(self):
        resource = {"data": "", "links": {}, "meta": {}}
        with patch('jsonapi_framework.japi_format_validators.'
                   'assert_links_object') as link_function,\
                patch('jsonapi_framework.japi_format_validators.'
                      'assert_meta_object') as meta_function:
            link_function.side_effect = None
            meta_function.side_effect = None
            self.assertEqual(assert_relationship_object(resource), None)

    @data("str",
          {},
          {"data": "", "extra": "extra_value"})
    def test_assert_relationship_object_invalid_dic(self, resource):
            with self.assertRaises(BadRequest):
                assert_relationship_object(resource)

    def test_assert_relationship_object_to_one(self):
        resource = {"data": ""}
        with patch('jsonapi_framework.japi_format_validators.'
                   'assert_to_one_resource_linkage') \
                as to_one_resource_linkage:
            to_one_resource_linkage.side_effect = BadRequest
            with self.assertRaises(BadRequest):
                assert_relationship_object(resource, to_one=True)

    def test_assert_relationship_object_to_many(self):
        resource = {"data": ""}
        with patch('jsonapi_framework.japi_format_validators.'
                   'assert_to_one_resource_linkage') \
                as to_one_resource_linkage:
            to_one_resource_linkage.side_effect = BadRequest
            with self.assertRaises(BadRequest):
                assert_relationship_object(resource, to_many=True)

    def test_assert_to_one_relationship_object(self):
        resource = {"data": {"id": "1", "type": "foo", "meta": {}}}
        with patch('jsonapi_framework.japi_format_validators.'
                   'assert_relationship_object') as assert_relationship_object:
            assert_relationship_object.side_effect = None
            self.assertEqual(assert_to_one_relationship_object(resource), None)

    def test_assert_to_many_relationship_object(self):
        resource = {"data": [{"id": "1", "type": "foo", "meta": {}},
                             {"id": "2", "type": "foo", "meta": {}}]}
        with patch('jsonapi_framework.japi_format_validators.'
                   'assert_relationship_object') \
                as assert_relationship_object,\
                patch('jsonapi_framework.japi_format_validators.'
                      'assert_to_many_resource_linkage') \
                as assert_to_many_resource_linkage:
            assert_relationship_object.side_effect = None
            assert_to_many_resource_linkage.side_effect = None
            self.assertEqual(assert_to_many_relationship_object(
                resource), None)

    def test_assert_to_many_resource_linkage_correct(self):
        resource = [{"id": "1", "type": "foo"}, {"id": "2", "type": "foo"}]
        with patch('jsonapi_framework.japi_format_validators.'
                   'assert_resource_identifier_object') \
                as assert_resource_identifier_object:
            assert_resource_identifier_object.side_effect = None
            self.assertEqual(assert_to_many_resource_linkage(resource), None)

    def test_assert_to_many_resource_linkage_bad_request(self):
        resource = [{"type": "foo"}, {"id": "2", "type": "foo"}]
        with patch('jsonapi_framework.japi_format_validators.'
                   'assert_resource_identifier_object') \
                as assert_resource_identifier_object:
            assert_resource_identifier_object.side_effect = BadRequest
            with self.assertRaises(BadRequest):
                assert_to_many_resource_linkage(resource)

    def test_assert_to_many_resource_linkage_not_list(self):
        resource = {}
        with self.assertRaises(BadRequest):
            assert_to_many_resource_linkage(resource)

    def test_assert_relationships_object(self):
        d = "str"
        with patch('jsonapi_framework.japi_format_validators.'
                   'assert_relationship_object') as assert_relationship_object:
            assert_relationship_object.side_effect = None
            with self.assertRaises(BadRequest):
                assert_relationships_object(d)

    @data(None, {"id": "1", "type": "foo"})
    def test_assert_to_one_resource_linkage_correct(self, resource):
        with patch('jsonapi_framework.japi_format_validators.'
                   'assert_resource_identifier_object') \
                as assert_resource_identifier_object:
            assert_resource_identifier_object.side_effect = None
            self.assertEqual(assert_to_one_resource_linkage(resource), None)

    def test_assert_to_one_resource_linkage_bad_request(self):
        d = "str"
        with self.assertRaises(BadRequest):
            assert_relationships_object(d)
