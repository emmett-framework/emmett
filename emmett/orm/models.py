# -*- coding: utf-8 -*-
"""
    emmett.orm.models
    -----------------

    Provides model layer for Emmet's ORM.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

import operator
import types

from collections import OrderedDict
from functools import reduce
from typing import Any, Callable

from ..datastructures import sdict
from .apis import (
    compute,
    rowattr,
    rowmethod,
    scope,
    belongs_to,
    refers_to,
    has_one,
    has_many
)
from .errors import (
    InsertFailureOnSave,
    SaveException,
    UpdateFailureOnSave,
    ValidationError,
    DestroyException
)
from .helpers import (
    Callback,
    ReferenceData,
    RowReferenceMixin,
    RowReferenceMulti,
    camelize,
    decamelize,
    make_tablename,
    typed_row_reference,
    typed_row_reference_from_record,
    wrap_scope_on_model,
    wrap_virtual_on_model
)
from .objects import Field, StructuredRow
from .wrappers import HasOneWrap, HasOneViaWrap, HasManyWrap, HasManyViaWrap


class MetaModel(type):
    _inheritable_dict_attrs_ = [
        'indexes', 'validation', ('fields_rw', {'id': False}), 'foreign_keys',
        'default_values', 'update_values', 'repr_values',
        'form_labels', 'form_info', 'form_widgets'
    ]

    def __new__(cls, name, bases, attrs):
        new_class = type.__new__(cls, name, bases, attrs)
        #: collect declared attributes
        tablename = attrs.get('tablename')
        fields = []
        vfields = []
        computations = []
        callbacks = []
        declared_fields = OrderedDict()
        declared_vfields = OrderedDict()
        declared_computations = OrderedDict()
        declared_callbacks = OrderedDict()
        declared_scopes = {}
        for key, value in list(attrs.items()):
            if isinstance(value, Field):
                fields.append((key, value))
            elif isinstance(value, rowattr):
                vfields.append((key, value))
            elif isinstance(value, compute):
                computations.append((key, value))
            elif isinstance(value, Callback):
                callbacks.append((key, value))
            elif isinstance(value, scope):
                declared_scopes[key] = value
        declared_relations = sdict(
            belongs=OrderedDict(), refers=OrderedDict(),
            hasone=OrderedDict(), hasmany=OrderedDict()
        )
        for ref in belongs_to._references_.values():
            for item in ref.reference:
                rkey = list(item)[0] if isinstance(item, dict) else item
                declared_relations.belongs[rkey] = item
        belongs_to._references_ = {}
        for ref in refers_to._references_.values():
            for item in ref.reference:
                rkey = list(item)[0] if isinstance(item, dict) else item
                declared_relations.refers[rkey] = item
        refers_to._references_ = {}
        for ref in has_one._references_.values():
            for item in ref.reference:
                rkey = list(item)[0] if isinstance(item, dict) else item
                declared_relations.hasone[rkey] = item
        has_one._references_ = {}
        for ref in has_many._references_.values():
            for item in ref.reference:
                rkey = list(item)[0] if isinstance(item, dict) else item
                declared_relations.hasmany[rkey] = item
        has_many._references_ = {}
        #: sort declared attributes that keeps order
        fields.sort(key=lambda x: x[1]._inst_count_)
        vfields.sort(key=lambda x: x[1]._inst_count_)
        computations.sort(key=lambda x: x[1]._inst_count_)
        callbacks.sort(key=lambda x: x[1]._inst_count_)
        declared_fields.update(fields)
        declared_vfields.update(vfields)
        declared_computations.update(computations)
        declared_callbacks.update(callbacks)
        #: store declared attributes in class
        new_class._declared_tablename_ = tablename
        new_class._declared_fields_ = declared_fields
        new_class._declared_virtuals_ = declared_vfields
        new_class._declared_computations_ = declared_computations
        new_class._declared_callbacks_ = declared_callbacks
        new_class._declared_scopes_ = declared_scopes
        new_class._declared_belongs_ref_ = declared_relations.belongs
        new_class._declared_refers_ref_ = declared_relations.refers
        new_class._declared_hasone_ref_ = declared_relations.hasone
        new_class._declared_hasmany_ref_ = declared_relations.hasmany
        #: get super declared attributes
        all_fields = OrderedDict()
        all_vfields = OrderedDict()
        all_computations = OrderedDict()
        all_callbacks = OrderedDict()
        all_scopes = {}
        all_relations = sdict(
            belongs=OrderedDict(), refers=OrderedDict(),
            hasone=OrderedDict(), hasmany=OrderedDict()
        )
        super_vfields = OrderedDict()
        for base in reversed(new_class.__mro__[1:]):
            if hasattr(base, '_declared_fields_'):
                all_fields.update(base._declared_fields_)
            if hasattr(base, '_declared_virtuals_'):
                all_vfields.update(base._declared_virtuals_)
                super_vfields.update(base._declared_virtuals_)
            if hasattr(base, '_declared_computations_'):
                all_computations.update(base._declared_computations_)
            if hasattr(base, '_declared_callbacks_'):
                all_callbacks.update(base._declared_callbacks_)
            if hasattr(base, '_declared_scopes_'):
                all_scopes.update(base._declared_scopes_)
            for key in list(all_relations):
                attrkey = '_declared_' + key + '_ref_'
                if hasattr(base, attrkey):
                    all_relations[key].update(getattr(base, attrkey))
        #: compose 'all' attributes
        all_fields.update(declared_fields)
        all_vfields.update(declared_vfields)
        all_computations.update(declared_computations)
        all_callbacks.update(declared_callbacks)
        all_scopes.update(declared_scopes)
        for key in list(all_relations):
            all_relations[key].update(declared_relations[key])
        #: store 'all' attributes on class
        new_class._all_fields_ = all_fields
        new_class._all_virtuals_ = all_vfields
        new_class._all_computations_ = all_computations
        new_class._all_callbacks_ = all_callbacks
        new_class._all_scopes_ = all_scopes
        new_class._all_belongs_ref_ = all_relations.belongs
        new_class._all_refers_ref_ = all_relations.refers
        new_class._all_hasone_ref_ = all_relations.hasone
        new_class._all_hasmany_ref_ = all_relations.hasmany
        #: store 'super' attributes on class
        new_class._super_virtuals_ = super_vfields
        return new_class


class Model(metaclass=MetaModel):
    db = None
    table = None

    auto_validation = True

    @classmethod
    def _init_inheritable_dicts_(cls):
        if cls.__bases__ != (object,):
            return
        for attr in cls._inheritable_dict_attrs_:
            if isinstance(attr, tuple):
                attr_name, default = attr
            else:
                attr_name, default = attr, {}
            if not isinstance(default, dict):
                raise SyntaxError(f"{attr_name} is not a dictionary")
            setattr(cls, attr_name, default)

    @classmethod
    def _merge_inheritable_dicts_(cls, models):
        for attr in cls._inheritable_dict_attrs_:
            if isinstance(attr, tuple):
                attr_name = attr[0]
            else:
                attr_name = attr
            attrs = {}
            for model in models:
                superattrs = getattr(model, attr_name)
                for k, v in superattrs.items():
                    attrs[k] = v
            for k, v in getattr(cls, attr_name).items():
                attrs[k] = v
            setattr(cls, attr_name, attrs)

    @classmethod
    def __getsuperattrs(cls):
        superattr = "_supermodels" + cls.__name__
        if hasattr(cls, superattr):
            return
        supermodels = cls.__bases__
        superattr_val = []
        for supermodel in supermodels:
            try:
                supermodel.__getsuperattrs()
                superattr_val.append(supermodel)
            except Exception:
                pass
        setattr(cls, superattr, superattr_val)
        sup = getattr(cls, superattr)
        if not sup:
            return
        cls._merge_inheritable_dicts_(sup)

    def __new__(cls):
        if cls._declared_tablename_ is None:
            cls.tablename = make_tablename(cls.__name__)
        cls.__getsuperattrs()
        return super(Model, cls).__new__(cls)

    def __init__(self):
        if not hasattr(self, 'migrate'):
            self.migrate = self.config.get('migrate', self.db._migrate)
        if not hasattr(self, 'format'):
            self.format = None
        if not hasattr(self, 'primary_keys'):
            self.primary_keys = []
        self._fieldset_pk = set(self.primary_keys or ['id'])

    @property
    def config(self):
        return self.db.config

    def __parse_relation_via(self, via):
        if via is None:
            return via
        rv = sdict()
        splitted = via.split('.')
        rv.via = splitted[0]
        if len(splitted) > 1:
            rv.field = splitted[1]
        return rv

    def __parse_belongs_relation(self, item, on_delete):
        rv = sdict(fk=None, on_delete=on_delete, compound=None)
        if isinstance(item, dict):
            rv.name = list(item)[0]
            rdata = item[rv.name]
            target = None
            if isinstance(rdata, dict):
                if "target" in rdata:
                    target = rdata["target"]
                if "on_delete" in rdata:
                    rv.on_delete = rdata["on_delete"]
            else:
                target = rdata
            if not target:
                target = camelize(rv.name)
            if "." in target:
                target, rv.fk = target.split(".")
            if target == "self":
                target = self.__class__.__name__
            rv.model = target
        else:
            rv.name = item
            rv.model = camelize(item)
        return rv

    def __build_relation_modelname(self, name, relation, singularize):
        relation.model = camelize(name)
        if singularize:
            relation.model = relation.model[:-1]

    def __build_relation_fieldnames(self, relation):
        splitted = relation.model.split('.')
        relation.model = splitted[0]
        if len(splitted) > 1:
            relation.fields = [splitted[1]]
        else:
            if len(self.primary_keys) > 1:
                relation.fields = [
                    f"{decamelize(self.__class__.__name__)}_{pk}"
                    for pk in self.primary_keys
                ]
            else:
                relation.fields = [decamelize(self.__class__.__name__)]

    def __parse_relation_dict(self, rel, singularize):
        if 'scope' in rel.model:
            rel.scope = rel.model['scope']
        if 'where' in rel.model:
            rel.where = rel.model['where']
        if 'via' in rel.model:
            rel.update(self.__parse_relation_via(rel.model['via']))
            del rel.model
        else:
            if 'target' in rel.model:
                rel.model = rel.model['target']
            if not isinstance(rel.model, str):
                self.__build_relation_modelname(rel.name, rel, singularize)

    def __parse_many_relation(self, item, singularize=True):
        rv = ReferenceData(self)
        if isinstance(item, dict):
            rv.name = list(item)[0]
            rv.model = item[rv.name]
            if isinstance(rv.model, dict):
                if 'method' in rv.model:
                    if 'field' in rv.model:
                        rv.fields = [rv.model['field']]
                    else:
                        if len(self.primary_keys) > 1:
                            rv.fields = [
                                f"{decamelize(self.__class__.__name__)}_{pk}"
                                for pk in self.primary_keys
                            ]
                        else:
                            rv.fields = [decamelize(self.__class__.__name__)]
                    rv.cast = rv.model.get('cast')
                    rv.method = rv.model['method']
                    del rv.model
                else:
                    self.__parse_relation_dict(rv, singularize)
        else:
            rv.name = item
            self.__build_relation_modelname(item, rv, singularize)
        if rv.model:
            if not rv.fields:
                self.__build_relation_fieldnames(rv)
            if rv.model == "self":
                rv.model = self.__class__.__name__
        if not rv.via:
            rv.reverse = (
                rv.fields[0] if len(rv.fields) == 1 else
                decamelize(self.__class__.__name__)
            )
        return rv

    def _define_props_(self):
        #: create pydal's Field elements
        self.fields = []
        if not self.primary_keys and 'id' not in self._all_fields_:
            idfield = Field('id')._make_field('id', model=self)
            setattr(self.__class__, 'id', idfield)
            self.fields.append(idfield)
        for name, obj in self._all_fields_.items():
            if obj.modelname is not None:
                obj = Field(obj._type, *obj._args, _kw=obj._ormkw, **obj._kwargs)
                setattr(self.__class__, name, obj)
            self.fields.append(obj._make_field(name, self))

    def __find_matching_fk_definition(self, fields, rmodel):
        match = None
        if not set(fields).issubset(set(rmodel.primary_keys)):
            return match
        for key, val in self.foreign_keys.items():
            if set(val["foreign_fields"]) == set(rmodel.primary_keys):
                match = key
                break
        return match

    def _define_relations_(self):
        self._virtual_relations_ = OrderedDict()
        self._compound_relations_ = {}
        bad_args_error = (
            "belongs_to, has_one and has_many "
            "only accept strings or dicts as arguments"
        )
        #: belongs_to and refers_to are mapped with 'reference' type Field
        _references = []
        _reference_keys = ['_all_belongs_ref_', '_all_refers_ref_']
        belongs_references = {}
        belongs_fks = {}
        for key in _reference_keys:
            if hasattr(self, key):
                _references.append(list(getattr(self, key).values()))
            else:
                _references.append([])
        is_belongs, ondelete = True, 'cascade'
        for _references_obj in _references:
            for item in _references_obj:
                if not isinstance(item, (str, dict)):
                    raise RuntimeError(bad_args_error)
                reference = self.__parse_belongs_relation(item, ondelete)
                reference.is_refers = not is_belongs
                refmodel = (
                    self.db[reference.model]._model_
                    if reference.model != self.__class__.__name__
                    else self
                )
                ref_multi_pk = len(refmodel._fieldset_pk) > 1
                fk_def_key, fks_data, multi_fk = None, {}, []
                if ref_multi_pk and reference.fk:
                    fk_def_key = self.__find_matching_fk_definition(
                        [reference.fk], refmodel
                    )
                    if not fk_def_key:
                        raise SyntaxError(
                            f"{self.__class__.__name__}.{reference.name} relation "
                            "targets a compound primary key table. A matching foreign "
                            "key needs to be defined into `foreign_keys`"
                        )
                    fks_data = self.foreign_keys[fk_def_key]
                elif ref_multi_pk and not reference.fk:
                    multi_fk = list(refmodel.primary_keys)
                elif not reference.fk:
                    reference.fk = list(refmodel._fieldset_pk)[0]
                if multi_fk:
                    references = []
                    fks_data["fields"] = []
                    fks_data["foreign_fields"] = []
                    for fk in multi_fk:
                        refclone = sdict(reference)
                        refclone.fk = fk
                        refclone.ftype = getattr(refmodel, refclone.fk).type
                        refclone.name = f"{refclone.name}_{refclone.fk}"
                        refclone.compound = reference.name
                        references.append(refclone)
                        fks_data["fields"].append(refclone.name)
                        fks_data["foreign_fields"].append(refclone.fk)
                    belongs_fks[reference.name] = sdict(
                        model=reference.model,
                        name=reference.name,
                        local_fields=fks_data["fields"],
                        foreign_fields=fks_data["foreign_fields"],
                        coupled_fields=[
                            (local, fks_data["foreign_fields"][idx])
                            for idx, local in enumerate(fks_data["fields"])
                        ],
                        is_refers=reference.is_refers
                    )
                    self._compound_relations_[reference.name] = sdict(
                        model=reference.model,
                        local_fields=belongs_fks[reference.name].local_fields,
                        foreign_fields=belongs_fks[reference.name].foreign_fields,
                        coupled_fields=belongs_fks[reference.name].coupled_fields,
                    )
                else:
                    reference.ftype = getattr(refmodel, reference.fk).type
                    references = [reference]
                    belongs_fks[reference.name] = sdict(
                        model=reference.model,
                        name=reference.name,
                        local_fields=[reference.name],
                        foreign_fields=[reference.fk],
                        coupled_fields=[(reference.name, reference.fk)],
                        is_refers=reference.is_refers
                    )
                if not fk_def_key and fks_data:
                    self.foreign_keys[reference.name] = self.foreign_keys.get(
                        reference.name
                    ) or fks_data
                for reference in references:
                    if reference.model != self.__class__.__name__:
                        tablename = self.db[reference.model]._tablename
                    else:
                        tablename = self.tablename
                    fieldobj = Field(
                        (
                            f"reference {tablename}" if not ref_multi_pk else
                            f"reference {tablename}.{reference.fk}"
                        ),
                        ondelete=reference.on_delete,
                        _isrefers=not is_belongs
                    )
                    setattr(self.__class__, reference.name, fieldobj)
                    self.fields.append(
                        getattr(self, reference.name)._make_field(
                            reference.name, self
                        )
                    )
                    belongs_references[reference.name] = reference
            is_belongs = False
            ondelete = 'nullify'
        setattr(self.__class__, '_belongs_ref_', belongs_references)
        setattr(self.__class__, '_belongs_fks_', belongs_fks)
        #: has_one are mapped with rowattr
        hasone_references = {}
        if hasattr(self, '_all_hasone_ref_'):
            for item in getattr(self, '_all_hasone_ref_').values():
                if not isinstance(item, (str, dict)):
                    raise RuntimeError(bad_args_error)
                reference = self.__parse_many_relation(item, False)
                if reference.via is not None:
                    #: maps has_one({'thing': {'via': 'otherthings'}})
                    wrapper = HasOneViaWrap
                else:
                    #: maps has_one('thing'), has_one({'thing': 'othername'})
                    wrapper = HasOneWrap
                self._virtual_relations_[reference.name] = rowattr(
                    reference.name
                )(wrapper(reference))
                hasone_references[reference.name] = reference
        setattr(self.__class__, '_hasone_ref_', hasone_references)
        #: has_many are mapped with rowattr
        hasmany_references = {}
        if hasattr(self, '_all_hasmany_ref_'):
            for item in getattr(self, '_all_hasmany_ref_').values():
                if not isinstance(item, (str, dict)):
                    raise RuntimeError(bad_args_error)
                reference = self.__parse_many_relation(item)
                if reference.via is not None:
                    #: maps has_many({'things': {'via': 'otherthings'}})
                    wrapper = HasManyViaWrap
                else:
                    #: maps has_many('things'), has_many({'things': 'othername'})
                    wrapper = HasManyWrap
                self._virtual_relations_[reference.name] = rowattr(
                    reference.name
                )(wrapper(reference))
                hasmany_references[reference.name] = reference
        setattr(self.__class__, '_hasmany_ref_', hasmany_references)
        self.__define_fks()

    def __define_fks(self):
        self._foreign_keys_ = {}
        implicit_defs = {}
        grouped_rels = {}
        for rname, rel in self._belongs_ref_.items():
            rmodel = (
                self.db[rel.model]._model_
                if rel.model != self.__class__.__name__
                else self
            )
            if (
                not rmodel.primary_keys and
                getattr(rmodel, list(rmodel._fieldset_pk)[0]).type == 'id'
            ):
                continue
            if len(rmodel._fieldset_pk) > 1:
                match = self.__find_matching_fk_definition([rel.fk], rmodel)
                if not match:
                    raise SyntaxError(
                        f"{self.__class__.__name__}.{rname} relation targets a "
                        "compound primary key table. A matching foreign key "
                        "needs to be defined into `foreign_keys`."
                    )
                trels = grouped_rels[rmodel.tablename] = grouped_rels.get(
                    rmodel.tablename, {
                        'rels': {},
                        'on_delete': self.foreign_keys[match].get(
                            "on_delete", "cascade"
                        )
                    }
                )
                trels['rels'][rname] = rel
            else:
                # NOTE: we need this since pyDAL doesn't support id/refs types != int
                implicit_defs[rname] = {
                    'table': rmodel.tablename,
                    'fields_local': [rname],
                    'fields_foreign': [rel.fk],
                    'on_delete': Field._internal_delete[rel.on_delete]
                }
        for rname, rel in implicit_defs.items():
            constraint_name =  self.__create_fk_contraint_name(
                rel['table'], *rel['fields_local']
            )
            self._foreign_keys_[constraint_name] = {**rel}
        for tname, rels in grouped_rels.items():
            constraint_name = self.__create_fk_contraint_name(
                tname, *[rel.name for rel in rels['rels'].values()]
            )
            self._foreign_keys_[constraint_name] = {
                'table': tname,
                'fields_local': [rel.name for rel in rels['rels'].values()],
                'fields_foreign': [rel.fk for rel in rels['rels'].values()],
                'on_delete': Field._internal_delete[rels['on_delete']]
            }

    def _define_virtuals_(self):
        self._all_rowattrs_ = {}
        self._all_rowmethods_ = {}
        self._super_rowmethods_ = {}
        err = 'rowattr or rowmethod cannot have the name of an existent field!'
        field_names = [field.name for field in self.fields]
        for attr in ['_virtual_relations_', '_all_virtuals_']:
            for obj in getattr(self, attr, {}).values():
                if obj.field_name in field_names:
                    raise RuntimeError(err)
                wrapped = wrap_virtual_on_model(self, obj.f)
                if isinstance(obj, rowmethod):
                    self._all_rowmethods_[obj.field_name] = wrapped
                    f = Field.Method(obj.field_name, wrapped)
                else:
                    self._all_rowattrs_[obj.field_name] = wrapped
                    f = Field.Virtual(obj.field_name, wrapped)
                self.fields.append(f)
        for obj in self._super_virtuals_.values():
            wrapped = wrap_virtual_on_model(self, obj.f)
            if not isinstance(obj, rowmethod):
                continue
            self._super_rowmethods_[obj.field_name] = wrapped

    def _set_row_persistence_id(self, row, ret):
        row.id = ret.id
        object.__setattr__(row, '_concrete', True)

    def _set_row_persistence_pk(self, row, ret):
        row[self.primary_keys[0]] = ret[self.primary_keys[0]]
        object.__setattr__(row, '_concrete', True)

    def _set_row_persistence_pks(self, row, ret):
        for field_name in self.primary_keys:
            row[field_name] = ret[field_name]
        object.__setattr__(row, '_concrete', True)

    def _unset_row_persistence(self, row):
        for field_name in self._fieldset_pk:
            row[field_name] = None
        object.__setattr__(row, '_concrete', False)

    def _build_rowclass_(self):
        #: build helpers for rows
        save_excluded_fields = (
            set(
                field.name for field in self.fields if
                getattr(field, "type", None) == "id"
            ) |
            set(self._all_rowattrs_.keys()) |
            set(self._all_rowmethods_.keys())
        )
        self._fieldset_initable = set([
            field.name for field in self.fields
        ]) - save_excluded_fields
        self._fieldset_editable = set([
            field.name for field in self.fields
        ]) - save_excluded_fields - self._fieldset_pk
        self._fieldset_all = self._fieldset_initable | self._fieldset_pk
        self._fieldset_update = set([
            field.name for field in self.fields
            if getattr(field, "update", None) is not None
        ]) & self._fieldset_editable
        self._relations_wrapset = (
            set(self._belongs_fks_.keys()) -
            set(self._compound_relations_.keys())
        )
        if not self.primary_keys:
            self._set_row_persistence = self._set_row_persistence_id
        elif len(self.primary_keys) == 1:
            self._set_row_persistence = self._set_row_persistence_pk
        else:
            self._set_row_persistence = self._set_row_persistence_pks
        #: create dynamic row class
        clsname = self.__class__.__name__ + "Row"
        attrs = {'_model': self}
        attrs.update({k: RowFieldMapper(k) for k in self._fieldset_all})
        attrs.update({
            k: RowVirtualMapper(k, v)
            for k, v in self._all_rowattrs_.items()
        })
        attrs.update(self._all_rowmethods_)
        attrs.update({
            k: RowRelationMapper(self.db, self._belongs_ref_[k])
            for k in self._relations_wrapset
        })
        attrs.update({
            k: RowCompoundRelationMapper(
                self.db, data
            ) for k, data in self._compound_relations_.items()
        })
        self._rowclass_ = type(clsname, (StructuredRow,), attrs)
        globals()[clsname] = self._rowclass_

    def _define_(self):
        self.__define_indexes()
        self.__define_validation()
        self.__define_access()
        self.__define_defaults()
        self.__define_updates()
        self.__define_representation()
        self.__define_computations()
        self.__define_callbacks()
        self.__define_scopes()
        self.__define_query_helpers()
        self.__define_form_utils()
        self.setup()

    def __define_validation(self):
        for field in self.fields:
            if isinstance(field, (Field.Method, Field.Virtual)):
                continue
            validation = self.validation.get(field.name, {})
            if isinstance(validation, dict):
                for key in list(validation):
                    field._requires[key] = validation[key]
            elif isinstance(validation, list):
                field._custom_requires += validation
            else:
                field._custom_requires.append(validation)
            field._parse_validation()

    def __define_access(self):
        for field, value in self.fields_rw.items():
            if field == 'id' and field not in self.table:
                continue
            if isinstance(value, (tuple, list)):
                readable, writable = value
            else:
                writable = value
                readable = value
            self.table[field].writable = writable
            self.table[field].readable = readable

    def __define_defaults(self):
        for field, value in self.default_values.items():
            self.table[field].default = value

    def __define_updates(self):
        for field, value in self.update_values.items():
            self.table[field].update = value

    def __define_representation(self):
        for field, value in self.repr_values.items():
            self.table[field].represent = value

    def __define_computations(self):
        err = 'computations should have the name of an existing field to compute!'
        field_names = [field.name for field in self.fields]
        for obj in self._all_computations_.values():
            if obj.field_name not in field_names:
                raise RuntimeError(err)
            self.table[obj.field_name].compute = (
                lambda row, obj=obj, self=self: obj.compute(self, row)
            )

    def __define_callbacks(self):
        for obj in self._all_callbacks_.values():
            for t in obj.t:
                if t in [
                    "_before_insert",
                    "_before_delete",
                    "_after_delete",
                    "_before_save",
                    "_after_save",
                    "_before_destroy",
                    "_after_destroy",
                    "_before_commit_insert",
                    "_before_commit_update",
                    "_before_commit_delete",
                    "_before_commit_save",
                    "_before_commit_destroy",
                    "_after_commit_insert",
                    "_after_commit_update",
                    "_after_commit_delete",
                    "_after_commit_save",
                    "_after_commit_destroy"
                ]:
                    getattr(self.table, t).append(
                        lambda a, obj=obj, self=self: obj.f(self, a)
                    )
                else:
                    getattr(self.table, t).append(
                        lambda a, b, obj=obj, self=self: obj.f(self, a, b)
                    )

    def __define_scopes(self):
        self._scopes_ = {}
        for obj in self._all_scopes_.values():
            self._scopes_[obj.name] = obj
            if not hasattr(self.__class__, obj.name):
                setattr(
                    self.__class__, obj.name,
                    classmethod(wrap_scope_on_model(obj.f))
                )

    def __prepend_table_name(self, name, ns):
        return '%s_%s__%s' % (self.tablename, ns, name)

    def __create_index_name(self, *values):
        components = []
        for value in values:
            components.append(value.replace('_', ''))
        return self.__prepend_table_name("_".join(components), 'widx')

    def __create_fk_contraint_name(self, *values):
        components = []
        for value in values:
            components.append(value.replace('_', ''))
        return self.__prepend_table_name("fk__" + "_".join(components), 'ecnt')

    def __parse_index_dict(self, value):
        rv = {}
        fields = value.get('fields') or []
        if not isinstance(fields, (list, tuple)):
            fields = [fields]
        rv['fields'] = fields
        where_query = None
        where_cond = value.get('where')
        if callable(where_cond):
            where_query = where_cond(self.__class__)
        if where_query:
            rv['where'] = where_query
        expressions = []
        expressions_cond = value.get('expressions')
        if callable(expressions_cond):
            expressions = expressions_cond(self.__class__)
        if not isinstance(expressions, (tuple, list)):
            expressions = [expressions]
        rv['expressions'] = expressions
        rv['unique'] = value.get('unique', False)
        return rv

    def __define_indexes(self):
        self._indexes_ = {}
        #: auto-define indexes based on fields
        for field in self.fields:
            if getattr(field, 'unique', False):
                idx_name = self.__prepend_table_name(f'{field.name}_unique', 'widx')
                idx_dict = self.__parse_index_dict(
                    {'fields': [field.name], 'unique': True}
                )
                self._indexes_[idx_name] = idx_dict
        #: parse user-defined fields
        for key, value in self.indexes.items():
            if isinstance(value, bool):
                if not value:
                    continue
                if not isinstance(key, tuple):
                    key = [key]
                if any(field not in self.table for field in key):
                    raise SyntaxError(f'Invalid field specified in indexes: {key}')
                idx_name = self.__create_index_name(*key)
                idx_dict = {'fields': key, 'expressions': [], 'unique': False}
            elif isinstance(value, dict):
                idx_name = self.__prepend_table_name(key, 'widx')
                idx_dict = self.__parse_index_dict(value)
            else:
                raise SyntaxError('Values in indexes dict should be booleans or dicts')
            self._indexes_[idx_name] = idx_dict

    def _row_record_query_id(self, row):
        return self.table.id == row.id

    def _row_record_query_pk(self, row):
        return self.table[self.primary_keys[0]] == row[self.primary_keys[0]]

    def _row_record_query_pks(self, row):
        return reduce(
            operator.and_, [self.table[pk] == row[pk] for pk in self.primary_keys]
        )

    def __define_query_helpers(self):
        if not self.primary_keys:
            self._query_id = self.table.id != None # noqa
            self._query_row = self._row_record_query_id
            self._order_by_id_asc = self.table.id
            self._order_by_id_desc = ~self.table.id
        elif len(self.primary_keys) == 1:
            self._query_id = self.table[self.primary_keys[0]] != None # noqa
            self._query_row = self._row_record_query_pk
            self._order_by_id_asc = self.table[self.primary_keys[0]]
            self._order_by_id_desc = ~self.table[self.primary_keys[0]]
        else:
            self._query_id = reduce(
                operator.and_, [
                    self.table[key] != None # noqa
                    for key in self.primary_keys
                ]
            )
            self._query_row = self._row_record_query_pks
            self._order_by_id_asc = reduce(
                operator.or_, [self.table[key] for key in self.primary_keys]
            )
            self._order_by_id_desc = reduce(
                operator.or_, [~self.table[key] for key in self.primary_keys]
            )

    def __define_form_utils(self):
        #: labels
        for field, value in self.form_labels.items():
            self.table[field].label = value
        #: info
        for field, value in self.form_info.items():
            self.table[field].comment = value
        #: widgets
        for field, value in self.form_widgets.items():
            self.table[field].widget = value

    def setup(self):
        pass

    def get_rowmethod(self, name: str):
        return self._all_rowmethods_[name]

    def super_rowmethod(self, name: str):
        return self._super_rowmethods_[name]

    @classmethod
    def _instance_(cls):
        return cls.table._model_

    @classmethod
    def new(cls, **attributes):
        inst = cls._instance_()
        attrset = set(attributes.keys())
        rowattrs = {}
        for field in (inst._fieldset_initable - inst._relations_wrapset) & attrset:
            rowattrs[field] = attributes[field]
        for field in inst._fieldset_initable - attrset:
            val = cls.table[field].default
            if callable(val):
                val = val()
            rowattrs[field] = val
        for field in (inst.primary_keys or ["id"]):
            if inst.table[field].type == "id":
                rowattrs[field] = None
        for field in set(inst._compound_relations_.keys()) & attrset:
            reldata = inst._compound_relations_[field]
            for local_field, foreign_field in reldata.coupled_fields:
                rowattrs[local_field] = attributes[field][foreign_field]
        rv = inst._rowclass_(
            rowattrs, __concrete=False,
            **{k: attributes[k] for k in attrset - set(rowattrs)}
        )
        rv._fields.update({
            field: attributes[field] if not attributes[field] else (
                typed_row_reference_from_record(
                    attributes[field], inst.db[inst._belongs_fks_[field].model]._model_
                ) if isinstance(attributes[field], StructuredRow) else
                typed_row_reference(
                    attributes[field], inst.db[inst._belongs_fks_[field].model]
                )
            ) for field in inst._relations_wrapset & attrset
        })
        return rv

    @classmethod
    def create(cls, *args, skip_callbacks=False, **kwargs):
        inst = cls._instance_()
        if args:
            if isinstance(args[0], (dict, sdict)):
                for key in list(args[0]):
                    kwargs[key] = args[0][key]
        for field in set(inst._compound_relations_.keys()) & set(kwargs.keys()):
            reldata = inst._compound_relations_[field]
            for local_field, foreign_field in reldata.coupled_fields:
                kwargs[local_field] = kwargs[field][foreign_field]
        return cls.table.validate_and_insert(skip_callbacks=skip_callbacks, **kwargs)

    @classmethod
    def validate(cls, row, write_values: bool = False):
        inst, errors = cls._instance_(), sdict()
        for field_name in inst._fieldset_all:
            field = inst.table[field_name]
            default = getattr(field, 'default')
            if callable(default):
                default = default()
            value = row.get(field_name, default)
            new_value, error = field.validate(value)
            if error:
                errors[field_name] = error
            elif new_value is not None and write_values:
                row[field_name] = new_value
        return errors

    @classmethod
    def where(cls, cond):
        if not isinstance(cond, types.LambdaType):
            raise ValueError("Model.where expects a lambda as parameter")
        return cls.db.where(cond(cls), model=cls)

    @classmethod
    def all(cls):
        return cls.db.where(cls._instance_()._query_id, model=cls)

    @classmethod
    def first(cls):
        return cls.all().select(
            orderby=cls._instance_()._order_by_id_asc,
            limitby=(0, 1)
        ).first()

    @classmethod
    def last(cls):
        return cls.all().select(
            orderby=cls._instance_()._order_by_id_desc,
            limitby=(0, 1)
        ).first()

    @classmethod
    def get(cls, *args, **kwargs):
        if args:
            inst = cls._instance_()
            if len(args) == 1:
                if isinstance(args[0], tuple):
                    args = args[0]
                elif isinstance(args[0], dict) and not kwargs:
                    return cls.table(**args[0])
            if len(args) != len(inst._fieldset_pk):
                raise SyntaxError(
                    f"{cls.__name__}.get requires the same number of arguments "
                    "as its primary keys"
                )
            pks = inst.primary_keys or ["id"]
            return cls.table(
                **{pks[idx]: val for idx, val in enumerate(args)}
            )
        return cls.table(**kwargs)

    @rowmethod('update_record')
    def _update_record(self, row, skip_callbacks=False, **fields):
        newfields = fields or dict(row)
        for field_name in set(newfields.keys()) - self._fieldset_editable:
            del newfields[field_name]
        res = self.db(
            self._query_row(row), ignore_common_filters=True
        ).update(skip_callbacks=skip_callbacks, **newfields)
        if res:
            row.update(self.get(**{key: row[key] for key in self._fieldset_pk}))
        return row

    @rowmethod('delete_record')
    def _delete_record(self, row, skip_callbacks=False):
        return self.db(self._query_row(row)).delete(skip_callbacks=skip_callbacks)

    @rowmethod('refresh')
    def _row_refresh(self, row) -> bool:
        if not row._concrete:
            return False
        last = self.db(self._query_row(row)).select(
            limitby=(0, 1),
            orderby_on_limitby=False
        ).first()
        if not last:
            return False
        row._fields.update(last._fields)
        row.__dict__.clear()
        row._changes.clear()
        return True

    @rowmethod('save')
    def _row_save(
        self,
        row,
        raise_on_error: bool = False,
        skip_callbacks: bool = False
    ) -> bool:
        if row._concrete:
            if set(row._changes.keys()) & self._fieldset_pk:
                if raise_on_error:
                    raise SaveException(
                        'Cannot save a record with altered primary key(s)'
                    )
                return False
            for field_name in self._fieldset_update:
                val = self.table[field_name].update
                if callable(val):
                    val = val()
                row[field_name] = val
        errors = self.validate(row, write_values=True)
        if errors:
            if raise_on_error:
                raise ValidationError
            return False
        if row._concrete:
            res = self.db(
                self._query_row(row), ignore_common_filters=True
            )._update_from_save(self, row, skip_callbacks=skip_callbacks)
            if not res:
                if raise_on_error:
                    raise UpdateFailureOnSave
                return False
        else:
            self.table._insert_from_save(row, skip_callbacks=skip_callbacks)
            if not row._concrete:
                if raise_on_error:
                    raise InsertFailureOnSave
                return False
        extra_changes = {
            key: row._changes[key]
            for key in set(row._changes.keys()) & set(row.__dict__.keys())
        }
        row._changes.clear()
        row._changes.update(extra_changes)
        return True

    @rowmethod('destroy')
    def _row_destroy(
        self,
        row,
        raise_on_error: bool = False,
        skip_callbacks: bool = False
    ) -> bool:
        if not row._concrete:
            return False
        res = self.db(
            self._query_row(row), ignore_common_filters=True
        )._delete_from_destroy(self, row, skip_callbacks=skip_callbacks)
        if not res:
            if raise_on_error:
                raise DestroyException
            return False
        row._changes.clear()
        return True


class RowFieldMapper:
    __slots__ = ["field"]

    def __init__(self, field: str):
        self.field = field

    def __set__(self, obj, val):
        obj._fields[self.field] = val

    def __get__(self, obj, objtype=None):
        return obj._fields.get(self.field)

    def __delete__(self, obj):
        obj._fields.pop(self.field, None)


class RowVirtualMapper:
    __slots__ = ["field", "fget"]

    def __init__(self, field: str, fget: Callable[..., Any]):
        self.field = field
        self.fget = fget

    def __get__(self, obj, objtype=None):
        if self.field not in obj._virtuals:
            obj._virtuals[self.field] = rv = self.fget(obj)
            return rv
        return obj._virtuals[self.field]

    def __delete__(self, obj):
        obj._virtuals.pop(self.field, None)


class RowRelationMapper:
    __slots__ = ["table", "field"]

    def __init__(self, db, relation_data):
        self.table = db[relation_data.model]
        self.field = relation_data.name

    def __set__(self, obj, val):
        if not val:
            val = None
        elif val and not isinstance(val, RowReferenceMixin):
            if isinstance(val, StructuredRow):
                val = typed_row_reference_from_record(val, val._model)
            else:
                val = typed_row_reference(val, self.table)
        obj._fields[self.field] = val

    def __get__(self, obj, objtype=None):
        return obj._fields.get(self.field)

    def __delete__(self, obj):
        obj._fields.pop(self.field, None)


class RowCompoundRelationMapper:
    __slots__ = ["table", "fields", "field"]

    def __init__(self, db, relation_data):
        self.table = db[relation_data.model]
        self.field = relation_data.name
        self.fields = relation_data.coupled_fields

    def __set__(self, obj, val):
        if not isinstance(val, (StructuredRow, RowReferenceMulti)):
            return
        for local_field, foreign_field in self.fields:
            obj[local_field] = val[foreign_field]

    def __get__(self, obj, objtype=None):
        pks = {fk: obj[lk] for lk, fk in self.fields}
        key = (self.field, *pks.values())
        if key not in obj._compound_rels:
            obj._compound_rels[key] = RowReferenceMulti(pks, self.table) if all(
                v is not None for v in pks.values()
            ) else None
        return obj._compound_rels[key]

    def __delete__(self, obj):
        pks = {fk: obj[lk] for lk, fk in self.fields}
        key = (self.field, *pks.values())
        obj._compound_rels.pop(key, None)
