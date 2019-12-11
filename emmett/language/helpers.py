# -*- coding: utf-8 -*-
"""
    emmett.language.helpers
    -----------------------

    Adapted from the web2py's code (http://www.web2py.com)

    :copyright: (c) by Massimo Di Pierro <mdipierro@cs.depaul.edu>
    :license: LGPLv3 (http://www.gnu.org/licenses/lgpl.html)
"""

import ast
import os
import pkgutil
import re

# TODO: check conversions
from .._shortcuts import to_bytes, to_unicode

from ..datastructures import Accept
from ..libs.portalocker import read_locked, LockedFile
from .cache import clear_cache, getcfs


regex_locale_delim = re.compile(r'[_-]')
regex_backslash = re.compile(r"\\([\\{}%])")
regex_langfile = re.compile('^[a-z]{2}(-[a-z]{2})?\.py$')
regex_plural = re.compile('%({.+?})')
# %%{word(varname or number)}
regex_plural_dict = re.compile(
    '^{(?P<w>[^()[\]][^()[\]]*?)\((?P<n>[^()\[\]]+)\)}$')
# %%{word[index]} or %%{word}
regex_plural_tuple = re.compile('^{(?P<w>[^[\]()]+)(?:\[(?P<i>\d+)\])?}$')
regex_plural_file = re.compile('^plural-[a-zA-Z]{2}(-[a-zA-Z]{2})?\.py$')


# DEFAULT PLURAL-FORMS RULES:
# language doesn't use plural forms
DEFAULT_NPLURALS = 1
# only one singular/plural form is used
DEFAULT_GET_PLURAL_ID = lambda n: 0
# word is unchangeable
DEFAULT_CONSTRUCT_PLURAL_FORM = lambda word, plural_id: word


def read_possible_plural_rules():
    """
    create list of all possible plural rules files
    result is cached in PLURAL_RULES dictionary to increase speed
    """
    plurals = {}
    try:
        from . import plurals as package
        for importer, modname, ispkg in pkgutil.iter_modules(package.__path__):
            if len(modname) == 2:
                module = __import__(package.__name__ + '.' + modname,
                                    fromlist=[modname])
                lang = modname
                #pname = modname + '.py'
                nplurals = getattr(module, 'nplurals', DEFAULT_NPLURALS)
                get_plural_id = getattr(
                    module, 'get_plural_id',
                    DEFAULT_GET_PLURAL_ID)
                construct_plural_form = getattr(
                    module, 'construct_plural_form',
                    DEFAULT_CONSTRUCT_PLURAL_FORM)
                plurals[lang] = (lang, nplurals, get_plural_id,
                                 construct_plural_form)
    except ImportError:
        pass
    return plurals


PLURAL_RULES = read_possible_plural_rules()


class LanguageAccept(Accept):
    def _value_matches(self, value, item):
        def _normalize(language):
            return regex_locale_delim.split(language.lower())[0]
        return item == '*' or _normalize(value) == _normalize(item)


def read_plural_dict_aux(filename):
    lang_text = read_locked(filename).replace('\r\n', '\n')
    try:
        return eval(lang_text) or {}
    except Exception:
        #e = sys.exc_info()[1]
        #status = 'Syntax error in %s (%s)' % (filename, e)
        #logging.error(status)
        status = 'Syntax error in %s' % filename
        return {'__corrupted__': status}


def read_plural_dict(filename):
    return getcfs('plurals:' + filename, filename,
                  lambda: read_plural_dict_aux(filename))


_plural_header = '''#!/usr/bin/env python
# "singular form (0)": ["first plural form (1)", "second plural form (2)", ...]
{
'''


def write_plural_dict(filename, contents):
    if '__corrupted__' in contents:
        return
    try:
        fp = LockedFile(filename, 'wb')
        fp.write(to_bytes(_plural_header))
        # coding: utf8\n{\n')
        for key in sorted(contents):
            forms = '[' + ','.join(
                '"' + form + '"' for form in contents[key]
            ) + ']'
            val = '    "%s": %s,\n' % (key, forms)
            fp.write(to_bytes(val))
        fp.write(to_bytes('}\n'))
    except (IOError, OSError):
        #if not is_gae:
        #    logging.warning('Unable to write to file %s' % filename)
        return
    finally:
        fp.close()


def safe_eval(text):
    if text.strip():
        try:
            return ast.literal_eval(text)
        except ImportError:
            return eval(text, {}, {})
    return None


