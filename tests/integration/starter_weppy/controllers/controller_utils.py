from weppy import response, abort

from starter_weppy import app, auth


def not_auth():
    abort(403)


def is_admin():
    # So we can tweak the master "admin" group name/id in one place.
    return auth.has_membership('admin')


@app.on_error(404)
def error_404():
    response.meta.title = "StarterWeppy-404"
    return app.render_template("errors/404.haml")


@app.on_error(403)
def error_403():
    response.meta.title = "StarterWeppy-403"
    return app.render_template("errors/403.haml")


@app.on_error(500)
def error_500():
    response.meta.title = "StarterWeppy | Maintenance"
    return app.render_template("errors/500.haml")


@app.route()
def maintenance_check():
    # This is for testing / maintenance page development.
    abort(500)
