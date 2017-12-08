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
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
"""
jsonapi.base.validators
=======================

This module contains validators for the different JSON API document types. If
a request contains an invalid document, a validator detects the error source
and creates a verbose error with a *source-pointer*.

All validators only assert the correct document structure, e.g.: An identifier
object must contain an *id* and a *type* attribute. However, the validator
does not check if the type is correct or even exists.

.. seealso::

    *   http://jsonapi.org/format/#document-structure
    *   http://jsonapi.org/format/#errors
"""

from jsonapi_framework.errors import BadRequest


def assert_resource_object(d, id_required=True, source_pointer="/"):
    """
    Verifies that *d* is a JSONapi resource object, raising an exception if
    it is not.

    :seealso: http://jsonapi.org/format/#document-resource-objects

    :param d:
    :param boolean id_required: Whether or not the 'id' member is required.
                                It is not required when it represents a new
                                resource to be created on the server, where
                                client generated ids are not required.
    :param str source_pointer:

    :raises BadRequest:
    """
    if not isinstance(d, dict):
        raise BadRequest(
            detail="A resource object must be an object.",
            source_pointer=source_pointer)

    if not d.keys() <= {
            "id", "type", "attributes", "relationships", "links", "meta"}:
        raise BadRequest(
            detail="A resource object may only contain these members: "
                   "'id', 'type', 'attributes', 'relationships', 'links',"
                   "'meta'.",
            source_pointer=source_pointer)

    if "type" not in d:
        raise BadRequest(
            detail="The 'type' member is not present.",
            source_pointer=source_pointer)
    if not isinstance(d["type"], str):
        raise BadRequest(
            detail="The value of 'type' must be a string.",
            source_pointer=source_pointer + "type/")

    if id_required and "id" not in d:
        raise BadRequest(
            detail="The 'id' member is not present.",
            source_pointer=source_pointer)
    if "id" in d and not isinstance(d["id"], str):
        raise BadRequest(
            detail="The value 'id' must be a string.",
            source_pointer=source_pointer + "id/")

    if "attributes" in d:
        assert_attributes_object(d["attributes"],
                                 source_pointer + "attributes/")
    if "relationships" in d:
        assert_relationships_object(d["relationships"],
                                    source_pointer + "relationships/")
    if "links" in d:
        assert_links_object(d["links"], source_pointer + "links/")
    if "meta" in d:
        assert_meta_object(d["meta"], source_pointer + "meta/")


def assert_attributes_object(d, source_pointer="/"):
    """
    Asserts, that *d* is a JSONapi attributes object.

    :seealso: http://jsonapi.org/format/#document-resource-object-attributes

    :param d:
    :param str source_pointer:

    :raises BadRequest:
    """
    if not isinstance(d, dict):
        raise BadRequest(
            detail="An attributes object must be an object.",
            source_pointer=source_pointer)


def assert_relationships_object(d, source_pointer="/"):
    """
    Asserts, that *d* is a JSONapi relationships object.

    :seealso: http://jsonapi.org/format/#document-resource-object-relationships

    :param d:
    :param str source_pointer:

    :raises BadRequest:
    """
    if not isinstance(d, dict):
        raise BadRequest(
            detail="A relationships object must be an object.",
            source_pointer=source_pointer)

    for key, value in d.items():
        assert_relationship_object(value, source_pointer + key + "/")


def assert_relationship_object(d, source_pointer="/", to_many=False,
                               to_one=False):
    """
    Verifies that *d* is a relationship object.

    :seelso: http://jsonapi.org/format/#document-resource-object-relationships

    :param d:
    :param str source_pointer:
    :param boolean to_many: Check that it is a to_many relationship object:
    :param boolean to_one: Check that it is a to_one relationship object:

    :raises BadRequest:
    """
    if not isinstance(d, dict):
        raise BadRequest(
            detail="A relationship object must be an object",
            source_pointer=source_pointer)
    if not d:
        raise BadRequest(
            detail=("A relationship object must contain at least one of these "
                    "members: 'data', 'links', 'meta'."),
            source_pointer=source_pointer)
    if not d.keys() <= {"links", "data", "meta"}:
        raise BadRequest(
            detail=(
                "A relationship object may only contain the following"
                "members: 'links', 'data' and 'meta'."),
            source_pointer=source_pointer)

    if "links" in d:
        assert_links_object(d["links"], source_pointer + "links/")
    if "meta" in d:
        assert_meta_object(d["meta"], source_pointer + "meta/")
    if "data" in d:
        exception = None
        if to_one:
            try:
                assert_to_one_resource_linkage(
                    d["data"], source_pointer + "data/")
            except BadRequest as b:
                exception = b
        if to_many:
            try:
                assert_to_many_resource_linkage(
                    d["data"], source_pointer + "data/")
            except BadRequest as b:
                exception = b

        if exception:
            raise exception
    else:
        raise BadRequest(detail=("Missing data member"),
                         source_pointer=source_pointer)


