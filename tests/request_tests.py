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

from jsonapi_framework.request import Request


class RequestTestCase(unittest.TestCase):
    def test_init(self):
        request_type = 'RequestType.FOO'
        query_args = {}
        method = 'GET'
        link_prefix = '/nar1/nar2'
        session = None
        headers = {}
        body = {}
        request = Request(request_type, query_args, method,
                          link_prefix, session, headers, body, id=None,
                          relationship=None)
        self.assertEqual(Request('RequestType.FOO', {}, 'GET',
                                 '/nar1/nar2', None, {}, {}).request_type,
                         request.request_type)
        self.assertEqual(Request('RequestType.FOO', {}, 'GET',
                                 '/nar1/nar2', None, {}, {}).query_args,
                         request.query_args)
        self.assertEqual(Request('RequestType.FOO', {}, 'GET',
                                 '/nar1/nar2', None, {}, {}).method,
                         request.method)
        self.assertEqual(Request('RequestType.FOO', {}, 'GET',
                                 '/nar1/nar2', None, {}, {}).link_prefix,
                         request.link_prefix)
        self.assertEqual(Request('RequestType.FOO', {}, 'GET',
                                 '/nar1/nar2', None, {}, {}).session,
                         request.session)
        self.assertEqual(Request('RequestType.FOO', {}, 'GET',
                                 '/nar1/nar2', None, {}, {}).headers,
                         request.headers)
        self.assertEqual(Request('RequestType.FOO', {}, 'GET',
                                 '/nar1/nar2', None, {}, {}).body,
                         request.body)
