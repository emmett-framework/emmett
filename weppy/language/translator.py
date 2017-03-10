# -*- coding: utf-8 -*-
"""
    weppy.language.translator
    -------------------------

    The translator main logic.

    :copyright: (c) 2014-2017 by Giovanni Barillari

    Based on the web2py's translation system (http://www.web2py.com)
    :copyright: (c) by Massimo Di Pierro <mdipierro@cs.depaul.edu>

    :license: LGPLv3 (http://www.gnu.org/licenses/lgpl.html)
"""

import os

from .._compat import (
    PY2, implements_bool, implements_to_string, iteritems, iterkeys,
    to_unicode
)
from ..globals import current
from ..html import asis, htmlescape
from ..utils import cachedprop
from .helpers import (
    regex_backslash, regex_plural, regex_plural_dict, regex_plural_tuple,
    DEFAULT_NPLURALS, DEFAULT_GET_PLURAL_ID, DEFAULT_CONSTRUCT_PLURAL_FORM,
    read_possible_languages, read_dict, write_dict, read_plural_dict,
    write_plural_dict, ttab_in, ttab_out, upper_fun, title_fun, cap_fun
)
from .cache import get_from_cache

if PY2:
    NUMBERS = (int, long, float)
else:
    NUMBERS = (int, float)


#: The single 'translator string element', is created when user calls
#  T('string'), and will be translated when loaded in templates or converted to
#  a string (via str())
@implements_bool
@implements_to_string
class TElement(object):
    m = s = T = language = None
    M = is_copy = False

    def __init__(self, T, message, symbols={}, M=False, language=None):
        if isinstance(message, TElement):
            self.m = message.m
            self.s = message.s
            self.T = message.T
            self.M = message.M
            self.language = message.language
            self.is_copy = True
        else:
            self.m = message
            self.s = symbols
            self.T = T
            self.M = M
            self.language = language
            self.is_copy = False

    def __getstate__(self):
        return {'m': self.m, 's': self.s, 'language': self.language}

    def __setstate__(self, state):
        from . import _instance
        self.T = _instance._t
        self.m = state['m']
        self.s = state['s']
        self.language = state['language']

    def __repr__(self):
        return "<Tstr %s>" % repr(self.m)

    def __str__(self):
        lang = self.language
        if lang is None:
            #: use language provided by http_accept_language or
            #  url (if forced by application), fallback on default language
            lang = current.language or self.T.current_languages[0]
        # return str(self.T.apply_filter(lang, self.m, self.s) if self.M else
        #            self.T.translate(lang, self.m, self.s))
        return self.T.translate(lang, self.m, self.s)

    def __eq__(self, other):
        return str(self) == str(other)

    def __ne__(self, other):
        return str(self) != str(other)

    def __add__(self, other):
        return '%s%s' % (self, other)

    def __radd__(self, other):
        return '%s%s' % (other, self)

    def __mul__(self, other):
        return str(self) * other

    def __cmp__(self, other):
        return cmp(str(self), str(other))

    def __hash__(self):
        return hash(str(self))

    def __getattr__(self, name):
        return getattr(str(self), name)

    def __getitem__(self, i):
        return str(self)[i]

    def __getslice__(self, i, j):
        return str(self)[i:j]

    def __iter__(self):
        for c in str(self):
            yield c

    def __len__(self):
        return len(str(self))

    def __bool__(self):
        return len(self.m) > 0

    def encode(self, *a, **b):
        return str(self).encode(*a, **b)

    def decode(self, *a, **b):
        return str(self).decode(*a, **b)

    def read(self):
        return str(self)

    def __mod__(self, symbols):
        if self.is_copy:
            return TElement(self)
        return TElement(self.T, self.m, symbols, self.M)

    def __json__(self):
        return str(self)


