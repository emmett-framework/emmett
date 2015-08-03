# -*- coding: utf-8 -*-
"""
    weppy.tools.auth.helpers
    ------------------------

    Provides helpers for the authorization system.

    :copyright: (c) 2015 by Giovanni Barillari

    Based on the web2py's auth module (http://www.web2py.com)
    :copyright: (c) by Massimo Di Pierro <mdipierro@cs.depaul.edu>

    :license: LGPLv3 (http://www.gnu.org/licenses/lgpl.html)
"""

from ...globals import request
from ...http import redirect


def callback(actions, form, tablename=None):
    if actions:
        if tablename and isinstance(actions, dict):
            actions = actions.get(tablename, [])
        if not isinstance(actions, (list, tuple)):
            actions = [actions]
        [action(form) for action in actions]


def call_or_redirect(f, *args):
    if callable(f):
        redirect(f(*args))
    else:
        redirect(f)


def replace_id(u, form):
    if u:
        u = u.replace('[id]', str(form.vars.id))
        if u[0] == '/' or u[:4] == 'http':
            return u
    return '/account'+u


def get_vars_next():
    nextv = request.vars._next
    if isinstance(nextv, (list, tuple)):
        nextv = nextv[0]
    return nextv
