# -*- coding: utf-8 -*-
"""
    weppy.validators
    ----------------

    Implements validators for pyDAL.

    :copyright: (c) 2015 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from .basic import Validator, isntEmpty, isEmptyOr, Equals, Matches, hasLength
from .consist import isInt, isFloat, isDecimal, isDate, isTime, isDatetime, \
    isEmail, isJSON, isUrl, isIP, isImage
from .inside import inRange, inSet, inSubSet, inDb, notInDb
from .process import Cleanup, Crypt, Lower, Slug, Upper


class ValidateFromDict(object):
    numkeys = {'gt': 1, 'gte': 0, 'lt': 0, 'lte': 1}

    def __init__(self):
        self.iskeys = {
            'int': isInt, 'float': isFloat, 'decimal': isDecimal,
            'date': isDate, 'time': isTime, 'datetime': isDatetime,
            'email': isEmail, 'url': isUrl, 'ip': isIP, 'json': isJSON,
            'image': isImage
        }
        self.prockeys = {
            'crypt': Crypt, 'lower': Lower, 'upper': Upper, 'slug': Slug,
            'clean': Cleanup
        }

    def parse_num_comparisons(self, data):
        minv = None
        maxv = None
        for key, addend in self.numkeys.iteritems():
            val = data.get(key)
            if val is not None:
                if key[0] == "g":
                    minv = val + addend
                elif key[0] == "l":
                    maxv = val + addend
        return minv, maxv

    def __call__(self, field, data):
        # 'is', 'equals', 'not', 'match', 'length', 'presence', 'empty'
        validators = []
        #: parse 'presence' and 'empty'
        presence = data.get('presence')
        if presence is None:
            presence = not data.get('empty', True)
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
                validators.append(hasLength(_len, _len,
                                  error_message='Enter %(min)g characters'))
            else:
                #: allows
                #  {'len': {'gt': 1, 'gte': 2, 'lt': 5, 'lte' 6}}
                #  {'len': {'range': (2, 6)}}
                if _len.get('range') is not None:
                    minv, maxv = _len['range']
                else:
                    minv, maxv = self.parse_num_comparisons(_len)
                validators.append(hasLength(maxv, minv))
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
        minv, maxv = self.parse_num_comparisons(data)
        if minv is not None or maxv is not None:
            validators.append(inRange(minv, maxv))
        # 'range'
        #if 'range' in data:
        #    minv, maxv = data['range']
        #    validators.append(inRange(minv, maxv))
        #: parse 'equals'
        if 'equals' in data:
            validators.append(Equals(data['equals']))
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
        #: parse 'not'
        if 'not' in data:
            validators.append(self(data['not']))
        #: insert presence validation if needed
        if presence:
            if field.type.startswith('reference'):
                pass
            else:
                validators.insert(0, isntEmpty())
        else:
            if validators:
                validators = [isEmptyOr(validators)]
        return validators
