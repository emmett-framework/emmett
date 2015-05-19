# -*- coding: utf-8 -*-
"""
    weppy.validators
    ----------------

    Implements validators for pyDAL.

    :copyright: (c) 2015 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from .basic import Validator, isntEmpty, isEmptyOr, Equals, Matches, \
    hasLength, Not, Allow, isEmpty, Any
from .consist import isInt, isFloat, isDecimal, isDate, isTime, isDatetime, \
    isEmail, isJSON, isUrl, isIP, isImage, isAlphanumeric
from .inside import inRange, inSet, inSubSet, inDB, notInDB
from .process import Cleanup, Crypt, Lower, Urlify, Upper


class ValidateFromDict(object):
    numkeys = {'gt': False, 'gte': True, 'lt': False, 'lte': True}

    def __init__(self):
        self.iskeys = {
            'int': isInt, 'float': isFloat, 'decimal': isDecimal,
            'date': isDate, 'time': isTime, 'datetime': isDatetime,
            'email': isEmail, 'url': isUrl, 'ip': isIP, 'json': isJSON,
            'image': isImage, 'alphanumeric': isAlphanumeric
        }
        self.prockeys = {
            'crypt': Crypt, 'lower': Lower, 'upper': Upper, 'urlify': Urlify,
            'clean': Cleanup
        }

    def parse_num_comparisons(self, data, minv=None, maxv=None):
        inclusions = [True, False]
        for key, include in self.numkeys.iteritems():
            val = data.get(key)
            if val is not None:
                if key[0] == "g":
                    minv = val
                    inclusions[0] = include
                elif key[0] == "l":
                    maxv = val
                    inclusions[1] = include
        return minv, maxv, inclusions

    def __call__(self, field, data):
        # 'is', 'equals', 'not', 'match', 'length', 'presence', 'empty'
        validators = []
        #: parse 'presence' and 'empty'
        presence = data.get('presence')
        empty = data.get('empty')
        if presence is None and empty is not None:
            presence = not empty
        #: parse 'is'
        _is = data.get('is')
        if _is is not None:
            # TODO 'list'
            #: map types with fields
            if isinstance(_is, basestring):
                validator = self.iskeys.get(_is)
                options = {}
            elif isinstance(_is, dict):
                key = list(_is)[0]
                validator = self.iskeys.get(key)
                options = _is[key]
            else:
                raise SyntaxError("'is' validator accepts only string or dict")
            if validator is None:
                raise SyntaxError("Unknown type %s for 'is' validator" % _is)
            validators.append(validator(**options))
        #: parse 'len'
        _len = data.get('len')
        if _len is not None:
            if isinstance(_len, int):
                #: allows {'len': 2}
                validators.append(
                    hasLength(_len+1, _len, message='Enter %(min)g characters')
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
                validators.append(hasLength(maxv, minv, inc))
        #: parse 'in'
        _in = data.get('in', [])
        if _in:
            if isinstance(_in, (list, tuple, set)):
                #: allows {'in': [1, 2], 'labels': ['one', 'two']}
                opt_keys = ['labels', 'message', 'multiple', 'zero', 'sort']
                options = {}
                for key in opt_keys:
                    val = data.get(key)
                    if val:
                        options[key] = val
                validators.append(inSet(_in, **options))
            elif isinstance(_in, dict):
                #: allows {'in': {'range': (1, 5)}}
                _range = _in.get('range')
                if isinstance(_range, (tuple, list)):
                    validators.append(inRange(_range[0], _range[1]))
                #: allows {'in': {'sub': [1, 2, 4]}}
                _sub = _in.get('sub')
                if isinstance(_sub, (list, set, tuple)):
                    validators.append(inSubSet(_sub))
            else:
                raise SyntaxError(
                    "'in' validator accepts only a set or a dict")
        #: parse 'gt', 'gte', 'lt', 'lte'
        minv, maxv, inc = self.parse_num_comparisons(data)
        if minv is not None or maxv is not None:
            validators.append(inRange(minv, maxv, inc))
        #: parse 'equals'
        if 'equals' in data:
            validators.append(Equals(data['equals']))
        #: parse 'match'
        if 'match' in data:
            if isinstance(data['match'], dict):
                validators.append(Matches(**data['match']))
            else:
                validators.append(Matches(data['match']))
        #: parse transforming validators
        for key, vclass in self.prockeys.iteritems():
            if key in data:
                options = {}
                if isinstance(data[key], dict):
                    options = data[key]
                elif data[key] != True:
                    if key == 'crypt' and isinstance(data[key], basestring):
                        options = {'algorithm': data[key]}
                    else:
                        raise SyntaxError(
                            key+" validator accepts only dict or True")
                validators.append(vclass(**options))
        #: parse 'unique'
        if data.get('unique', False):
            validators.append(notInDB(field.db, field.table, field.name))
        #: common options ('format', 'message')
        if 'format' in data:
            for validator in validators:
                if hasattr(validator, 'format'):
                    validator.format = data['format']
                    break
        if 'message' in data:
            for validator in validators:
                validator.message = data['message']
        #: parse 'any'
        if 'any' in data:
            validators.append(Any(self(field, data['any'])))
        #: parse 'not'
        if 'not' in data:
            validators.append(Not(self(field, data['not'])))
        #: insert presence/empty validation if needed
        if presence:
            if field.type.startswith('reference'):
                ref_table = field.type.split(' ')[1]
                validators.append(inDB(field.db, ref_table))
            validators.insert(0, isntEmpty())
        if empty:
            validators.insert(0, isEmpty())
        #: parse 'allow'
        if 'allow' in data:
            if data['allow'] in ['empty', 'blank']:
                validators = [isEmptyOr(validators)]
            else:
                validators = [Allow(data['allow'], validators)]
        return validators