#: A language for the translator.
class TLanguage(object):
    def __init__(self, translator, l_info, filename=None, writable=True):
        self.translator = translator
        self.filename = filename
        self.writable = writable
        self.cached = translator.cached
        self._init_plurals(l_info)

    def _init_plurals(self, lang_info):
        if lang_info:
            (pname, pmtime, self.plural_language, self.nplurals,
             self.get_plural_id, self.construct_plural_form) = lang_info[3:]
            self.pmtime = pmtime
            if pname:
                pname = os.path.join(self.translator.langpath, pname)
            self.plural_file = pname
        else:
            self.plural_language = 'default'
            self.nplurals = DEFAULT_NPLURALS
            self.get_plural_id = DEFAULT_GET_PLURAL_ID
            self.construct_plural_form = DEFAULT_CONSTRUCT_PLURAL_FORM
            self.pmtime = 0
            self.plural_file = None

    def _read_t(self):
        if self.filename is None:
            return {}
        return read_dict(self.filename)

    @cachedprop
    def _t(self):
        return self._read_t()

    @property
    def t(self):
        if self.cached:
            return self._t
        return self._read_t()

    def set(self, key, message):
        # [WARN]: if it's not cached, is safe?
        self.t[key] = message
        if self.writable and self.filename:
            write_dict(self.filename, self.t)

    def get(self, key):
        return self.t.get(key)

    def get_default(self, key, message):
        if self.translator.default_translator is self:
            return message
        return self.translator.default_translator.t.get(key, message)

    def _read_pl(self):
        if self.plural_file is None or self.pmtime == 0:
            return {}
        return read_plural_dict(self.plural_file)

    @cachedprop
    def _pl(self):
        return self._read_pl()

    @property
    def pl(self):
        if self.cached:
            return self._pl
        return self._read_pl()

    def plural(self, word, n):
        """ get plural form of word for number *n*
        args:
            word (str): word in singular
            n (numeric): number plural form created for

        returns:
            (str): word in appropriate singular/plural form
        """
        if int(n) == 1:
            return word
        elif word:
            id = self.get_plural_id(abs(int(n)))
            # id = 0 singular form
            # id = 1 first plural form
            # id = 2 second plural form
            # etc.
            if id != 0:
                forms = self.pl.get(word, [])
                if len(forms) >= id:
                    # have this plural form:
                    return forms[id - 1]
                else:
                    # guessing this plural form
                    forms += [''] * (self.nplurals - len(forms) - 1)
                    form = self.construct_plural_form(word, id)
                    forms[id - 1] = form
                    self.pl[word] = forms
                    if self.writable and self.plural_file:
                        write_plural_dict(self.plural_file,
                                          self.pl)
                    return form
        return word

    def get_t(self, message, prefix=u''):
        """
        use ## to add a comment into a translation string
        the comment can be useful do discriminate different possible
        translations for the same string (for example different locations)

        T(' hello world ') -> ' hello world '
        T(' hello world ## token') -> ' hello world '
        T('hello ## world## token') -> 'hello ## world'

        the ## notation is ignored in multiline strings and strings that
        start with ##. this is to allow markmin syntax to be translated
        """
        message = to_unicode(message)
        key = prefix + message
        mt = self.get(key)
        if mt is not None:
            return mt
        # we did not find a translation
        if message.find('##') > 0 and '\n' not in message:
            # remove comments
            message = message.rsplit('##', 1)[0]
        # guess translation same as original
        #self.t[key] = mt = self.default_t.get(key, message)
        mt = self.get_default(key, message)
        self.set(key, mt)
        return regex_backslash.sub(
            lambda m: m.group(1).translate(ttab_in), mt)

    def translate(self, message):
        if self.cached:
            return get_from_cache(
                self.filename, to_unicode(message),
                lambda: to_unicode(self.get_t(message)))
        return to_unicode(self.get_t(message))


