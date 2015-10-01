# -*- coding: utf-8 -*-
"""
    weppy.language.helpers
    ----------------------

    Adapted from the web2py's code (http://www.web2py.com)

    :copyright: (c) by Massimo Di Pierro <mdipierro@cs.depaul.edu>
    :license: LGPLv3 (http://www.gnu.org/licenses/lgpl.html)
"""

import ast
import os
import pkgutil
import re

from .._compat import PY2, to_unicode, to_bytes
from .cache import clear_cache, getcfs
from ..libs.portalocker import read_locked, LockedFile


regex_backslash = re.compile(r"\\([\\{}%])")
regex_langfile = re.compile('^[a-z]{2}(-[a-z]{2})?\.py$')
regex_plural = re.compile('%({.+?})')
# %%{word(varname or number)}
regex_plural_dict = re.compile(
    '^{(?P<w>[^()[\]][^()[\]]*?)\((?P<n>[^()\[\]]+)\)}$')
# %%{word[index]} or %%{word}
regex_plural_tuple = re.compile('^{(?P<w>[^[\]()]+)(?:\[(?P<i>\d+)\])?}$')
regex_plural_file = re.compile('^plural-[a-zA-Z]{2}(-[a-zA-Z]{2})?\.py$')
regex_language = re.compile(
    '([a-z]{2,3}(?:\-[a-z]{2})?(?:\-[a-z]{2})?)(?:[,;]|$)')


DEFAULT_LANGUAGE = 'en'
DEFAULT_LANGUAGE_NAME = 'English'

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
        import weppy.language.plurals as package
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


def write_plural_dict(filename, contents):
    if '__corrupted__' in contents:
        return
    try:
        fp = LockedFile(filename, 'wb')
        fp.write(to_bytes(u'#!/usr/bin/env python\n{\n# "singular form (0)": ["first plural form (1)", "second plural form (2)", ...],\n'))
        # coding: utf8\n{\n')
        for key in sorted(contents):
            forms = u'[' + u','.join('"'+form+'"' for form in contents[key]) + u']'
            val = u'"%s": %s,\n' % (key, forms)
            fp.write(to_bytes(val))
        fp.write(to_bytes(u'}\n'))
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
        if PY2:
            for key, val in rv.items():
                rv[to_unicode(key)] = to_unicode(val)
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
    fp.write(to_bytes(u'# coding: utf8\n{\n'))
    for key in sorted(contents):
        val = u'"%s": "%s",\n' % (key, contents[key])
        fp.write(to_bytes(val))
    fp.write(to_bytes(u'}\n'))
    fp.close()


def read_possible_languages_aux(langdir):
    def get_lang_struct(lang, langcode, langname, langfile_mtime):
        if lang == 'default':
            real_lang = langcode.lower()
        else:
            real_lang = lang
        (prules_langcode,
         nplurals,
         get_plural_id,
         construct_plural_form
         ) = PLURAL_RULES.get(real_lang[:2], ('default',
                                              DEFAULT_NPLURALS,
                                              DEFAULT_GET_PLURAL_ID,
                                              DEFAULT_CONSTRUCT_PLURAL_FORM))
        if prules_langcode != 'default':
            (pluraldict_fname, pluraldict_mtime) = plurals.get(
                real_lang,
                plurals.get(real_lang[:2], ('plural-%s.py' % real_lang, 0)))
        else:
            pluraldict_fname = None
            pluraldict_mtime = 0
        return (langcode,        # language code from !langcode!
                langname,
                # language name in national spelling from !langname!
                langfile_mtime,  # m_time of language file
                pluraldict_fname,  # name of plural dictionary file or None (when default.py is not exist)
                pluraldict_mtime,  # m_time of plural dictionary file or 0 if file is not exist
                prules_langcode,  # code of plural rules language or 'default'
                nplurals,        # nplurals for current language
                get_plural_id,   # get_plural_id() for current language
                construct_plural_form)  # construct_plural_form() for current language

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
        if regex_langfile.match(fname) or fname == 'default.py':
            fname_with_path = os.path.join(langdir, fname)
            d = read_dict(fname_with_path)
            lang = fname[:-3]
            langcode = d.get('!langcode!', lang if lang != 'default'
                             else DEFAULT_LANGUAGE)
            langname = d.get('!langname!', langcode)
            langfile_mtime = os.stat(fname_with_path).st_mtime
            langs[lang] = get_lang_struct(lang, langcode,
                                          langname, langfile_mtime)
    if 'default' not in langs:
        # if default.py is not found,
        # add DEFAULT_LANGUAGE as default language:
        langs['default'] = get_lang_struct('default', DEFAULT_LANGUAGE,
                                           DEFAULT_LANGUAGE_NAME, 0)
    deflang = langs['default']
    deflangcode = deflang[0]
    if deflangcode not in langs:
        # create language from default.py:
        langs[deflangcode] = deflang[:2] + (0,) + deflang[3:]

    return langs


def read_possible_languages(langpath):
    return getcfs('langs:' + langpath, langpath,
                  lambda: read_possible_languages_aux(langpath))


def upper_fun(s):
    return to_unicode(s).upper().encode('utf-8')


def title_fun(s):
    return to_unicode(s).title().encode('utf-8')


def cap_fun(s):
    return to_unicode(s).capitalize().encode('utf-8')


def _make_ttabin():
    ltrans = u"\\%{}"
    rtrans = u'\x1c\x1d\x1e\x1f'
    return dict((ord(char), rtrans) for char in ltrans)


def _make_ttabout():
    ltrans = u'\x1c\x1d\x1e\x1f'
    rtrans = u"\\%{}"
    return dict((ord(char), rtrans) for char in ltrans)


#ttab_in = maketrans(u"\\%{}", u'\x1c\x1d\x1e\x1f')
#ttab_out = maketrans(u'\x1c\x1d\x1e\x1f', u"\\%{}")
ttab_in = _make_ttabin()
ttab_out = _make_ttabout()
