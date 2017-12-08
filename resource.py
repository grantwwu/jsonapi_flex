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
jsonapi_framework.base_fields
==========================
This file contains several tightly coupled classes.

* BaseField - base class for JSON API fields
    * Attribute - class for JSON API attributes
    * Relationship - class for JSON API relationships
        * ToOneRelationship - class for relationships that are to-one,
                              i.e. there is a FK present on the
                              corresponding ORM mapped class
    * Id - special class for the id special JSON API field
* ResourceMeta - metaclass for Resource
* Resource - class representing resources

Note on serialization/deserialization and representation formats:

Representations:
    - JSON: Python data type is str.  String representation of pure JSON.
    - Resource dict: Output of json.loads (or utilities.load_json).
        Composed of dicts, lists, strings, numbers, etc.  Should be a very
        faithful representation of the JSON.
    - Resource object: An instance of the Resource class.  The most "fully"
        deserialized form, with the most structure.  Fields should be
        represented in this format with the most convenient type.
    - Patch dict: A python dictionary containing an attributes dictionary and a
        relationship dictionary.  This is essentially only used during PATCH
        requests, as a cheap way to represent the "diff".  We don't directly
        use Resource objects because they don't semantically represent diffs
        and because we want to avoid issues with validation - a valid diff may
        not update every required field, for example.  Fields are in their
        most convenient type.

Field representations:
    - Primitive value: Dict, list, string, number, etc.  Something with a
                       direct JSON analogue.  For relationships, this is a
                       dict analogue of a resource identifier object.
    - Most convenient type:  The most convenient type to represent a field. For
        example, timestamps might be DateTimes, UUIDs might be UUID objects,
        etc. Since we currently only support to-one relationships, the
        relationships are represented directly using whatever SQLAlchemy uses
        for foreign keys.


Resource object level (de)serialization functions:
    - deserialize: Python primitives -> resource_object (constructs new)
    - create_patch_dict: Resource dict -> patch dict
    - apply_patch_dict: patch dict + Resource object -> resource object
                             (applies the patch dict)
    - serialize: Resource object -> Python primitives

Field level (de)serialization functions:
    - serialize: Most convenient type -> Python primitive
    - deserialize: Python primitive -> Most convenient type
    - deserialize_into_obj:
        Python primitive + Resource object ->
            Most convenient type (Writes into the Resource object)

Functions that work with JSON (see utilities.py)
    - dump_json: python primitives -> JSON
    - load_json: JSON -> python primitive
