from weppy import response

from starter_weppy import app, auth


@app.route("/")
def welcome():
    response.meta.title = "StarterWeppy"
    return dict()


@app.route('/account(/<str:f>)?(/<str:k>)?')
def account(f, k):
    response.meta.title = "StarterWeppy | Account"
    form = auth(f, k)
    return dict(req=f, form=form)