def assert_to_one_relationship_object(d, source_pointer="/"):
    assert_relationship_object(d, source_pointer, to_one=True)


def assert_to_many_relationship_object(d, source_pointer="/"):
    assert_relationship_object(d, source_pointer, to_many=True)
    assert_to_many_resource_linkage(d["data"], source_pointer + "data/")


def assert_to_one_resource_linkage(d, source_pointer="/"):
    """
    Verifies that that *d* is a valid resource linkage for a to-one
    relationship, raising BadRequest if it is not.

    :seealso: http://jsonapi.org/format/#document-resource-object-linkage

    :param d:
    :param str source_pointer:

    :raises BadRequest:
    """
    if d is None:
        pass
    elif isinstance(d, dict):
        assert_resource_identifier_object(d, source_pointer)
    else:
        raise BadRequest(
            detail=(
                "A resource linkage for a to-one relationship must be 'None' "
                "or a resource identifier object."),
            source_pointer=source_pointer)


def assert_to_many_resource_linkage(d, source_pointer="/"):
    """
    Verifies that that *d* is a valid resource linkage for a to-many
    relationship, raising BadRequest if it is not.

    :seealso: http://jsonapi.org/format/#document-resource-object-linkage

    :param d:
    :param str source_pointer:

    :raises BadRequest:
    """
    if isinstance(d, list):
        for i, item in enumerate(d):
            assert_resource_identifier_object(item,
                                              source_pointer + str(i) + "/")
    else:
        raise BadRequest(
            detail=(
                "A resource linkage for a to-many relationship must be an "
                "empty list or an array of resource identifier objects."),
            source_pointer=source_pointer)


def assert_resource_identifier_object(d, source_pointer="/"):
    """
    Verifies that *d* is a resource identifier object, raising BadRequest if it
    is not.

    :seealso: http://jsonapi.org/format/#document-resource-identifier-objects

    :param d:
    :param str source_pointer:

    :raises BadRequest:
    """
    if not isinstance(d, dict):
        raise BadRequest(
            detail="A resource identifier object must be an object.",
            source_pointer=source_pointer)
    if not d.keys() <= {"id", "type", "meta"}:
        raise BadRequest(
            detail=(
                "A resource identifier object can only contain these members: "
                "'id', 'type', 'meta'."),
            source_pointer=source_pointer)

    if "meta" in d:
        assert_meta_object(d["meta"], source_pointer + "meta/")

    if "type" not in d:
        raise BadRequest(
            detail="The 'type' member is not present.",
            source_pointer=source_pointer)
    if not isinstance(d["type"], str):
        raise BadRequest(
            detail="The value of 'type' must be a string.",
            source_pointer=source_pointer + "type/")

    if "id" not in d:
        raise BadRequest(
            detail="The 'id' member is not present.",
            source_pointer=source_pointer)
    if not isinstance(d["id"], str):
        raise BadRequest(
            detail="The value of 'id' must be a string.",
            source_pointer=source_pointer + "id/")


def assert_links_object(d, source_pointer="/"):
    """
    Verifies that *d* is a JSON API links object, raising BadRequest if it is
    not.

    :seealso: http://jsonapi.org/format/#document-links

    :param d:
    :param str source_pointer:

    :raises BadRequest:
    """
    if not isinstance(d, dict):
        raise BadRequest(
            detail="A links object must be an object.",
            source_pointer=source_pointer)

    for key, value in d.items():
        assert_link(value, source_pointer + key + "/")


def assert_link(d, source_pointer="/"):
    """
    Verifies that *d* is a valid JSON API link, raising BadRequest if it is
    not.

    :seealso: http://jsonapi.org/format/#document-links

    :param d:
    :param str source_pointer:

    :raises BadRequest:
    """
    if isinstance(d, str):
        pass
    elif isinstance(d, dict):
        if not d:
            raise BadRequest(
                detail="A link object cannot be an empty object.",
                source_pointer=source_pointer)
        if not d.keys() <= {"href", "meta"}:
            raise BadRequest(
                detail="A link object can only contain these members: "
                       "'href', 'meta'.",
                source_pointer=source_pointer)
        if "href" in d and not isinstance(d["href"], str):
            raise BadRequest(
                detail="The value of 'href' must be a string.",
                source_pointer=source_pointer + "href/")
        if "meta" in d:
            assert_meta_object(d["meta"], source_pointer + "meta/")
    else:
        raise BadRequest(
            detail="A link object must be a string or an object.",
            source_pointer=source_pointer)


def assert_meta_object(d, source_pointer="/"):
    """
    Verifies that *d* is a valid meta object, raising BadRequest if it is not.

    :seealso: http://jsonapi.org/format/#document-meta

    :param d:
    :param str source_pointer:

    :raises BadRequest:
    """
    if not isinstance(d, dict):
        raise BadRequest(
            detail="A meta object must be an object.",
            source_pointer=source_pointer)
