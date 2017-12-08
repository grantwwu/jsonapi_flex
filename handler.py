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
jsonapi_framework.handler
======================
Contains Handler classes, which currently
1. Use the DAL to query for resources
2. Perform business logic functions
3. Perform JSON API related formatting
"""
import logging

import jsonapi_framework.errors as errors
import jsonapi_framework.sqlalchemy_dal as dal
import jsonapi_framework.japi_format_validators as japi_format_vals
from jsonapi_framework.context import Context
from jsonapi_framework.response import Response
from jsonapi_framework.utilities import (link_for_resource,
                                         link_for_collection,
                                         link_for_related,
                                         get_sparse_fields,
                                         get_order_by_fields,
                                         get_filter)
from jsonapi_framework.pagination import NumberSize

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.INFO)


def handle(cls, request):
    """
    Calls the correct handler method (*get*, *patch*, ...) depending on
    HTTP

    :param Handler class cls: A handler class
    :param request request: The relevant request

    :returns Response: The response
    """
    if request.method == "get":
        return cls.get(request)
    elif request.method == "post":
        return cls.post(request)
    elif request.method == "patch":
        return cls.patch(request)
    elif request.method == "delete":
        return cls.delete(request)
    raise errors.MethodNotAllowed()


class ResourceHandler(object):
    @classmethod
    def link(cls, link_prefix, id):
        """
        Gets a link for the resource corresponding to this ResourceHandler

        :param str link_prefix: The link prefix to use
        :param str id: The id to use for the link

        :returns str: The link
        """
        return link_for_resource(
            link_prefix, cls.resource_class.japi_resource_url_component, id)

    @classmethod
    def before_patch(cls, old_resource, patch_dict):
        """
        This function is called before the a PATCH request is applied and
        validators are called.

        :param str old_resource: The resource about to be patched
        :param dict patch_dict: The patch dict to use for the patching
        """
        pass

    @classmethod
    def after_patch(cls, response, id):
        """
        This function is called right before the response to a PATCH request
        is returned.

        :param Response response: The response to return
        :param str id: The id of the resource that was patched
        """
        pass

    @classmethod
    def after_delete(cls, response, id):
        """
        This function is called right before the response to a DELETE request
        is returned.

        :param Response response: The response to return
        :param str id: The id of the resource that was deleted
        """
        pass

    @classmethod
    def get(cls, request):
        """
        Handle a GET request for a resource

        :param Request request: The request being handled

        :returns Response: Returns a response to the caller
        """
        args = request.query_args.items(multi=True)
        sparse_fields_to_return, sparse_fields_for_query = get_sparse_fields(
            args, cls.resource_class)
        resource = dal.query_resource(
            request.session, cls.resource_class,
            cls.resource_class.id.deserialize(request.id),
            sparse_fields_for_query)
        if resource is None:
            raise errors.NotFound()

        links = {"self": cls.link(request.link_prefix, request.id)}
        resp_doc = {
            "data": resource.serialize(
                link_prefix=request.link_prefix,
                fields=sparse_fields_to_return),
            "links": links
        }
        return Response(resp_doc)

    @classmethod
    def patch(cls, request):
        """
        Handle a PATCH request for a resource

        :param Request request: The request being handled

        :returns Response: Returns a response to the caller
        """
        try:
            if not request.body:
                raise errors.BadRequest(detail="Missing request body")
            patch_json = request.body["data"]
        except KeyError:
            raise errors.BadRequest(detail="Missing primary data object")
        japi_format_vals.assert_resource_object(patch_json,
                                                source_pointer="/data/")
        patch_dict = cls.resource_class.create_patch_dict(patch_json)
        resource = dal.query_resource(
            request.session, cls.resource_class,
            cls.resource_class.id.deserialize(request.id))
        if resource is None:
            raise errors.NotFound()

        cls.before_patch(resource, patch_dict)
        resource.apply_patch_dict(patch_dict)
        resource.validate(Context.UPDATE)

        args = request.query_args.items(multi=True)
        sparse_fields_to_return, _ = get_sparse_fields(
            args, cls.resource_class)
        links = {"self": cls.link(request.link_prefix, request.id)}
        resp_doc = {
            "data": resource.serialize(link_prefix=request.link_prefix,
                                       fields=sparse_fields_to_return),
            "links": links,
        }

        resp = Response(resp_doc)
        dal.commit(request.session)
        cls.after_patch(resp, cls.resource_class.id.deserialize(request.id))
        return resp

    @classmethod
    def delete(cls, request):
        """
        Handle a DELETE request for a resource

        :param Request request: The request being handled

        :returns Response: Returns a response to the caller
        """
        resource = dal.query_resource(
            request.session, cls.resource_class,
            cls.resource_class.id.deserialize(request.id))
        if resource is None:
            return errors.error_to_response(errors.NotFound())

        dal.delete(request.session, resource.model)
        dal.commit(request.session)
        resp = Response(None, 204)
        cls.after_delete(resp, cls.resource_class.id.deserialize(request.id))
        return resp


class CollectionHandler(object):
    @classmethod
    def link(cls, link_prefix):
        """
        Gets a link for the resource collection corresponding to this
        CollectionHandler

        :param str link_prefix: The link prefix to use

        :returns str: The link
        """
        return link_for_collection(
            link_prefix, cls.resource_class.japi_resource_url_component)

    @classmethod
    def before_post(cls, new_resource):
        """
        This function is called before the resource specified in a POST request
        is created

        :param str new_resource: The resource about to be created.
        """
        pass

    @classmethod
    def after_post(cls, response, id):
        """
        This function is called right before the response to a POST request
        is returned

        :param Response response: The response to return
        :param str id: The id of the new resource
        """
        pass

    @classmethod
    def get(cls, request):
        """
        Handle a GET request for a collection of resources

        :param Request request: The request being handled

        :returns Response: Returns a response to the caller
        """
        args = request.query_args.items(multi=True)
        sparse_fields_to_return, sparse_fields_for_query = get_sparse_fields(
            args, cls.resource_class)
        # args needs to get again because of generator problem.
        args = request.query_args.items(multi=True)
        filters = get_filter(args, cls.resource_class)
        args = request.query_args
        order_by = get_order_by_fields(args, cls.resource_class)
        total_number_resources = dal.query_total_number_resources(
            request.session, cls.resource_class)

        links = {"self": cls.link(request.link_prefix)}
        limit = None
        offset = None
        meta = {}
        if "page[size]" in args:
            pagination = NumberSize.from_request(
                request,
                cls.resource_class.japi_resource_url_component,
                total_number_resources
            )
            offset = pagination.offset
            limit = pagination.limit
            links = pagination.json_links()
            meta = pagination.json_meta()

        resources = dal.query_collection(
            request.session, cls.resource_class,
            sparse_fields_for_query, order_by, filters,
            limit=limit, offset=offset)

        resp_doc = {
            "data":
            [r.serialize(
                link_prefix=request.link_prefix, fields=sparse_fields_to_return
                ) for r in resources],
            "links": links,
        }
        if meta:
            resp_doc["meta"] = meta
        return Response(resp_doc)

    @classmethod
    def post(cls, request):
        """
        Handle a POST request to create a new resource

        :param Request request: The request being handled

        :returns Response: Returns a response to the caller
        """
        try:
            if not request.body:
                raise errors.BadRequest(detail="Missing request body")
            resource_dict = request.body["data"]
        except KeyError:
            raise errors.BadRequest(detail="Missing primary data object")
        japi_format_vals.assert_resource_object(
            resource_dict, id_required=False, source_pointer="/data/")
        new_resource = cls.resource_class.deserialize(resource_dict)
        cls.before_post(new_resource)
        new_resource.validate(Context.CREATE)
        dal.add(request.session, new_resource.model)
        dal.flush(request.session)
        link = link_for_resource(
            request.link_prefix,
            cls.resource_class.japi_resource_url_component, new_resource.id)
        links = {"self": link}
        args = request.query_args.items(multi=True)
        sparse_fields, _ = get_sparse_fields(args, cls.resource_class)
        resp_doc = {
            "data": new_resource.serialize(link_prefix=request.link_prefix,
                                           fields=sparse_fields),
            "links": links,
        }
        dal.commit(request.session)
        resp = Response(resp_doc, 201, {"Location": link})
        cls.after_post(resp, new_resource.id)
        return resp


class RelatedHandler(object):
    @classmethod
    def link(cls, link_prefix, id, relationship):
        """
        Gets a related resource link corresponding to this RelatedHandler

        :param str link_prefix: The link prefix to use
        :param str id: The id to use for the link

        :returns str: The link
        """
        return link_for_related(
            link_prefix, cls.resource_class.japi_resource_url_component, id,
            relationship)

    @classmethod
    def get(cls, request):
        """
        Handle a GET request for a related resource

        :param Request request: The request being handled

        :returns Response: Returns a response to the caller
        """
        args = request.query_args.items(multi=True)
        related_resource_class = getattr(
            cls.resource_class, request.relationship).related_resource_class
        sparse_fields_to_return, sparse_fields_for_query = get_sparse_fields(
            args, related_resource_class)
        related = dal.query_related(
            request.session, cls.resource_class,
            cls.resource_class.id.deserialize(request.id),
            request.relationship, sparse_fields_for_query)
        if related is None:
            raise errors.NotFound()
        links = {
            "self": cls.link(request.link_prefix, request.id,
                             request.relationship)
        }
        resp_doc = {
            "data": related.serialize(
                link_prefix=request.link_prefix,
                fields=sparse_fields_to_return),
            "links": links,
        }
        return Response(resp_doc)


class ToOneRelationshipHandler(object):
    @classmethod
    def after_patch(cls, response, id):
        """
        This function is called right before the response to a PATCH request
        is returned.

        :param Response response: The response to return
        :param str id: The id of the resource which had a relationship that
                       was patched
        """
        pass

    @classmethod
    def get(cls, request):
        """
        Handle a GET request for a relationship

        :param Request request: The request being handled

        :returns Response: Returns a response to the caller
        """
        resource = dal.query_resource(
            request.session, cls.resource_class,
            cls.resource_class.id.deserialize(request.id))
        rel = cls.resource_class._rels_by_japi_name[request.relationship]
        resource_linkage = rel.serialize(resource.model, request.id,
                                         request.link_prefix)
        return Response(resource_linkage)

    @classmethod
    def patch(cls, request):
        """
        Handle a PATCH request for a relationship

        :param Request request: The request being handled

        :returns Response: Returns a response to the caller
        """
        japi_format_vals.assert_to_one_relationship_object(request.body)
        resource = dal.query_resource(
            request.session, cls.resource_class,
            cls.resource_class.id.deserialize(request.id))
        rel = cls.resource_class._rels_by_japi_name[request.relationship]
        rel.deserialize_into_obj(resource.model, request.body)
        dal.commit(request.session)
        resp = Response(None, 204)
        cls.after_patch(resp, cls.resource_class.id.deserialize(request.id))
        return resp

    @classmethod
    def post(cls, request):
        # Posting is only for to-many relationships
        raise errors.MethodNotAllowed()

    @classmethod
    def delete(cls, request):
        # Deleting is only for to-many relationships
        raise errors.MethodNotAllowed()