"""
import copy
import itertools
import logging

import jsonapi_framework.errors as errors
from jsonapi_framework.utilities import (link_for_resource, link_for_related,
                                         link_for_relationship)
from jsonapi_framework.context import ALWAYS_SET, Context
from six import with_metaclass

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.INFO)


class BaseField(object):
    """
    The base class for all fields defined on a resource.
    Fields are either attributes or relationships, or the special cased id.
    Fields are property like descriptors - they follow the descriptor
    protocol.  They proxy reads and writes to the backing model instance.

    Skimming https://docs.python.org/3/howto/descriptor.html, particularly the
    property section, may be helpful.  Parts of this implementation are
    modeled on the example pure Python implementation of properties.

    Why didn't we use properties?  Properties do not interact very well with
    inheritance because they, just like all descriptors, are class variables
    under the hood.  This means that if you wish to modify them you need to
    replace them wholesale with a new property in the child class; mutating
    them is unacceptable because the behavior change will be reflected in the
    parent class and sibling classes.

    The way I worked around this is by having __get__ and __set__ proxy to
    self._fget and self._fset, which are just normal instance methods that can
    be overriden.  Note that they take in database model objects - _fget and
    _fset operate directly on the entire model for extra flexibility.  Suppose
    you had a JSON API field which was the sum of two database columns - you'd
    need the entire model.

    Note that in general, validators are never automatically called by any of
    the non-validation related functions in this file, including the
    deserialization functions.  This is for maximum flexibility in case of API
    changes or the need to perform some odd business logic related
    functionality.  If this were inflexible, we would need to break in the
    face of change (aka, in problematic corner cases, API clients would
    end up removing validators altogether, which is probably undesirable).

    .. hint::

        The inheritance of fields is currently implemented using the
        :func:`~copy.deepcopy` function from the standard library.

        Therefore, if you have a field which cannot be deepcopied using the
        default deepcopy implementation in a way that does not cause state
        to be improperly shared between Resource classes using instances of
        the BaseField subclass, or which otherwise does not work properly, you
        may need to implement a custom :meth:`__deepcopy__` method when you
        subclass :class:`BaseField`.

        TODO: use seealso
        (Refer to the implementation of ResourceMeta)
    """

    def __init__(self,
                 writable_during=ALWAYS_SET,
                 nullable=False,
                 has_default=False,
                 fget=None,
                 fset=None,
                 fvalidators=[]):
        """
            :param Context set writable_during:
                Describes when the field is writable.
            :param boolean nullable:
                Describes whether the field can be nullable.
            :param boolean has_default:
                If the field is nullable, describes whether the field has a
                non-null default.
                If the field is non-nullable, describes whether the field has
                a default value or not (and is therefore required to be
                provided during creation).
            :param callable fget:
                A function which returns the current value of the resource's
                attribute:
                ``fget(model)``.
            :param callable fset:
                A function which updates the current value of the resource's
                attribute:
                ``fset(model, new_value)``.
            :param callable list fvalidators:
                functions which validate the current value of the resource's
                attribute:
                ``fvalidate(model, context)``.
        """
        # If name is None, it'll be set later in the metaclass
        self.writable_during = writable_during
        self.nullable = nullable
        self.has_default = has_default

        if fget and not fset:
            # fset not supplied means that it cannot be writeable at all
            assert not self.writable_during

            # poison setter
            def fset(model, value):
                raise AttributeError("No setter provided")

        self._fget = fget
        self._fset = fset

        self._fvalidators = fvalidators

    def __get__(self, instance, owner):
        """
        Implements the descriptor protocol:
            https://docs.python.org/3/howto/descriptor.html
        """
        # If accessing through class, return the property object
        # (useful for validators)
        if instance is None:
            return self
        else:
            return self._fget(instance.model)

    def __set__(self, instance, value):
        """
        Implements the descriptor protocol:
            https://docs.python.org/3/howto/descriptor.html
        """
        if instance is None:
            raise AttributeError("Can't set class property")
        else:
            self._fset(instance.model, value)

    def validate(self, model, context):
        """
        The intended API of this function is for it to return None (implictly)
        if the validation passes.  Otherwise, one of the validators should
        throw an exception.

        :param Model model: The model instance backing store that we should use
                            to get the values to validate.
        :param Context context: The context in which we are validating.
                                Validators can specify which context they are
                                validating in.
        """
        for validator in self._fvalidators:
            if context in validator.contexts:
                validator(self, model)

    def serialize(self, model):
        """
        Return a representation that can be converted into a JSON value.

        :param Model model: The model instance backing store for we should use
                            to get the values to serialize.
        """
        raise NotImplementedError()

    def deserialize(self, prim_value):
        """
        Take a JSON value and convert it into a form suitable for directly
        passing to self._fset (most convenient type).
        """
        raise NotImplementedError()

    def deserialize_into_obj(self, model, prim_value):
        """
        Take a JSON value and assign a deserialized form (most convenient type)
        to the associated model instance.
        """
        raise NotImplementedError()


class Attribute(BaseField):
    """
    Attribute class representing attributes that map directly to a column in
    the database table.

    .. seealso::

        http://jsonapi.org/format/#document-resource-object-attributes

    """

    def __init__(self, mapped_attribute_name=None, japi_name=None,
                 **kwargs):
        """
        Create an Attribute object.

        :param str mapped_attribute_name: Name of the column on the database
                                          model to which this attribute is
                                          mapped.
        :param str japi_name: Name of the attribute in the JSON API schema.
                              Normally unnecessary - ResourceMeta will set it
                              equal to the class variable name.
        """
        super().__init__(**kwargs)

        self.mapped_attribute_name = mapped_attribute_name
        self.japi_name = japi_name

    def serialize(self, model):
        """
        No-op serialization.

        :param Model model: The model instance backing store that we should use
                            to get the value to serialize.

        :returns: The serialized value
        """
        return self._fget(model)

    def deserialize(self, prim_value):
        """
        No-op deserialization.

        :param prim_value: Whatever primitive value we want to deserialize.

        :returns: Deserialized value.
        """
        return prim_value

    def deserialize_into_obj(self, model, prim_value):
        """
        No-op deserialization.

        :param prim_value: Whatever primitive value we want to deserialize and
                           write into the backing model.

        :returns: Deserialized value.
        """
        self._fset(model, self.deserialize(prim_value))


class Relationship(BaseField):
    """
    .. seealso::

        http://jsonapi.org/format/#document-resource-object-relationships
    """

    def __init__(self, related_resource_class, japi_name=None, **kwargs):
        """
        Create a Relationship object.

        :param Resource subclass related_resource_class:
            A resource class that represents the resource at the other end of
            this relationship
        :param str japi_name: Name of the relationship in the JSON API schema.
                              Normally unnecessary - ResourceMeta will set it
                              equal to the class variable name.
        """
        self.related_resource_class = related_resource_class

        self.japi_name = japi_name

        super().__init__(**kwargs)

    def relationship_link(self, link_prefix, id):
        """
        Create a link representing this relationship.  This is defined here
        instead of in the handler because it's used in the serialization.

        :param str link_prefix: The link prefix to use
        :param str id: The id to use for the link

        :returns str: The relationship link
        """
        return link_for_relationship(
            link_prefix, self.bound_resource_class.japi_resource_url_component,
            id, self.japi_name)

    def related_link(self, link_prefix, id):
        """
        Create a related resource link.  This is defined here instead of in the
        handler because it's used in the serialization.

        :param str link_prefix: The link prefix to use
        :param str id: The id to use for the link

        :returns str: The related resource link
        """
        return link_for_related(
            link_prefix, self.bound_resource_class.japi_resource_url_component,
            id, self.japi_name)


class ToOneRelationship(Relationship):
    """
    Class for relationships that are to-one or to-one-or-none, i.e. there is a
    FK present on the corresponding table

    NOTE: This class assumes that the foreign keys are integers
    """

    def __init__(self, mapped_fk_name, related_resource_class, japi_name=None,
                 **kwargs):
        """
        Create a ToOneRelationship object.

        :param str mapped_fk_name: Name of the corresponding foreign key on the
                                   database schema to use for determining the
                                   related resource.
        :param Resource class related_resource_class:
            Class that represents the resource that this relationship points
            to.
        :param str japi_name: Name of the relationship in the JSON API schema.
                              Normally unnecessary - ResourceMeta will set it
                              equal to the class variable name.
        """
        # Call __init__ first to create _fset and _fget
        super().__init__(related_resource_class, **kwargs)
        self.mapped_fk_name = mapped_fk_name
        if self._fget:
            assert not mapped_fk_name
        else:
            assert self._fset is None

            # Neither fget nor fset were provided, use getattr and
            # setattr as defaults
            def fget(model, _hack=mapped_fk_name):
                # Default arg is a hack to deal with late binding
                return getattr(model, _hack)
            self._fget = fget

            if self.writable_during:
                def fset(model, value, _hack=mapped_fk_name):
                    setattr(model, _hack, value)
            # Use a poisoned setter if it is not configured to be
            # writable
            else:
                def fset(model, value):
                    raise AttributeError("No setter provided")
            self._fset = fset

    def serialize(self, model, resource_id, link_prefix):
        """
        No-op serialize (put the foreign key directly into the resource
        identifier object)

        :param Model model: The model instance backing store that we should use
                            to get the value to serialize.
        :param str resource_id: The id of the resource from which the
                                relationship points (i.e. not the related
                                resource).
        :param str link_prefix: The link prefix to use.

        :returns dict: Serialized form of this resource linkage.
        """
        related_resource_id = self._fget(model)
        if related_resource_id is None:
            data = None
        else:
            data = {
                "type": self.related_resource_class.japi_resource_type,
                "id": str(related_resource_id)
            }
        return {
            "links": {
                "self": self.relationship_link(link_prefix, resource_id),
                "related": self.related_link(link_prefix, resource_id)
            },
            "data": data
        }

    def deserialize(self, value):
        """
        No-op deserialize (directly extract the id from the resource linkage)

        :param dict value: The resource linkage we are deserializing

        :returns: Deserialized value
        """
        data = value["data"]
        if data is None:
            return None
        else:
            if data["type"] != self.related_resource_class.japi_resource_type:
                raise errors.BadRequest(
                    detail="Relationship type doesn't match definition")
            return int(data["id"])

    def deserialize_into_obj(self, model, value):
        """
        No-op deserialize (write foreign key directly into the database model)

        :param Model model: The model into which we should write the foreign
                            key
        :param dict value: The resource linkage we are deserializing
        """
        self._fset(model, self.deserialize(value))


class Id(BaseField):
    """
    Represents a JSON API id.  This implementation assumes a single integer
    primary key, auto-incrementing by default.
    """
    def __init__(self, mapped_pk_name=None, has_default=True, **kwargs):
        """
        :param str mapped_pk_name: The integer primary key on the database
                                   model that the Id maps directly to.
        :param bool has_default: This is True by default to support the common
                                 case of auto-incrementing primary keys.
        """
        super().__init__(has_default=has_default, **kwargs)

        self.mapped_pk_name = mapped_pk_name

    def serialize(self, model):
        """
        No-op serialization (turn the integer key directly into a string)

        :param Model model: The backing model instance to get the id from

        :returns str: Serialized form of the id
        """
        return str(self._fget(model))

    def deserialize(self, value):
        """
        No-op deserialization (turn the string ID directly into an integer)

        :param str value: The Id we are deserializing

        :returns int: Deserialized id
        """
        try:
            return int(value)
        except ValueError:
            raise errors.BadRequest(
                detail="Could not parse {} as integer.".format(value))

    def deserialize_into_obj(self, model, value):
        """
        No-op deserialization (write the string ID directly into the backing
        model instance as an integer)

        :param Model model: The backing model instance
        :param str value: The Id we are deserializing
        """
        self._fset(model, self.deserialize(value))


class ResourceMeta(type):
    def __init__(cls, name, bases, attrs):  # noqa: N805
        """
        This is a metaclass.  The below are decent sources:
        http://eli.thegreenplace.net/2011/08/14/python-metaclasses-by-example
        https://blog.ionelmc.ro/2015/02/09/understanding-python-metaclasses/
        This is the specification, but is not very readable:
        https://docs.python.org/3/reference/datamodel.html#metaclasses

        Metaclasses are complex; I will attempt to keep __init__ as short as
        possible.

        :param str name:
            The name of the resource class
        :param tuple bases:
            The direct bases of the resource class
        :param dict attrs:
            A dictionary with all properties defined on the resource class
            (attributes, methods, ...)
        """
        # Copy the inherited attributes and relationships
        # This is best done here because we have access to bases (the list of
        # superclasses)
        attrs_by_japi_name = {}
        rels_by_japi_name = {}

        for base in reversed(bases):
            if issubclass(base, Resource):
                attrs_by_japi_name.update(base._attrs_by_japi_name)
                rels_by_japi_name.update(base._rels_by_japi_name)

        # Refer to the BaseField docstring as to why deepcopy is necessary
        attrs_by_japi_name = copy.deepcopy(attrs_by_japi_name)
        cls._attrs_by_japi_name = attrs_by_japi_name
        rels_by_japi_name = copy.deepcopy(rels_by_japi_name)
        cls._rels_by_japi_name = rels_by_japi_name

        for python_name, val in attrs.items():
            if isinstance(val, BaseField):
                # Set the python_name attribute on the value
                # This (access to python_name) is only possible here - without
                # resorting to __dict__
                val.python_name = python_name

                if isinstance(val, Attribute):
                    if not val.japi_name:
                        val.japi_name = python_name
                    attrs_by_japi_name[val.japi_name] = val

                    if val._fget:
                        # If we supplied a custom getter, we shouldn't be using
                        # the default one
                        assert not val.mapped_attribute_name
                    else:
                        # Shouldn't have a custom setter but no getter!
                        assert val._fset is None

                        # If the mapped_attribute_name was not provided, use
                        # the name to which it was assigned
                        if not val.mapped_attribute_name:
                            val.mapped_attribute_name = val.python_name

                        # Neither fget nor fset were provided, use getattr and
                        # setattr as defaults
                        def fget(model, _hack=val.mapped_attribute_name):
                            # Default arg is a hack to deal with late binding
                            return getattr(model, _hack)
                        val._fget = fget

                        if val.writable_during:
                            def fset(model, value,
                                     _hack=val.mapped_attribute_name):
                                setattr(model, _hack, value)
                        # Use a poisoned setter if it is not configured to be
                        # writable
                        else:
                            def fset(model, value):
                                raise AttributeError("No setter provided")
                        val._fset = fset
                if isinstance(val, Id):
                    if val._fget:
                        # If we supplied a custom getter, we shouldn't be using
                        # the default one
                        assert not val.mapped_pk_name
                    else:
                        # Shouldn't have a custom setter but no getter!
                        assert val._fset is None

                        # If the mapped_pk_name was not provided, use
                        # the name to which it was assigned
                        if not val.mapped_pk_name:
                            val.mapped_pk_name = "id"

                        # Neither fget nor fset were provided, use getattr and
                        # setattr as defaults
                        def fget(model, _hack=val.mapped_pk_name):
                            # Default arg is a hack to deal with late binding
                            return getattr(model, _hack)
                        val._fget = fget

                        if val.writable_during:
                            def fset(model, value,
                                     _hack=val.mapped_pk_name):
                                setattr(model, _hack, value)
                        # Use a poisoned setter if it is not configured to be
                        # writable
                        else:
                            def fset(model, value):
                                raise AttributeError("No setter provided")
                        val._fset = fset
                if isinstance(val, Relationship):
                    if not val.japi_name:
                        val.japi_name = python_name
                    val.bound_resource_class = cls
                    rels_by_japi_name[val.japi_name] = val

        cls._instantiable = (
            # Make sure every resource class has an Id
            isinstance(attrs.get("id"), Id) and
            # Make sure every resource class has a corresponding model class
            isinstance(attrs.get("model_class"), type) and
            # Make sure every resource class has a JSON API resource type
            isinstance(attrs.get("japi_resource_type"), str) and
            # Make sure every resource class has a JSON API resource url
            # component
            isinstance(attrs.get("japi_resource_url_component"), str))

        return super().__init__(name, bases, attrs)


class Resource(with_metaclass(ResourceMeta)):
    """
    Represents a JSON API resource.
    """

    def __init__(self, model):
        """
        Creates a Resource.

        :param Model model: Backing database model.
        """
        # Why do we do this here?  So that we can have un-instantiable
        # intermediate subclasses
        assert self._instantiable
        self.model = model

    def serialize(self, link_prefix, fields=None):
        """
        Serializes a Resource.

        :param str link_prefix: The link prefix to use.
        :param str list fields: If None, means we aren't using this option.

        :return dict: Serialized resource in primitive values.
        """
        ret = {}
        id = type(self).id.serialize(self.model)
        ret["id"] = id
        ret["type"] = self.japi_resource_type
        ret["links"] = {
            "self": link_for_resource(
                link_prefix, self.japi_resource_url_component, self.id)
        }

        attributes_dict = {}
        # NOTE: This is accessing *class* attribute!!!
        for attribute_name, value in self._attrs_by_japi_name.items():
            if fields is None or attribute_name in fields:
                attributes_dict[attribute_name] = value.serialize(self.model)

        if attributes_dict:
            ret["attributes"] = attributes_dict

        relationships_dict = {}
        for relationship_name, value in self._rels_by_japi_name.items():
            if fields is None or relationship_name in fields:
                relationships_dict[relationship_name] = value.serialize(
                    self.model, id, link_prefix)
        if relationships_dict:
            ret["relationships"] = relationships_dict

        return ret

    @classmethod
    def deserialize(cls, input_dict, *args, **kwargs):
        """
        Deserialize a Resource from primitive values.

        Use *args and **kwargs to pass required arguments to the constructor
        for the model class

        :param dict input_dict: Primitive values to deserialize.
        """
        res = cls(cls.model_class(*args, **kwargs))

        if input_dict["type"] != cls.japi_resource_type:
            raise errors.BadRequest(
                detail="Type field does not match handler's resource")

        # Attributes handling
        input_attributes_dict = input_dict.get("attributes") or {}

        # Use .keys(), because the values may not be hashable
        request_attributes = input_attributes_dict.keys()
        resource_attributes = cls._attrs_by_japi_name.keys()

        # Unexpected attributes
        extra = request_attributes - resource_attributes
        # Expected attributes present in input_dict
        intersection = request_attributes & resource_attributes
        # Attributes that are defined in the Resource class that don't exist
        # in the request
        missing = resource_attributes - request_attributes

        # A well-formed request should never have any extra attributes.
        if extra:
            # TODO: Better format for error message
            raise errors.UnprocessableEntity(detail="Extra attributes")
        for m in missing:
            field = cls._attrs_by_japi_name[m]
            if not (field.has_default or field.nullable):
                raise errors.UnprocessableEntity(detail="Missing attributes")

        for attribute_name in intersection:
            input_value = input_attributes_dict[attribute_name]
            field = cls._attrs_by_japi_name[attribute_name]
            if input_value is None and not field.nullable:
                raise errors.UnprocessableEntity(
                    detail="Non-nullable attribute set to None")
            if Context.CREATE not in field.writable_during:
                raise errors.Forbidden(detail="Cannot write to field")
            field.deserialize_into_obj(res.model, input_value)

        # Relationships handling
        relationships_dict = input_dict.get("relationships") or {}

        request_relationships = relationships_dict.keys()
        resource_relationships = cls._rels_by_japi_name.keys()

        extra = request_relationships - resource_relationships
        intersection = request_relationships & resource_relationships
        missing = resource_relationships - request_relationships

        if extra:
            # TODO: Better format
            raise errors.UnprocessableEntity(detail="Extra relationships")
        for m in missing:
            field = cls._rels_by_japi_name[m]
            if not (field.nullable or field.has_default):
                raise errors.UnprocessableEntity(detail="Missing relationship")

        for relationship_name in intersection:
            input_value = relationships_dict[relationship_name]
            field = cls._rels_by_japi_name[relationship_name]
            # NOTE: We only currently support to-one relationships
            assert isinstance(field, ToOneRelationship)

            if Context.CREATE not in field.writable_during:
                raise errors.Forbidden(detail="Cannot write to field")
            if input_value is None:  # NOTE: input_value is [] for to one rels
                if not field.nullable:
                    raise errors.UnprocessableEntity(
                        detail="Non-nullable relationship set to None")
            else:
                resource_identifier_obj = input_value["data"]
                if (resource_identifier_obj["type"] !=
                        field.related_resource_class.japi_resource_type):
                    raise errors.BadRequest(
                        detail="Type field does not match schema")

            field.deserialize_into_obj(res.model, input_value)

        return res

    @classmethod
    def create_patch_dict(cls, resource_dict):
        """
        Creates a patch dict.

        :param dict resource_dict: Create a patch dict out of these primitive
                                   values.

        :returns dict: A patch dictionary.
        """
        if resource_dict["type"] != cls.japi_resource_type:
            raise errors.BadRequest(
                detail="Type field does not match handler's resource")

        ret_attrs = {}
        ret_rels = {}

        attributes_dict = resource_dict.get("attributes") or {}

        request_attributes = attributes_dict.keys()
        resource_attributes = cls._attrs_by_japi_name.keys()

        # Unexpected attributes
        extra = request_attributes - resource_attributes
        if extra:
            # TODO: Better format for error message
            raise errors.UnprocessableEntity(detail="Extra attributes")

        # Expected attributes present in resource_dict
        intersection = request_attributes & resource_attributes
        for attribute_name in intersection:
            field = cls._attrs_by_japi_name[attribute_name]
            if Context.UPDATE not in field.writable_during:
                raise errors.Forbidden(detail="Cannot update attribute")
            value = attributes_dict[attribute_name]
            ret_attrs[attribute_name] = field.deserialize(value)

        relationships_dict = resource_dict.get("relationships") or {}

        request_relationships = relationships_dict.keys()
        resource_relationships = cls._rels_by_japi_name.keys()

        # Unexpected relationships
        extra = request_relationships - resource_relationships
        if extra:
            # TODO: Better format for error message
            raise errors.UnprocessableEntity(detail="Extra relationships")

        # Expected relationships present in resource_dict
        intersection = request_relationships & resource_relationships
        for relationship_name in intersection:
            value = relationships_dict[relationship_name]
            field = cls._rels_by_japi_name[relationship_name]
            # NOTE: We only currently support forward relationships
            assert isinstance(field, ToOneRelationship)

            if Context.UPDATE not in field.writable_during:
                raise errors.Forbidden(detail="Cannot update relationship")

            if value is None:  # NOTE: or value is [] for to one relationships
                if not field.nullable:
                    raise errors.UnprocessableEntity(
                        detail="Non-nullable relationship set to None")
            else:
                resource_identifier_obj = value["data"]
                if (resource_identifier_obj["type"] !=
                        field.related_resource_class.japi_resource_type):
                    raise errors.BadRequest(
                        detail="Type field does not match schema")

            ret_rels[relationship_name] = field.deserialize(value)

        return {"attributes": ret_attrs, "relationships": ret_rels}

    def apply_patch_dict(self, patch_dict):
        """
        Applies a patch dictionary to this resource instance.

        :param dict patch_dict: Should be the output of create_patch_dict
        """
        attributes_dict = patch_dict["attributes"]
        for attribute_name, value in attributes_dict.items():
            # NOTE: This is accessing *class* attribute!!!
            field = self._attrs_by_japi_name[attribute_name]
            field._fset(self.model, value)

        relationships_dict = patch_dict["relationships"]
        for relationship_name, value in relationships_dict.items():
            # TODO: We only currently support forward relationships
            assert isinstance(value, ToOneRelationship)
            # NOTE: This is accessing *class* attribute!!!
            field = self._rels_by_japi_name[relationship_name]
            field._fset(self.model, value)

    def validate(self, context):
        """
        Validates this resource.

        :param Context context: The context to determine which validators to
                                call.
        """
        for field in (itertools.chain(self._attrs_by_japi_name.values(),
                                      self._rels_by_japi_name.values())):
            field.validate(self.model, context)
