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
jsonapi_framework.flask_api
===========
This is an API adapter between Flask and this JSON API framework.



"""
import logging

from flask import request as flask_request
from flask import make_response as flask_make_response
import sqlalchemy.exc
import sqlalchemy_filters

import jsonapi_framework.utilities as utilities
import jsonapi_framework.errors as errors
import jsonapi_framework.sqlalchemy_dal as dal
from jsonapi_framework.request import Request, RequestType
from jsonapi_framework.debug import DEBUG
from jsonapi_framework.handler import handle


LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG if DEBUG else logging.INFO)


class FlaskAPI(object):
    """
    This class:
        * Constructs request objects
        * Looks up the proper handler(s) from the Router and invokes it with
          the constructed Request object
        * Adds the jsonapi object to the response
        * Serializes the returned Response into JSON and returns it
    """

    def __init__(self, handler_map, flask, session_callable, api_prefix="",
                 proxy_prefix="", hostname=""):
        """
        :param dict handler_map: Map of resource types to request type maps:
        :param Flask flask: Flask object
        :param callable session_callable: Object called when we want a session
        :param str api_prefix:
            The prefix before the JSON API paths.
        :param str proxy_prefix:
            An extra prefix that goes before the api_prefix, in case you are
            behind a reverse proxy that strips URL segments
        :param str hostname:
            Hostname for the api.  Leave blank for relative links (default)
            TODO: Support automatic detection from request
        """
        self.handler_map = handler_map
        self.session_callable = session_callable
        self.api_prefix = api_prefix
        self.proxy_prefix = proxy_prefix
        self.hostname = hostname

        # Passing self.foo_request works because passing a bound method
        # actually closes over self, as if the function was partially applied
        # to self at the time that it's referenced
        # In less theoretical terms, the method remembers which instance it's
        # bound to.
        # This might be useful: (ignore unbound methods, as the answer mentions
        # there is no distinction between unbound methods and plain functions
        # in Python 3)
        # https://stackoverflow.com/questions/11949808/what-is-the-difference-between-a-function-an-unbound-method-and-a-bound-method

        # Rule for resource request

        flask.add_url_rule(
            api_prefix + "/<string:japi_resource_url_component>/<string:id>",
            view_func=self.resource_request,
            methods=['GET', 'DELETE', 'PATCH'])
        # Rule for collection request
        flask.add_url_rule(
            api_prefix + "/<string:japi_resource_url_component>",
            view_func=self.collection_request, methods=['GET', 'POST'])
        # Rule for related resource request
        flask.add_url_rule(
            api_prefix +
            "/<string:japi_resource_url_component>/"
            "<string:id>/<string:relationship>",
            view_func=self.related_request, methods=['GET'])
        # Rule for relationship request
        flask.add_url_rule(
            api_prefix + "/<string:japi_resource_url_component>/<string:id>"
            "/relationships/<string:relationship>",
            view_func=self.relationship_request,
            methods=['GET', 'POST', 'DELETE', 'PATCH'])

    def handle_request(self, japi_resource_url_component, request_type,
                       id=None, relationship=None):
        """
        The routing logic is arranged in this unnatural manner (a bunch of
        functions that act as proxies for handle_request) because we want to
        take advantage of Flask's provided parsing logic (which is really
        provided by Werkzeug...)
        """
        LOG.info(" " * 80)
        LOG.info("=" * 80)
        LOG.info("Received %s request at %s with resource url component: %s "
                 "and request type: %s", flask_request.method,
                 flask_request.url, japi_resource_url_component, request_type)
        LOG.debug("Flask headers: {}".format(flask_request.headers).strip())
        LOG.debug("Flask data (fallback): %.1000s", flask_request.data)
        session = self.session_callable()
        try:
            try:
                r_json = flask_request.get_json()
            except Exception:
                raise errors.BadRequest(detail="JSON body parse error")
            request = Request(
                request_type,
                flask_request.args,
                flask_request.method,
                self.hostname + self.proxy_prefix + self.api_prefix,
                session,
                flask_request.headers,
                r_json,
                id=id,
                relationship=relationship)
            try:
                resource_map = self.handler_map[japi_resource_url_component]
                if (request_type == RequestType.RELATIONSHIP or
                        request_type == RequestType.RELATED):
                    rel_handler_map = resource_map[request_type]
                    handler = rel_handler_map[relationship]
                else:
                    handler = resource_map[request_type]
            except KeyError:
                raise errors.NotFound()

            # If user expects something odd, handle the request accordingly
            # NOTE: Right now we don't respect the accept header order i.e. if
            # it indicates that both a JSON API and text/plain response
            # are acceptable in the Accept header, we send the JSON API
            # response.
            # If we end up supporting more MIME types we probably want to do
            # something more intelligent here.  But since text/plain support
            # is just a hack right now...
            if ("application/vnd.api+json" in flask_request.accept_mimetypes
                    or not flask_request.accept_mimetypes):
                response = handle(handler, request)
            elif "text/plain" in flask_request.accept_mimetypes:
                try:
                    response = handler.get_plain_text(request)
                except AttributeError:
                    raise errors.NotAcceptable()
            else:
                raise errors.NotAcceptable()
        except (errors.Error, errors.ErrorList) as err:
            dal.rollback(session)
            response = errors.error_to_response(err)
        except sqlalchemy.exc.IntegrityError as err:
            dal.rollback(session)
            LOG.error("handle_request caught a database exception error",
                      exc_info=True)
            response = errors.error_to_response(
                errors.BadRequest(detail="Database integrity exception. Check "
                                         "that your request does not break "
                                         "database invariants."))
        except (sqlalchemy.exc.ArgumentError,
                sqlalchemy.exc.ProgrammingError,
                sqlalchemy_filters.exceptions.FieldNotFound) as err:
            dal.rollback(session)
            LOG.error("handle_request caught a database exception error",
                      exc_info=True)
            response = errors.error_to_response(
                errors.BadRequest(
                    detail="The table doesn't have the column(s)."))
        except sqlalchemy.exc.DataError as err:
            dal.rollback(session)
            LOG.error("handle_request caught a database exception error",
                      exc_info=True)
            response = errors.error_to_response(
                errors.BadRequest(
                    detail="Wrong value."))
        except Exception as err:
            dal.rollback(session)
            LOG.error("handle_request caught an exception", exc_info=True)
            if DEBUG:
                response = errors.stacktrace_to_response(err)
            else:
                response = errors.error_to_response(
                    errors.InternalServerError())
        finally:
            session.remove()
        return self.response_to_flask_response(response)

    def response_to_flask_response(self, response):
        if "Content-Type" not in response.headers:
            response.headers["Content-Type"] = "application/vnd.api+json"
            if response.body is None:
                body = ""
            else:
                body = utilities.dump_json(response.body)
        else:
            body = response.body
        return flask_make_response((body, response.status,
                                    response.headers))

    def resource_request(self, japi_resource_url_component=None, id=None):
        return self.handle_request(japi_resource_url_component,
                                   RequestType.RESOURCE, id=id)

    def collection_request(self, japi_resource_url_component=None):
        return self.handle_request(japi_resource_url_component,
                                   RequestType.COLLECTION)

    def related_request(self, japi_resource_url_component=None, id=None,
                        relationship=None):
        return self.handle_request(japi_resource_url_component,
                                   RequestType.RELATED, id=id,
                                   relationship=relationship)

    def relationship_request(self, japi_resource_url_component=None, id=None,
                             relationship=None):
        return self.handle_request(japi_resource_url_component,
                                   RequestType.RELATIONSHIP,
                                   id=id, relationship=relationship)
