# -*- coding: utf-8 -*-
"""
    emmett.validators
    -----------------

    Implements validators for pyDAL.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from .basic import (
    Allow,
    Any,
    Equals,
    hasLength,
    isEmpty,
    isEmptyOr,
    isntEmpty,
    Matches,
    Not,
    Validator
)
from .consist import (
    isAlphanumeric,
    isDate,
    isDatetime,
    isDecimal,
    isEmail,
    isFloat,
    isImage,
    isInt,
    isIP,
    isJSON,
    isList,
    isTime,
    isUrl
)
from .inside import inRange, inSet, inDB, notInDB
from .process import Cleanup, Crypt, Lower, Urlify, Upper


class ValidateFromDict(object):
    numkeys = {"gt": False, "gte": True, "lt": False, "lte": True}

    def __init__(self):
        self.is_validators = {
            "alphanumeric": isAlphanumeric,
            "date": isDate,
            "datetime": isDatetime,
            "decimal": isDecimal,
            "email": isEmail,
            "float": isFloat,
            "image": isImage,
            "int": isInt,
            "ip": isIP,
            "json": isJSON,
            "time": isTime,
            "url": isUrl
        }
        self.proc_validators = {
            "clean": Cleanup,
            "crypt": Crypt,
            "lower": Lower,
            "upper": Upper,
            "urlify": Urlify
        }

    def parse_num_comparisons(self, data, minv=None, maxv=None):
        inclusions = [True, False]
        for key, include in self.numkeys.items():
            val = data.get(key)
            if val is not None:
                if key[0] == "g":
                    minv = val
                    inclusions[0] = include
                elif key[0] == "l":
                    maxv = val
                    inclusions[1] = include
        return minv, maxv, inclusions

    def parse_is(self, data, message=None):
        #: map types with fields
        if isinstance(data, str):
            #: map {'is': 'int'}
            key = data
            options = {}
        elif isinstance(data, dict):
            #: map {'is': {'float': {'dot': ','}}}
            key = list(data)[0]
            options = data[key]
        else:
            raise SyntaxError("'is' validator accepts only string or dict")
        validator = self.is_validators.get(key)
        return validator(message=message, **options) if validator else None

    def parse_is_list(self, data, message=None):
        #: map types with 'list' fields
        key = ''
        options = {}
        suboptions = {}
        lopts = ['splitter']
        if isinstance(data, str):
            #: map {'is': 'list:int'}
            key = data
        elif isinstance(data, dict):
            #: map {'is': {'list:float': {'dot': ',', 'splitter': ';'}}}
            key = list(data)[0]
            suboptions = data[key]
            for opt in list(suboptions):
                if opt in lopts:
                    options[opt] = suboptions[opt]
                    del suboptions[opt]
        else:
            raise SyntaxError("'is' validator accepts only string or dict")
        try:
            keyspecs = key.split(':')
            subkey = keyspecs[1].strip()
            assert keyspecs[0].strip() == 'list'
        except Exception:
            subkey = '_missing_'
        validator = self.is_validators.get(subkey)
        return isList(
            [validator(message=message, **suboptions)],
            message=message,
            **options
        ) if validator else None

    def parse_reference(self, field):
        ref_table = None
        multiple = None
        if field.type.startswith('reference'):
            multiple = False
        elif field.type.startswith('list:reference'):
            multiple = True
        if multiple is not None:
            ref_table = field.type.split(' ')[1]
        return ref_table, multiple

    def __call__(self, field, data):
        validators = []
        message = data.pop("message", None)
        #: parse 'presence' and 'empty'
        presence = data.get('presence')
        empty = data.get('empty')
        if presence is None and empty is not None:
            presence = not empty
        #: parse 'is'
        _is = data.get('is')
        if _is is not None:
            validator = self.parse_is(_is, message) or self.parse_is_list(_is, message)
            if validator is None:
                raise SyntaxError(
                    "Unknown type %s for 'is' validator" % data
                )
            validators.append(validator)
        #: parse 'len'
        _len = data.get('len')
        if _len is not None:
            if isinstance(_len, int):
                #: allows {'len': 2}
                validators.append(
                    hasLength(_len + 1, _len, message='Enter {min} characters')
                )
            else:
                #: allows
                #  {'len': {'gt': 1, 'gte': 2, 'lt': 5, 'lte' 6}}
                #  {'len': {'range': (2, 6)}}
                if _len.get('range') is not None:
                    minv, maxv = _len['range']
                    inc = (True, False)
                else:
                    minv, maxv, inc = self.parse_num_comparisons(_len, 0, 256)
                validators.append(hasLength(maxv, minv, inc, message=message))
        #: parse 'in'
        _dbset = None
        _in = data.get('in', [])
        if _in:
            if isinstance(_in, (list, tuple, set)):
                #: allows {'in': [1, 2]}
                validators.append(inSet(_in, message=message))
            elif isinstance(_in, dict):
                options = {}
                #: allows {'in': {'range': (1, 5)}}
                _range = _in.get('range')
                if isinstance(_range, (tuple, list)):
                    validators.append(inRange(_range[0], _range[1], message=message))
                #: allows {'in': {'set': [1, 5]}} with options
                _set = _in.get('set')
                if isinstance(_set, (list, tuple, set)):
                    opt_keys = [key for key in list(_in) if key != 'set']
                    for key in opt_keys:
                        options[key] = _in[key]
                    validators.append(inSet(_set, message=message, **options))
                #: allows {'in': {'dbset': lambda db: db.where(query)}}
                _dbset = _in.get('dbset')
                if callable(_dbset):
                    ref_table, multiple = self.parse_reference(field)
                    if ref_table:
                        opt_keys = [key for key in list(_in) if key != 'dbset']
                        for key in opt_keys:
                            options[key] = _in[key]
                        validators.append(
                            inDB(
                                field.db,
                                ref_table,
                                dbset=_dbset,
                                multiple=multiple,
                                message=message,
                                **options
                            )
                        )
                    else:
                        raise SyntaxError(
                            "'in:dbset' validator needs a reference field"
                        )
            else:
                raise SyntaxError(
                    "'in' validator accepts only a set or a dict"
                )
        #: parse 'gt', 'gte', 'lt', 'lte'
        minv, maxv, inc = self.parse_num_comparisons(data)
        if minv is not None or maxv is not None:
            validators.append(inRange(minv, maxv, inc, message=message))
        #: parse 'equals'
        if 'equals' in data:
            validators.append(Equals(data['equals'], message=message))
        #: parse 'match'
        if 'match' in data:
            if isinstance(data['match'], dict):
                validators.append(Matches(**data['match'], message=message))
            else:
                validators.append(Matches(data['match'], message=message))
        #: parse transforming validators
        for key, vclass in self.proc_validators.items():
            if key in data:
                options = {}
                if isinstance(data[key], dict):
                    options = data[key]
                elif data[key] != True:
                    if key == 'crypt' and isinstance(data[key], str):
                        options = {'algorithm': data[key]}
                    else:
                        raise SyntaxError(
                            key + " validator accepts only dict or True"
                        )
                validators.append(vclass(message=message, **options))
        #: parse 'unique'
        _unique = data.get('unique', False)
        if _unique:
            _udbset = None
            if isinstance(_unique, dict):
                whr = _unique.get('where', None)
                if callable(whr):
                    _dbset = whr
            validators.append(
                notInDB(
                    field.db,
                    field.table,
                    field.name,
                    dbset=_udbset,
                    message=message
                )
            )
            table = field.db[field._tablename]
            table._unique_fields_validation_[field.name] = 1
        #: apply 'format' option
        if 'format' in data:
            for validator in validators:
                children = [validator]
                if hasattr(validator, 'children'):
                    children += validator.children
                for child in children:
                    if hasattr(child, 'format'):
                        child.format = data['format']
                        break
        #: parse 'custom'
        if 'custom' in data:
            if isinstance(data['custom'], list):
                for element in data['custom']:
                    validators.append(element)
            else:
                validators.append(data['custom'])
        #: parse 'any'
        if 'any' in data:
            validators.append(Any(self(field, data['any']), message=message))
        #: parse 'not'
        if 'not' in data:
            validators.append(Not(self(field, data['not']), message=message))
        #: insert presence/empty validation if needed
        if presence:
            ref_table, multiple = self.parse_reference(field)
            if ref_table:
                if not _dbset:
                    validators.append(
                        inDB(field.db, ref_table, multiple=multiple, message=message)
                    )
            else:
                validators.insert(0, isntEmpty(message=message))
        if empty:
            validators.insert(0, isEmpty(message=message))
        #: parse 'allow'
        if 'allow' in data:
            if data['allow'] in ['empty', 'blank']:
                validators = [isEmptyOr(validators, message=message)]
            else:
                validators = [Allow(data['allow'], validators, message=message)]
        return validators
