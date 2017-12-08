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
jsonapi_framework.errors
==============

This module implements the base class for all JSON API exceptions:
http://jsonapi.org/format/#errors.

We also define frequently used HTTP errors and exceptions.

TODO: Some of the more interesting classes here aren't currently being used
when they could be used to better potential.
"""

import json
import traceback

from jsonapi_framework.response import Response


class Error(Exception):
    """
    :seealso: http://jsonapi.org/format/#errors

    This is the base class for all exceptions that we intend to throw (i.e.
    are not coding errors in the server code) as part of the API.
    """

    def __init__(self,
                 http_status=500,
                 id=None,
                 about="",
                 code=None,
                 title=None,
                 detail="",
                 source_parameter=None,
                 source_pointer=None,
                 meta=None):
        """
        :param int http_status:
            The HTTP status code applicable to this problem.
        :param str id:
            A unique identifier for this particular occurrence of the problem.
        :param str about:
            A link that leeds to further details about this particular
            occurrence of the problem.
        :param str code:
            An application specific error code, expressed as a string value.
        :param str title:
            A short, human-readable summay of the problem that SHOULD not
            change from occurrence to occurrence of the problem, except for
            purposes of localization. The default value is the class name.
        :param str detail:
            A human-readable explanation specific to this occurrence of the
            problem.
        :param source_pointer:
            A JSON Pointer [RFC6901] to the associated entity in the request
            document [e.g. `"/data"` for a primary data object, or
            `"/data/attributes/title"` for a specific attribute].
        :param str source_parameter:
            A string indicating which URI query parameter caused the error.
        :param dict meta:
            A meta object containing non-standard meta-information about the
            error.
        """
        self.http_status = http_status
        self.id = id
        self.about = about
        self.code = code
        self.title = title if title is not None else type(self).__name__
        self.detail = detail
        self.source_pointer = str(source_pointer)
        self.source_parameter = source_parameter
        self.meta = meta

    def __str__(self):
        """
        Returns the :attr:`detail` attribute by default.
        """
        return json.dumps(self.json, indent=4, sort_keys=True)

    @property
    def json(self):
        """
        The serialized version of this error.
        """
        d = {}
        if self.id is not None:
            d["id"] = str(self.id)
        d["status"] = self.http_status
        d["title"] = self.title
        if self.about:
            d["links"] = dict()
            d["links"]["about"] = self.about
        if self.code:
            d["code"] = self.code
        if self.detail:
            d["detail"] = self.detail
        if self.source_pointer or self.source_parameter:
            d["source"] = dict()
            if self.source_pointer:
                d["source"]["pointer"] = self.source_pointer
            if self.source_parameter:
                d["source"]["parameter"] = self.source_parameter
        if self.meta:
            d["meta"] = self.meta
        return d


class ErrorList(Exception):
    """
    Can be used to store a list of exceptions, which occur during the
    execution of a request.

    :seealso: http://jsonapi.org/format/#error-objects
    :seealso: http://jsonapi.org/examples/#error-objects-multiple-errors
    """

    def __init__(self, errors=None):
        """
        :param Error list errors: A list of errors to initialize this ErrorList
                                  with.
        """
        self.errors = []
        if errors:
            self.extend(errors)

    def __bool__(self):
        return bool(self.errors)

    def __len__(self):
        return len(self.errors)

    def __str__(self):
        return json.dumps(self.json, indent=4, sort_keys=True)

    @property
    def http_status(self):
        """
        The most specific http status code for the contained exceptions.
        """
        if not self.errors:
            return None
        elif all(err.http_status == self.errors[0].http_status
                 for err in self.errors):
            # If all errors are identical, return that error.
            return self.errors[0].http_status
        elif any(400 <= err.http_status < 500 for err in self.errors):
            return 400
        else:
            return 500

    def append(self, error):
        """
        Appends the :class:`Error` error to the error list.

        :param Error error:
        """
        if not isinstance(error, Error):
            raise TypeError("*error* must be of type Error")
        self.errors.append(error)

    def extend(self, errors):
        """
        Appends all errors in *errors* to the list. *errors* must be an
        :class:`ErrorList` or a sequence of :class:`Error`.

        :param errors:
        """
        if isinstance(errors, ErrorList):
            self.errors.extend(errors.errors)
        elif all(isinstance(err, Error) for err in errors):
            self.errors.extend(errors)
        else:
            raise TypeError(
                "*errors* must be of type ErrorList or a sequence of Error.")

    @property
    def json(self):
        """
        Creates the JSON API error object in resource dict representation (see
        resource.py).

        :seealso: http://jsonapi.org/format/#error-objects
        """
        return [error.json for error in self.errors]


def stacktrace_to_response(e):
    """
    Create a response consisting only of the plaintext stack trace
    for an exception.
    """
    body = "".join(traceback.format_exception(None, e, e.__traceback__))
    return Response(body, 500, {"Content-Type": "text/plain"})


def error_to_response(error):
    """
    Converts an :class:`Error` to a :class:`~jsonapi.Response`.

    :param Error error:
        The error, which is converted into a response.

    :rtype: jsonapi.request.Request
    """

    if isinstance(error, Error):
        body = {"errors": [error.json]}
    elif isinstance(error, ErrorList):
        body = {"errors": error.json}

    return Response(body=body, status=error.http_status)


# Common http errors
# ------------------

# 4xx errors
# ~~~~~~~~~~


class BadRequest(Error):
    def __init__(self, **kwargs):
        super().__init__(http_status=400, **kwargs)


class Unauthorized(Error):
    def __init__(self, **kwargs):
        super().__init__(http_status=401, **kwargs)


class Forbidden(Error):
    def __init__(self, **kwargs):
        super().__init__(http_status=403, **kwargs)


class NotFound(Error):
    def __init__(self, **kwargs):
        super().__init__(http_status=404, **kwargs)


class MethodNotAllowed(Error):
    def __init__(self, **kwargs):
        super().__init__(http_status=405, **kwargs)


class NotAcceptable(Error):
    def __init__(self, **kwargs):
        super().__init__(http_status=406, **kwargs)


class Conflict(Error):
    def __init__(self, **kwargs):
        super().__init__(http_status=409, **kwargs)


class Gone(Error):
    def __init__(self, **kwargs):
        super().__init__(http_status=410, **kwargs)


class PreConditionFailed(Error):
    def __init__(self, **kwargs):
        super().__init__(http_status=412, **kwargs)


class UnsupportedMediaType(Error):
    def __init__(self, **kwargs):
        super().__init__(http_status=415, **kwargs)


class UnprocessableEntity(Error):
    def __init__(self, **kwargs):
        super().__init__(http_status=422, **kwargs)


class Locked(Error):
    def __init__(self, **kwargs):
        super().__init__(http_status=423, **kwargs)


class FailedDependency(Error):
    def __init__(self, **kwargs):
        super().__init__(http_status=424, **kwargs)


class TooManyRequests(Error):
    def __init__(self, **kwargs):
        super().__init__(http_status=429, **kwargs)


# 5xx errors


class InternalServerError(Error):
    def __init__(self, **kwargs):
        super().__init__(http_status=500, **kwargs)


class NotImplemented(Error):
    def __init__(self, **kwargs):
        super().__init__(http_status=501, **kwargs)


class BadGateway(Error):
    def __init__(self, **kwargs):
        super().__init__(http_status=502, **kwargs)


class ServiceUnavailable(Error):
    def __init__(self, **kwargs):
        super().__init__(http_status=503, **kwargs)


class GatewayTimeout(Error):
    def __init__(self, **kwargs):
        super().__init__(http_status=504, **kwargs)


class VariantAlsoNegotiates(Error):
    def __init__(self, **kwargs):
        super().__init__(http_status=506, **kwargs)


class InsufficientStorage(Error):
    def __init__(self, **kwargs):
        super().__init__(http_status=507, **kwargs)


class NotExtended(Error):
    def __init__(self, **kwargs):
        super().__init__(http_status=510, **kwargs)


# Special JSON API errors

# TODO: We should use these errors

class ValidationError(BadRequest):
    """
    Raised if the structure of a JSON document in a request body is invalid.

    Please note, that this does not include semantic errors, like an unknown
    typename.

    This type of exception is used often in the :mod:`jsonapi.validator`
    and :mod:`jsonapi.validation` modules.

    :seealso: http://jsonapi.org/format/#document-structure
    """


class InvalidValue(ValidationError):
    """
    Raised if an input value (part of a JSON API document) has an invalid
    value.

    :seealso: http://jsonapi.org/format/#document-structure
    """


class InvalidType(ValidationError):
    """
    Raised if an input value (part of a JSON API document) has the wrong type.

    This type of exception is often raised during decoding.

    :seealso: http://jsonapi.org/format/#document-structure
    """


class MissingField(ValidationError):
    """
    Raised if a field is required but not part of the input data.

    TODO: We should actually use this, as well as

    :seealso: http://jsonapi.org/format/#document-structure
    """

    def __init__(self, type, field, **kwargs):
        kwargs.setdefault("detail", "The field '{}.{}' is required.".format(
            type, field))
        super().__init__(**kwargs)


class UnresolvableIncludePath(BadRequest):
    """
    Raised if an include path does not exist. The include path is part
    of the ``include`` query argument. (An include path is invalid, if a
    relationship mentioned in it is not defined on a resource).

    :seealso: http://jsonapi.org/format/#fetching-includes
    """

    def __init__(self, path, **kwargs):
        if not isinstance(path, str):
            path = ".".join(path)

        kwargs.setdefault("detail",
                          "The include path '{}' does not exist.".format(path))
        kwargs.setdefault("source_parameter", "include")
        super().__init__(**kwargs)


class UnsortableField(BadRequest):
    """
    If a field is used as sort key, but the field is not sortable.

    :seealso: http://jsonapi.org/format/#fetching-sorting
    """

    def __init__(self, type, field, **kwargs):
        kwargs.setdefault(
            "detail", "The field '{}.{}' can not be used for sorting.".format(
                type, field))
        kwargs.setdefault("source_parameter", "sort")
        super().__init__(**kwargs)


class UnsupportedFilter(BadRequest):
    """
    If a filter has been applied to a field which does not support that filter.

    :seealso: http://jsonapi.org/format/#fetching-filtering
    """

    def __init__(self, type, field, filtername, **kwargs):
        kwargs.setdefault(
            "detail",
            "The field '{}.{}' does not support the '{}' filter."
            .format(type, field, filtername)
        )
        kwargs.setdefault("source_parameter", "filter[{}]".format(field))
        super().__init__(**kwargs)


class ResourceNotFound(NotFound):
    """
    Raised if a resource does not exist.

    TODO: We should actually use this.
    """

    def __init__(self, type, id, **kwargs):
        kwargs.setdefault(
            "detail",
            "The resource (type='{}', id='{}') does not exist.".format(
                type, id))
        super().__init__(**kwargs)
