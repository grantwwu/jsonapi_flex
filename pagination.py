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
jsonapi_framework.pagination
======================

Contains Pagination classes, which currently performs
JSON API pagination function.
"""
import math
import urllib.parse

from jsonapi_framework.utilities import check_number, link_for_pagination


DEFAULT_LIMIT = 25


class BasePagination(object):
    """
    The base class for all pagination helpers.
    """

    def __init__(self, link_prefix, japi_resource_url_component, args):
        self._link_prefix = link_prefix
        self._japi_resource_url_component = japi_resource_url_component
        self._query = args.to_dict()
        return None

    @classmethod
    def from_request(cls, request, **kwargs):
        """
        Checks if the needed pagination parameters are present in the request
        and if so, a new pagination instance with these parameters is returned
        and *None* otherwise.
        """
        raise NotImplementedError()

    @property
    def link_prefix(self):
        return self._link_prefix

    def page_link(self, pagination):
        self._query.update({
            "page[{}]".format(key): str(value)
            for key, value in pagination.items()
        })
        query = urllib.parse.urlencode(self._query, doseq=True)

        link = link_for_pagination(self.link_prefix,
                                   self._japi_resource_url_component,
                                   query
                                   )
        return link

    def json_meta(self):
        """
        **Must be overridden.**
        A dictionary, which must be included in the top-level *meta object*.
        """
        return dict()

    def json_links(self):
        """
        **Must be overridden.**
        A dictionary, which must be included in the top-level *links object*.
        It contains these keys:
        *   *self*
            The link to the current page
        *   *first*
            The link to the first page
        *   *last*
            The link to the last page
        *   *prev*
            The link to the previous page (only set, if a previous page exists)
        *   *next*
            The link to the next page (only set, if a next page exists)
        """
        raise NotImplementedError()


class NumberSize(BasePagination):
    """
    Implements a pagination based on *number* and *size* values.
    eg:
        /Article/?sort=date_added&page[size]=5&page[number]=10
    """
    def __init__(self, link_prefix, japi_resource_url_component,
                 args, number, size, total_resources):
        """
        :param link_prefix: Link prefix.
        :param japi_resource_url_component: Name of the resources.
        :param args: The request arguments.
        :param number: The number of the current page.
        :param size: The number of resources on a page.
        :param total_resources:
        The total number of resources in the collection.
        """
        super().__init__(link_prefix,
                         japi_resource_url_component,
                         args
                         )
        assert number > 0
        assert size > 0
        assert total_resources >= 0

        self.number = number
        self.size = size
        self.total_resources = total_resources

    @classmethod
    def from_request(cls, request, japi_resource_url_component,
                     total_resources, default_size=DEFAULT_LIMIT):
        number = request.query_args.get('page[number]')
        number = check_number(number, 'page[number]')

        size = request.query_args.get('page[size]')
        size = check_number(size, 'page[size]')
        size = default_size if size == 0 else size
        return cls(request.link_prefix, japi_resource_url_component,
                   request.query_args, number, size, total_resources)

    @property
    def last_page(self):
        """
        The number of the last page.
        """
        return math.ceil(self.total_resources / self.size)

    @property
    def limit(self):
        """
        The limit, based on the page :attr:`size`.
        """
        return self.size

    @property
    def offset(self):
        """
        The offset, based on the page :attr:`size` and :attr:`number`.
        """
        return (self.number - 1) * self.size

    def json_links(self):
        d = dict()
        pagination = {"size": self.size}
        d["self"] = self.page_link(
            dict(pagination, **{"number": self.number})
        )
        d["first"] = self.page_link(
            dict(pagination, **{"number": 1})
        )
        d["last"] = self.page_link(
            dict(pagination, **{"number": self.last_page})
        )
        if self.number > 1:
            d["prev"] = self.page_link(
                dict(pagination, **{"number": self.number - 1})
            )
        if self.number < self.last_page:
            d['next'] = self.page_link(
                dict(pagination, **{"number": self.number + 1})
            )
        return d

    def json_meta(self):
        """
        Returns a dictionary.
        """
        d = dict()
        d["total-pages"] = self.last_page
        return d
