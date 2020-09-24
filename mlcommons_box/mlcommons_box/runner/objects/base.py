import abc
import collections
import os
import typing


class BaseField(abc.ABC):

    @abc.abstractmethod
    def get_default_value(self):
        return NotImplementedError

    @abc.abstractmethod
    def get_value_from_primitive(self,
            primitive: typing.Any=None) -> typing.Any:
        return NotImplementedError


class ObjectField(BaseField):

    def __init__(self, obj_class: 'BaseObject', embedded: bool=False):
        self.object_class = obj_class
        self.embedded = embedded

    def get_default_value(self) -> 'BaseObject':
        instance = self.object_class().default()
        return instance

    def get_value_from_primitive(self,
            primitive: typing.Any=None) -> 'BaseObject':
        instance = self.object_class().from_primitive(primitive=primitive)
        return instance


class PrimitiveField(BaseField):

    def __init__(self, default: typing.Any=None):
        self.default_value = default

    def get_default_value(self) -> typing.Any:
        return self.default_value

    def get_value_from_primitive(self,
            primitive: typing.Any=None) -> typing.Any:
        instance = self.get_default_value()
        if primitive is not None:
            instance = primitive
        return instance


class BaseObject(abc.ABC):

    @classmethod
    @abc.abstractmethod
    def validate(cls, primitive: typing.Any) -> bool:
        raise NotImplementedError

    @abc.abstractmethod
    def default(self) -> 'BaseObject':
        raise NotImplementedError

    @abc.abstractmethod
    def from_primitive(self,
            primitive: typing.Any) -> 'BaseObject':
        raise NotImplementedError

    @abc.abstractmethod
    def merge(self, overlay: typing.Any) -> 'BaseObject':
        raise NotImplementedError


class StandardObject(BaseObject):

    fields = {}

    @classmethod
    def validate(cls, primitive: typing.Any) -> bool:
        # TODO: implement proper validation
        if not isinstance(primitive, dict):
            return False
        return True

    def default(self) -> 'StandartObject':
        if self.fields is None:
            self.fields = {}
        for fld_name, fld in self.fields.items():
            attr = fld.get_default_value()
            setattr(self, fld_name, attr)
            if isinstance(fld, ObjectField) and fld.embedded is True:
                self._embed_object(attr)
        return self

    def from_primitive(self, primitive: typing.Any) -> 'StandardObject':
        if not self.validate(primitive):
            raise ValueError("Validation failed for {}".format(
                    self.__class__.__name__))
        for fld_name, fld in self.fields.items():
            if isinstance(fld, ObjectField) and fld.embedded is True:
                attr = fld.get_value_from_primitive(primitive)
                setattr(self, fld_name, attr)
                self._embed_object(attr)
            else:
                attr = fld.get_default_value()
                prim_fld_val = primitive.get(fld_name, None)
                if prim_fld_val is not None:
                    attr = fld.get_value_from_primitive(prim_fld_val)
                setattr(self, fld_name, attr)
        return self

    def _embed_object(self, obj):
        # Embed an object by copying its attributes to the current (parent)
        # object, with the exception that the current object has an existing
        # attribute of the same name, in which case the attribute in the
        # current (parent) object takes priority.
        if obj.fields is not None:
            for subfld_name, subfld in obj.fields.items():
                if subfld_name not in self.fields.keys():
                    subattr = getattr(obj, subfld_name)
                    setattr(self, subfld_name, subattr)

    def merge(self, overlay: typing.Any) -> 'StandardObject':
        def _merge_list(base, overlay):
            result = base or []
            result.extend(overlay)
            return result
        def _merge_dict(base, overlay):
            result = base or {}
            for key, val in overlay.items():
                if isinstance(val, dict):
                    node = result.setdefault(key, {})
                    result[key] = _merge_dict(node[key], val)
                else:
                    result[key] = val
            return result
        if not isinstance(overlay, self.__class__):
            raise TypeError("Cannot merge instances of different classes.")
        for attr_name in self.fields.keys():
            attr = getattr(self, attr_name)
            overlay_attr = getattr(overlay, attr_name)
            if isinstance(attr, BaseObject):
                attr.merge(overlay_attr)
            elif isinstance(overlay_attr, list):
                attr = _merge_list(attr, overlay_attr)
            elif isinstance(overlay_attr, dict):
                attr = _merge_dict(attr, overlay_attr)
            elif overlay_attr is not None:
                attr = overlay_attr
            setattr(self, attr_name, attr)
        return self


class ListOfObject(BaseObject):

    item_class = StandardObject

    def __init__(self):
        self._data = []
        super(ListOfObject, self).__init__()

    def __repr__(self): return repr(self._data)
    def __len__(self): return len(self._data)
    def __getitem__(self, i):
        if isinstance(i, slice):
            return self.__class__(self._data[i])
        else:
            return self._data[i]

    @classmethod
    def validate(cls, primitive: typing.Any) -> bool:
        # TODO: implement proper validation
        if not isinstance(primitive, list):
            return False
        return True

    def default(self) -> 'ListOfObject':
        self._data = []
        return self

    def from_primitive(self, primitive: typing.Any) -> 'ListOfObject':
        if not self.validate(primitive):
            raise ValueError("Validation failed for {}".format(
                    self.__class__.__name__))
        for item in primitive:
            if item is not None:
                obj_instance = self.item_class().from_primitive(item)
                self._data.append(obj_instance)
        return self

    def merge(self, overlay: typing.Any) -> 'ListOfObject':
        if not isinstance(overlay, self.__class__):
            raise TypeError("Cannot merge instances of different classes.")
        self._data.extend(overlay)
        return self


class DictOfObject(BaseObject):

    value_class = StandardObject

    def __init__(self):
        self._data = {}
        super(DictOfObject, self).__init__()

    def __repr__(self): return repr(self._data)
    def __len__(self): return len(self._data)
    def __getitem__(self, key):
        if key in self._data:
            return self._data[key]
        if hasattr(self.__class__, "__missing__"):
            return self.__class__.__missing__(self, key)
        raise KeyError(key)

    @classmethod
    def validate(cls, primitive: typing.Any) -> bool:
        # TODO: implement proper validation
        if not isinstance(primitive, dict):
            return False
        return True

    def default(self):
        self._data = {}
        return self

    def from_primitive(self, primitive: typing.Any) -> 'DictOfObject':
        if not self.validate(primitive):
            raise ValueError("Validation failed for {}".format(
                    self.__class__.__name__))
        for key, value in primitive.items():
            if value is not None:
                obj_instance = self.value_class().from_primitive(value)
                self._data[key] = obj_instance

    def merge(self, overlay: typing.Any) -> 'DictOfObject':
        if not isinstance(overlay, self.__class__):
            raise TypeError("Cannot merge instances of different classes.")
        for key, value in overlay.items():
            self._data.setdefault(value)
            self._data[key].merge(value)
        return self
