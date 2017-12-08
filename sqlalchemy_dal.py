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
jsonapi_framework.sqlalchemy_dal
=================

This module is the data access layer. The interface between database and the
api.
"""
from sqlalchemy.orm import load_only
from sqlalchemy_filters import apply_filters

from jsonapi_framework import errors


# NOTE: Simplifying assumption... id is a single primary key
def query_resource(session, resource_class, id, fields=None):
    pk_column = getattr(resource_class.model_class,
                        resource_class.id.mapped_pk_name)
    if fields:
        model = session.query(resource_class.model_class).options(
            load_only(*fields)).filter(pk_column == id).one_or_none()
    else:
        model = session.query(resource_class.model_class).filter(
            pk_column == id).one_or_none()
    return resource_class(model) if model else None


def query_collection(session, resource_class, fields=None,
                     order_by=None, filters=None, limit=None, offset=None):
    if fields:
        models = session.query(
            resource_class.model_class).options(load_only(*fields))
    else:
        models = session.query(resource_class.model_class)
    if order_by:
        order_by = [order_field if order_field[0] != '-' else
                    order_field[1:] + ' desc' for order_field in order_by]
        models = models.order_by(*order_by)
    if filters:
        models = apply_filters(models, filters)
    if offset is not None and limit is not None:
        models = models.offset(offset).limit(limit)
    return (resource_class(model) for model in models)


def query_total_number_resources(session, resource_class):
    return session.query(resource_class.model_class).count()


def query_related(session, resource_class, id, relationship_name, fields=None):
    # TODO: This is currently emitting two queries.  It would be more
    # performant to use a database join (with SQLAlchemy).
    this_resource = query_resource(session, resource_class, id)
    if this_resource is None:
        raise errors.NotFound()
    related_model_fk = getattr(this_resource, relationship_name)
    if related_model_fk is None:
        return None
    else:
        related_resource_class = getattr(
            resource_class, relationship_name).related_resource_class
        return query_resource(session, related_resource_class,
                              related_model_fk, fields)


def commit(session, *args, **kwargs):
    session.commit(*args, **kwargs)


def rollback(session, *args, **kwargs):
    session.rollback(*args, **kwargs)


def add(session, *args, **kwargs):
    session.add(*args, **kwargs)


def flush(session, *args, **kwargs):
    session.flush(*args, **kwargs)


def delete(session, *args, **kwargs):
    session.delete(*args, **kwargs)
