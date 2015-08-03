"""
    weppy_04_upgrade
    ----------------

    A basic script which dumps 0.3 auth tables' contents and insert dumped
    data into 0.4 tables with correct structure.

    :copyright: (c) 2015 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import json
import os


def before_upgrade(app, db):
    dump = {}
    dump['users'] = db(db.auth_user.id > 0).select().as_list()
    dump['groups'] = db(db.auth_group.id > 0).select().as_list()
    dump['memberships'] = db(db.auth_membership.id > 0).select().as_list()
    dump['permissions'] = db(db.auth_permission.id > 0).select().as_list()
    dump['events'] = db(db.auth_event.id > 0).select().as_list()
    fpath = os.path.join(app.root_path, '03dump.json')
    dumpfile = open(fpath, 'w')
    json.dump(dump, dumpfile)
    dumpfile.close()
    print "done"


def after_upgrade(app, db, auth):
    fpath = os.path.join(app.root_path, '03dump.json')
    dumpfile = open(fpath, 'w')
    data = json.load(dumpfile)
    dumpfile.close()
    for r in data['users']:
        auth.table_user.insert(**r)
    for r in data['groups']:
        auth.table_group.insert(**r)
    for r in data['memberships']:
        r['user'] = r['user_id']
        r['authgroup'] = r['group_id']
        del r['user_id']
        del r['group_id']
        auth.table_membership.insert(**r)
    for r in data['permissions']:
        r['authgroup'] = r['group_id']
        del r['group_id']
        auth.table_permission.insert(**r)
    for r in data['events']:
        r['user'] = r['user_id']
        del r['user_id']
        auth.table_event.insert(**r)
    try:
        for name in [
                'auth_user', 'auth_group', 'auth_membership',
                'auth_permission', 'auth_event']:
            db._adapter.execute('DROP TABLE %s;' % name)
    except:
        pass
    print "done"
