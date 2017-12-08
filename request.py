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
jsonapi.request
===============
TODO

"""

# std
from enum import Enum, auto

# TODO: Documentation
# TODO: Make immutable with properties


class RequestType(Enum):
    RESOURCE = auto()
    COLLECTION = auto()
    RELATED = auto()
    RELATIONSHIP = auto()


class Request(object):
    """
    Describes a JSON API request.
    """

    def __init__(self, request_type, query_args, method,
                 link_prefix, session, headers, body, id=None,
                 relationship=None):
        """
        :param RequestType request_type: What kind of request it is
        :param dict query_args: Query string arguments
        :param str method: HTTP method used
        :param str link_prefix:
            What to prepend to JSON API paths when making links
        :param str session:
            Session object to pass to the DAL
        :param dict headers: HTTP headers
        :param dict body: Parsed JSON request body
        :param dict id: The id
        :param str relationship:
        """
        self.request_type = request_type
        self.query_args = query_args
        self.method = method.lower()
        self.link_prefix = link_prefix
        self.session = session
        # TODO: throw error if header does not match
        self.headers = headers
        self.body = body
        self.id = id
        self.relationship = relationship