#: The main translator object, responsible of creating elements and loading
#  application languages
class Translator(object):
    def __init__(self, app):
        self.app = app
        self.langpath = os.path.join(app.root_path, "languages")
        self.is_writable = app.language_write
        def_langs = app.language_default
        if def_langs is None:
            def_langs = []
        if not isinstance(def_langs, (tuple, list)):
            def_langs = [def_langs]
        self.TLanguages = {}
        self.set_current_languages(def_langs)
        self.build_accepted_translators()

    @property
    def cached(self):
        return not self.app.debug

    @cachedprop
    def _pl_info(self):
        return read_possible_languages(self.langpath)

    @property
    def possible_languages(self):
        """
        return info for selected language or dictionary with all
            possible languages info from languages/*.py
        """
        #: if translator is cached, it doesn't check for filesystem updates
        if not self.cached:
            return read_possible_languages(self.langpath)
        return self._pl_info

    @cachedprop
    def all_languages(self):
        return {
            lang: lang for lang in iterkeys(self.possible_languages)
            if lang != 'default'}

    def get_language_info(self, lang):
        return self.possible_languages.get(lang)

    def set_current_languages(self, languages):
        """
        set current AKA "default" languages
        setting one of this languages makes force() function
        turn translation off to use default language
        """
        #: get default language info from default.py/DEFAULT_LANGUAGE
        pl_info = self.get_language_info('default')
        #: pl_info[2] is the langfile_mtime, if it equals 0 it means
        #  app doesn't have a languages/default.py
        if pl_info[2] == 0:
            self.default_language_file = self.langpath
        else:
            self.default_language_file = os.path.join(self.langpath,
                                                      'default.py')
        #: set default languages
        self.current_languages = [pl_info[0]]
        self.add_translator(pl_info[0], self.default_language_file, True)
        self.default_translator = self.TLanguages[pl_info[0]]
        for lang in languages:
            if lang not in self.current_languages:
                self.TLanguages[lang] = self.default_translator
                self.current_languages.append(lang)

    def build_accepted_translators(self):
        for lang in self.all_languages.keys():
            if lang not in self.TLanguages:
                self.add_translator(
                    lang, os.path.join(self.langpath, lang + '.py'))

    def add_translator(self, language, filename, default=False):
        writable = not default and self.is_writable
        pl_info = self.get_language_info(language)
        if filename == self.langpath:
            self.TLanguages[language] = TLanguage(
                self, pl_info, writable=writable)
        else:
            self.TLanguages[language] = TLanguage(
                self, pl_info, filename=filename, writable=writable)

    def __call__(self, message, symbols={}, language=None):
        return TElement(self, message, symbols, language=language)

    def apply_filter(self, message, symbols={}, filter=None, ftag=None):
        def get_tr(message, prefix, filter):
            s = self.get_t(message, prefix)
            return filter(s) if filter else self.filter(s)
        if filter:
            prefix = '@' + (ftag or 'userdef') + '\x01'
        else:
            prefix = '@' + self.ftag + '\x01'
        message = get_from_cache(
            self.cache, prefix + message,
            lambda: get_tr(message, prefix, filter))
        if symbols or symbols == 0 or symbols == "":
            if isinstance(symbols, dict):
                symbols.update(
                    (key, htmlescape(value).translate(ttab_in))
                    for key, value in iteritems(symbols)
                    if not isinstance(value, NUMBERS))
            else:
                if not isinstance(symbols, tuple):
                    symbols = (symbols,)
                symbols = tuple(
                    value if isinstance(value, NUMBERS)
                    else htmlescape(value).translate(ttab_in)
                    for value in symbols)
            message = self.params_substitution(message, symbols)
        return asis(message.translate(ttab_out))

    #def M(self, message, symbols={}, language=None,
    #      lazy=None, filter=None, ftag=None):
    #    """
    #    get cached translated markmin-message with inserted parametes
    #    if lazy==True lazyT object is returned
    #    """
    #    if lazy is None:
    #        lazy = self.lazy
    #    if not language:
    #        if lazy:
    #            return lazyT(message, symbols, self, filter, ftag, True)
    #        else:
    #            return self.apply_filter(message, symbols, filter, ftag)
    #    else:
    #        try:
    #            otherT = self.otherTs[language]
    #        except KeyError:
    #            otherT = self.otherTs[language] = translator(self.request)
    #            otherT.force(language)
    #        return otherT.M(message, symbols, lazy=lazy)

    def params_substitution(self, lang, message, symbols):
        """
        substitute parameters from symbols into message using %.
        also parse %%{} placeholders for plural-forms processing.
        returns: string with parameters
        NOTE: *symbols* MUST BE OR tuple OR dict of parameters!
        """
        def sub_plural(m):
            """string in %{} is transformed by this rules:
               If string starts with  \\, ! or ? such transformations
               take place:

               "!string of words" -> "String of word" (Capitalize)
               "!!string of words" -> "String Of Word" (Title)
               "!!!string of words" -> "STRING OF WORD" (Upper)
               "\\!string of words" -> "!string of word"
                             (remove \\ and disable transformations)
               "?word?number" -> "word" (return word, if number == 1)
               "?number" or "??number" -> "" (remove number,
                                              if number == 1)
               "?word?number" -> "number" (if number != 1)
            """
            def sub_tuple(m):
                w, i = m.group('w', 'i')
                c = w[0]
                if c not in '!?':
                    return self.TLanguages[lang].plural(w,
                                                        symbols[int(i or 0)])
                elif c == '?':
                    (p1, sep, p2) = w[1:].partition("?")
                    part1 = p1 if sep else ""
                    (part2, sep, part3) = (p2 if sep else p1).partition("?")
                    if not sep:
                        part3 = part2
                    if i is None:
                        # ?[word]?number[?number] or ?number
                        if not part2:
                            return m.group(0)
                        num = int(part2)
                    else:
                        # ?[word]?word2[?word3][number]
                        num = int(symbols[int(i or 0)])
                    return part1 if num == 1 else part3 if num == 0 else part2
                elif w.startswith('!!!'):
                    word = w[3:]
                    fun = upper_fun
                elif w.startswith('!!'):
                    word = w[2:]
                    fun = title_fun
                else:
                    word = w[1:]
                    fun = cap_fun
                if i is not None:
                    return fun(self.TLanguages[lang].plural(word,
                               symbols[int(i)]))
                return fun(word)

            def sub_dict(m):
                w, n = m.group('w', 'n')
                c = w[0]
                n = int(n) if n.isdigit() else symbols[n]
                if c not in '!?':
                    return self.TLanguages[lang].plural(w, n)
                elif c == '?':
                    (p1, sep, p2) = w[1:].partition("?")
                    part1 = p1 if sep else ""
                    (part2, sep, part3) = (p2 if sep else p1).partition("?")
                    if not sep:
                        part3 = part2
                    num = int(n)
                    return part1 if num == 1 else part3 if num == 0 else part2
                elif w.startswith('!!!'):
                    word = w[3:]
                    fun = upper_fun
                elif w.startswith('!!'):
                    word = w[2:]
                    fun = title_fun
                else:
                    word = w[1:]
                    fun = cap_fun
                return fun(self.TLanguages[lang].plural(word, n))

            s = m.group(1)
            part = regex_plural_tuple.sub(sub_tuple, s)
            if part == s:
                part = regex_plural_dict.sub(sub_dict, s)
                if part == s:
                    return m.group(0)
            return part
        message = message % symbols
        message = regex_plural.sub(sub_plural, message)
        return message

    def get_best_language(self, lang):
        return self.all_languages.get(lang, self.current_languages[0])

    def translate(self, lang, message, symbols):
        lang = self.get_best_language(lang)
        message = self.TLanguages[lang].translate(message)
        if symbols or symbols == 0 or symbols == "":
            if isinstance(symbols, dict):
                symbols.update(
                    (
                        key, to_unicode(value).translate(ttab_in)
                        if value else u'')
                    for key, value in iteritems(symbols)
                    if not isinstance(value, NUMBERS))
            else:
                if not isinstance(symbols, tuple):
                    symbols = (symbols,)
                symbols = tuple(
                    value if isinstance(value, NUMBERS)
                    else (
                        to_unicode(value).translate(ttab_in) if value else u'')
                    for value in symbols)
            message = self.params_substitution(lang, message, symbols)
        return message.translate(ttab_out)
