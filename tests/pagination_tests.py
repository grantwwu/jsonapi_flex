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
from jsonapi_framework.pagination import BasePagination


class BasePaginationTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        args = werkzeug.MultiDict([('page[size]', '2'),
                                   ('page[number]', '1')])
        cls.base_pagination = BasePagination("/nar1/nar2", "foo", args)

    def test_page_link(self):
        pagination = {"size": 2, "number": 1}
        with patch('jsonapi_framework.pagination.link_for_pagination') as \
                link_for_pagination:
            link_for_pagination.return_value = \
                "/nar1/nar2/foo?page%5Bnumber%5D=1&page%5Bsize%5D=2"
            self.assertEqual(
                self.base_pagination.page_link(pagination),
                "/nar1/nar2/foo?page%5Bnumber%5D=1&page%5Bsize%5D=2"
            )
