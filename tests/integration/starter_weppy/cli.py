"""
Usage:   weppy --app=starter_weppy <command>
Example: weppy --app=starter_weppy shell
"""
from starter_weppy import app


@app.cli.command('routes')
def print_routing():
    print(app.route.routes_out)


@app.cli.command('get_users')
def print_users():
    from starter_weppy import db
    from starter_weppy.models.user import User
    rows = db(User.email).select()
    for row in rows:
        print(row)