def read_dict_aux(filename):
    lang_text = read_locked(filename).replace('\r\n', '\n')
    clear_cache(filename)
    try:
        rv = safe_eval(lang_text) or {}
    except Exception:
        #e = sys.exc_info()[1]
        #status = 'Syntax error in %s (%s)' % (filename, e)
        #logging.error(status)
        status = 'Syntax error in %s' % filename
        rv = {'__corrupted__': status}
    return rv


def read_dict(filename):
    """ return dictionary with translation messages
    """
    return getcfs('lang:' + filename, filename,
                  lambda: read_dict_aux(filename))


def write_dict(filename, contents):
    if '__corrupted__' in contents:
        return
    try:
        fp = LockedFile(filename, 'wb')
    except (IOError, OSError):
        return
    fp.write(to_bytes('# coding: utf8\n{\n'))
    for key in sorted(contents):
        val = '"%s": "%s",\n' % (key, contents[key])
        fp.write(to_bytes(val))
    fp.write(to_bytes('}\n'))
    fp.close()


def _get_lang_struct(plurals, lang, langcode, langname, langfile_mtime):
    if lang == 'default':
        real_lang = langcode
    else:
        real_lang = lang
    (
        prules_langcode, nplurals, get_plural_id, construct_plural_form
    ) = PLURAL_RULES.get(
        (real_lang or '__unknown__')[:2], (
            'default', DEFAULT_NPLURALS, DEFAULT_GET_PLURAL_ID,
            DEFAULT_CONSTRUCT_PLURAL_FORM)
    )
    if prules_langcode != 'default':
        pluraldict_fname, pluraldict_mtime = plurals.get(
            real_lang,
            plurals.get(real_lang[:2], ('plural-%s.py' % real_lang, 0)))
    else:
        pluraldict_fname = None
        pluraldict_mtime = 0
    return (
        # language code from !langcode
        langcode,
        # language name in national spelling from !langname!
        langname,
        # m_time of language file
        langfile_mtime,
        # name of plural dictionary file or None (when default.py is not exist)
        pluraldict_fname,
        # m_time of plural dictionary file or 0 if file is not exist
        pluraldict_mtime,
        # code of plural rules language or 'default'
        prules_langcode,
        # nplurals for current language
        nplurals,
        # get_plural_id() for current language
        get_plural_id,
        # construct_plural_form() for current language
        construct_plural_form
    )


def _read_possible_languages(langdir):
    plurals = {}
    flist = os.listdir(langdir)
    # scan languages directory for plural dict files:
    for pname in flist:
        if regex_plural_file.match(pname):
            plurals[pname[7:-3]] = (
                pname,
                os.stat(os.path.join(langdir, pname)).st_mtime)
    langs = {}
    # scan languages directory for langfiles:
    for fname in flist:
        if not (regex_langfile.match(fname) or fname == 'default.py'):
            continue
        fname_with_path = os.path.join(langdir, fname)
        d = read_dict(fname_with_path)
        lang = fname[:-3]
        langcode = d.get(
            '!langcode!', lang if lang != 'default' else '__')
        langname = d.get('!langname!', 'None')
        langfile_mtime = os.stat(fname_with_path).st_mtime
        langs[lang] = _get_lang_struct(
            plurals, lang, langcode, langname, langfile_mtime)
    if 'default' not in langs:
        # if default.py is not found,
        # add DEFAULT_LANGUAGE as default language:
        langs['default'] = _get_lang_struct(
            plurals, 'default', '__', 'None', 0)
    deflang = langs['default']
    deflangcode = deflang[0]
    if deflangcode not in langs:
        # create language from default.py:
        langs[deflangcode] = deflang[:2] + (0,) + deflang[3:]
    return langs


def read_possible_languages(langpath):
    return getcfs(
        'langs:' + langpath, langpath,
        lambda: _read_possible_languages(langpath))


def upper_fun(s):
    return to_unicode(s).upper().encode('utf-8')


def title_fun(s):
    return to_unicode(s).title().encode('utf-8')


def cap_fun(s):
    return to_unicode(s).capitalize().encode('utf-8')


def _make_ttabin():
    ltrans = "\\%{}"
    rtrans = '\x1c\x1d\x1e\x1f'
    return dict((ord(char), rtrans) for char in ltrans)


def _make_ttabout():
    ltrans = '\x1c\x1d\x1e\x1f'
    rtrans = "\\%{}"
    return dict((ord(char), rtrans) for char in ltrans)


ttab_in = _make_ttabin()
ttab_out = _make_ttabout()