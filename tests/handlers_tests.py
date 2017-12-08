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
import werkzeug

from unittest.mock import patch
from unittest.mock import MagicMock
from jsonapi_framework.handler import (ResourceHandler,
                                       CollectionHandler,
                                       RelatedHandler,
                                       ToOneRelationshipHandler)
from jsonapi_framework.response import Response


class ResourceHandlerTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        resource = MagicMock()
        cls.resource_helper = ResourceHandler
        cls.resource_helper.resource_class = resource

    def test_link(self):
        link_prefix = "/nar1/nar2"
        id = "1"
        with patch('jsonapi_framework.handler.link_for_resource') as \
                link_for_resource:
            link_for_resource.return_value = "/nar1/nar2/nar3/1"
            self.assertEqual("/nar1/nar2/nar3/1",
                             self.resource_helper.link(link_prefix, id))

    def test_get(self):
        mock_requests = MagicMock()
        with patch('jsonapi_framework.handler.get_sparse_fields') as \
                get_sparse_fields, \
                patch('jsonapi_framework.handler.dal.query_resource') as \
                query_resource, \
                patch('jsonapi_framework.handler.ResourceHandler.link') as \
                self_link:
            get_sparse_fields.return_value = \
                ["col1", "col2", "rel1", "rel2"], \
                ["col1", "col2", "rel1_id", "rel2_id"]
            query_resource.return_value = MagicMock()
            query_resource.return_value.serialize.return_value = \
                {
                    "type": "foo",
                    "id": "1",
                    "attributes": {
                        "col1": "value1",
                        "col2": "value2"
                    },
                    "relationships": {
                        "rel1": "value3",
                        "rel2": "value4"
                    }
                }
            self_link.return_value = "/nar1/nar2/nar3/1"
            response = Response(status=200, headers=None, body={
                "data": {
                    "type": "foo",
                    "id": "1",
                    "attributes": {
                        "col1": "value1",
                        "col2": "value2"
                    },
                    "relationships": {
                        "rel1": "value3",
                        "rel2": "value4"
                    }
                },
                "links": {
                    "self": "/nar1/nar2/nar3/1"
                }
            })

            self.assertDictEqual(self.resource_helper.get(mock_requests).body,
                                 response.body)

    def test_patch(self):
        mock_requests = MagicMock()
        with patch('jsonapi_framework.handler.'
                   'japi_format_vals.assert_resource_object') \
            as assert_resource_object, \
                patch('jsonapi_framework.handler.'
                      'dal.query_resource') as query_resource, \
                patch('jsonapi_framework.handler.'
                      'dal.commit') as dal_commit, \
                patch('jsonapi_framework.handler.'
                      'get_sparse_fields') as get_sparse_fields, \
                patch('jsonapi_framework.handler.'
                      'ResourceHandler.link') as self_link, \
                patch('jsonapi_framework.handler.'
                      'ResourceHandler.after_patch') as after_patch:
            assert_resource_object.return_value = None
            query_resource.return_value = MagicMock()
            query_resource.return_value.apply_patch_dict.return_value = None
            query_resource.return_value.validate.return_value = None
            dal_commit.return_value = None
            get_sparse_fields.return_value = \
                ["col1", "col2", "rel1", "rel2"], \
                ["col1", "col2", "rel1_id", "rel2_id"]
            query_resource.return_value.serialize.return_value = \
                {
                    "type": "foo",
                    "id": "1",
                    "attributes": {
                        "col1": "value2"
                    },
                    "links": {
                        "self": "/nar1/nar2/nar3/1"
                    }
                }
            self_link.return_value = "/nar1/nar2/nar3/1"
            after_patch.return_value = None
            response = Response(status=200, headers=None, body={
                "data": {
                    "type": "foo",
                    "id": "1",
                    "attributes": {
                        "col1": "value2"
                    },
                    "links": {
                        "self": "/nar1/nar2/nar3/1"
                    }
                },
                "links": {
                    "self": "/nar1/nar2/nar3/1"
                }
            })
            self.assertDictEqual(
                self.resource_helper.patch(mock_requests).body, response.body)

    def test_delete(self):
        mock_requests = MagicMock()
        with patch('jsonapi_framework.handler.'
                   'dal.query_resource') as query_resource, \
                patch('jsonapi_framework.handler.'
                      'dal.commit') as dal_commit, \
                patch('jsonapi_framework.handler.'
                      'dal.delete') as dal_delete, \
                patch('jsonapi_framework.handler.'
                      'ResourceHandler.after_patch') as after_delete:
            query_resource.return_value = MagicMock()
            dal_commit.return_value = None
            dal_delete.return_value = None
            after_delete.return_value = None
            resp = Response(None, 204)
            self.assertEqual(
                self.resource_helper.delete(mock_requests).status, resp.status)


class CollectionHandlerTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        resource = MagicMock()
        cls.collection_helper = CollectionHandler
        cls.collection_helper.resource_class = resource

    def test_link(self):
        link_prefix = "/nar1/nar2"
        with patch('jsonapi_framework.handler.'
                   'link_for_collection') as link_for_collection:
            link_for_collection.return_value = "/nar1/nar2/nar3"
            self.assertEqual("/nar1/nar2/nar3",
                             self.collection_helper.link(link_prefix))

    def test_get(self):
        mock_requests = MagicMock()
        mock_requests.query_args = \
            werkzeug.MultiDict([('fields[foo]', 'col1'),
                                ('sort', '-rel1'),
                                ('filter[col1]', '%search_value1%'),
                                ('page[number]', '1'),
                                ('page[size]', '2')])
        with patch('jsonapi_framework.handler.'
                   'get_sparse_fields') as get_sparse_fields, \
                patch('jsonapi_framework.handler.'
                      'get_filter') as get_filter, \
                patch('jsonapi_framework.handler.'
                      'get_order_by_fields') as get_order_by_fields, \
                patch('jsonapi_framework.handler.'
                      'dal.query_collection') as query_collection, \
                patch('jsonapi_framework.handler.'
                      'dal.query_total_number_resources') as \
                query_total_number_resources, \
                patch('jsonapi_framework.handler.'
                      'CollectionHandler.link') as self_link, \
                patch('jsonapi_framework.handler.'
                      'NumberSize.from_request') as from_request:
            get_sparse_fields.return_value = ["col1"], \
                                             ["col1"]
            get_filter.return_value = \
                [{"field": "col1", "op": "like", "value": "%search_value1%"}]
            get_order_by_fields.return_value = ["-rel1_id"]
            resource1 = MagicMock()
            resource2 = MagicMock()
            query_collection.return_value = [resource1, resource2]
            resource1.serialize.return_value = {
                "type": "foo",
                "id": "1",
                "attributes": {
                    "col1": "value1_search_value1"
                },
                "links": {
                    "self": "/nar1/nar2/nar3/1"
                }
            }
            resource2.serialize.return_value = {
                "type": "foo",
                "id": "2",
                "attributes": {
                    "col1": "value1_search_value1"
                },
                "links": {
                    "self": "/nar1/nar2/nar3/2"
                }
            }
            query_total_number_resources.return_value = 2
            self_link.return_value = "/nar1/nar2/nar3"
            pagination = MagicMock()
            from_request.return_value = pagination
            pagination.offset = 0
            pagination.limit = 2
            pagination.json_links.return_value = {
                "first": "/nar1/nar2/nar3?"
                         "sort=-blob&"
                         "page%5Bnumber%5D=1&"
                         "page%5Bsize%5D=2&"
                         "fields%5Bfoo%5D=col1&"
                         "filter%5Bname%5D=%25train%25",
                "last": "/nar1/nar2/nar3?"
                         "sort=-blob&"
                         "page%5Bnumber%5D=1&"
                         "page%5Bsize%5D=2&"
                         "fields%5Bfoo%5D=col1&"
                         "filter%5Bname%5D=%25train%25",
                "self": "/nar1/nar2/nar3?"
                        "sort=-blob&"
                        "page%5Bnumber%5D=1&"
                        "page%5Bsize%5D=2&"
                        "fields%5Bfoo%5D=col1&"
                        "filter%5Bname%5D=%25train%25"
            }
            pagination.json_meta.return_value = {
                "total-pages": 1
            }

            response = Response(status=200, headers=None, body={
                "data": [
                    {
                        "type": "foo",
                        "id": "1",
                        "attributes": {
                            "col1": "value1_search_value1"
                        },
                        "links": {
                            "self": "/nar1/nar2/nar3/1"
                        }
                    },
                    {
                        "type": "foo",
                        "id": "2",
                        "attributes": {
                            "col1": "value1_search_value1"
                        },
                        "links": {
                            "self": "/nar1/nar2/nar3/2"
                        }
                    }
                ],
                "links": {
                    "first": "/nar1/nar2/nar3?"
                             "sort=-blob&"
                             "page%5Bnumber%5D=1&"
                             "page%5Bsize%5D=2&"
                             "fields%5Bfoo%5D=col1&"
                             "filter%5Bname%5D=%25train%25",
                    "last": "/nar1/nar2/nar3?"
                             "sort=-blob&"
                             "page%5Bnumber%5D=1&"
                             "page%5Bsize%5D=2&"
                             "fields%5Bfoo%5D=col1&"
                             "filter%5Bname%5D=%25train%25",
                    "self": "/nar1/nar2/nar3?"
                            "sort=-blob&"
                            "page%5Bnumber%5D=1&"
                            "page%5Bsize%5D=2&"
                            "fields%5Bfoo%5D=col1&"
                            "filter%5Bname%5D=%25train%25"
                },
                "meta": {
                    "total-pages": 1
                }
            })
            self.assertDictEqual(
                self.collection_helper.get(mock_requests).body, response.body)

    def test_post(self):
        mock_requests = MagicMock()
        with patch('jsonapi_framework.handler.'
                   'japi_format_vals.assert_resource_object') as \
                assert_resource_object, \
                patch('jsonapi_framework.handler.'
                      'CollectionHandler.before_post') as before_post, \
                patch('jsonapi_framework.handler.'
                      'dal.add') as dal_add, \
                patch('jsonapi_framework.handler.'
                      'dal.flush') as dal_flush, \
                patch('jsonapi_framework.handler.'
                      'link_for_resource') as link_for_resource, \
                patch('jsonapi_framework.handler.'
                      'get_sparse_fields') as get_sparse_fields, \
                patch('jsonapi_framework.handler.'
                      'dal.commit') as dal_commit, \
                patch('jsonapi_framework.handler.'
                      'CollectionHandler.after_post') as after_post, \
                patch('jsonapi_framework.handler.'
                      'CollectionHandler.resource_class.deserialize') as \
                deserialize:
            assert_resource_object.return_value = None
            before_post.return_value = None
            dal_add.return_value = None
            dal_flush.return_value = None
            link_for_resource.return_value = "/nar1/nar2/nar3/1"
            get_sparse_fields.return_value = ["col1"], \
                                             ["col1"]
            dal_commit.return_value = None
            after_post.return_value = None
            resource = MagicMock()
            deserialize.return_value = resource
            resource.validate.return_value = None
            resource.serialize.return_value = {
                "type": "foo",
                "id": "1",
                "attributes": {
                    "col1": "value1"
                },
                "links": {
                    "self": "/nar1/nar2/nar3/1"
                }
            }
            response = Response(status=201,
                                headers={"Location": "/nar1/nar2/nar3/1"},
                                body={
                                    "data": {
                                        "type": "foo",
                                        "id": "1",
                                        "attributes": {
                                            "col1": "value1"
                                        },
                                        "links": {
                                            "self": "/nar1/nar2/nar3/1"
                                        }
                                    },
                                    "links": {
                                        "self": "/nar1/nar2/nar3/1"
                                    }
                                })
            self.assertDictEqual(
                self.collection_helper.post(mock_requests).body,
                response.body
            )
            self.assertEqual(
                self.collection_helper.post(mock_requests).status,
                response.status
            )
            self.assertDictEqual(
                self.collection_helper.post(mock_requests).headers,
                response.headers
            )


class RelatedHandlerTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        resource = MagicMock()
        cls.related_helper = RelatedHandler
        cls.related_helper.resource_class = resource

    def test_link(self):
        link_prefix = "/nar1/nar2"
        id = "1"
        relationship = "foo"
        with patch('jsonapi_framework.handler.'
                   'link_for_related') as link_for_related:
            link_for_related.return_value = "/nar1/nar2/nar3/1/foo"
            self.assertEqual(self.related_helper.link(
                link_prefix, id, relationship),
                "/nar1/nar2/nar3/1/foo")

    def test_get(self):
        mock_requests = MagicMock()
        mock_requests.relationship = "foo"
        with patch('jsonapi_framework.handler.'
                   'get_sparse_fields') as get_sparse_fields, \
                patch('jsonapi_framework.handler.'
                      'dal.query_related') as dal_query_related, \
                patch('jsonapi_framework.handler.'
                      'RelatedHandler.link') as link:
            get_sparse_fields.return_value = ["col1"], \
                                             ["col1"]
            resource = MagicMock()
            dal_query_related.return_value = resource
            resource.serialize.return_value = {
                "type": "foo",
                "id": "1",
                "attributes": {
                    "col1": "value1"
                },
                "links": {
                    "self": "/nar1/nar2/nar3/1"
                }
            }
            link.return_value = "/nar1/nar2/nar3/1/foo"

            response = Response(body={
                "data": {
                    "type": "foo",
                    "id": "1",
                    "attributes": {
                        "col1": "value1"
                    },
                    "links": {
                        "self": "/nar1/nar2/nar3/1"
                    }
                },
                "links": {
                    "self": "/nar1/nar2/nar3/1/foo"
                }
            })
            self.assertDictEqual(
                self.related_helper.get(mock_requests).body,
                response.body
            )


class ToOneRelationshipHandlerTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        resource = MagicMock()
        rel = MagicMock()
        resource._rels_by_japi_name = {
            "foo": rel
        }
        cls.toOneRelation_helper = ToOneRelationshipHandler
        cls.toOneRelation_helper.resource_class = resource
        rel.serialize.return_value = {
            "data": {
                "id": "1",
                "type": "foo"
            },
            "links": {
                "related": "/nar1/nar2/nar3/1/foo",
                "self": "/nar1/nar2/nar3/1/relationships/foo"
            }
        }
        rel.deserialize_into_obj.return_value = None

    def test_get(self):
        mock_requests = MagicMock()
        mock_requests.relationship = "foo"
        with patch('jsonapi_framework.handler.dal.query_resource') as \
                query_resource:
            res = MagicMock()
            query_resource.return_value = res
            response = Response(body={
                "data": {
                    "id": "1",
                    "type": "foo"
                },
                "links": {
                    "related": "/nar1/nar2/nar3/1/foo",
                    "self": "/nar1/nar2/nar3/1/relationships/foo"
                }
            })
            self.assertDictEqual(
                self.toOneRelation_helper.get(mock_requests).body,
                response.body
            )

    def test_patch(self):
        mock_requests = MagicMock()
        mock_requests.relationship = "foo"
        with patch('jsonapi_framework.handler.'
                   'japi_format_vals.assert_to_one_relationship_object') \
                as assert_to_one_relationship_object, \
                patch('jsonapi_framework.handler.dal.'
                      'query_resource') as dal_query_resource, \
                patch('jsonapi_framework.handler.'
                      'dal.commit') as dal_commit, \
                patch('jsonapi_framework.handler.'
                      'ToOneRelationshipHandler.after_patch') as after_patch:
            assert_to_one_relationship_object.return_value = None
            res = MagicMock()
            dal_query_resource.return_value = res
            dal_commit.return_value = None
            after_patch.return_value = None
            resp = Response(None, 204)
            self.assertEqual(
                self.toOneRelation_helper.patch(mock_requests).body,
                resp.body
            )
            self.assertEqual(
                self.toOneRelation_helper.patch(mock_requests).status,
                resp.status
            )
