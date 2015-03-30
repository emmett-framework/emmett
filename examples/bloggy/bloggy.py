from weppy import App, request, session, url, redirect, abort
from weppy.dal import DAL, Field, Model, AuthModel
from weppy.validators import isntEmpty
from weppy.tools import Auth, requires
from weppy.sessions import SessionCookieManager


app = App(__name__)


#: define models
class User(AuthModel):
    # will create "auth_user" table and groups/permissions ones
    pass


class Post(Model):
    tablename = "posts"
    fields = [
        Field("author", "reference auth_user",
              default=lambda: session.auth.user.id),
        Field("title"),
        Field("text", "text"),
        Field("date", "datetime", default=lambda: request.now)
    ]
    visibility = {
        "author": (False, False),
        "date": (False, False)
    }
    validators = {
        "title": isntEmpty(),
        "text": isntEmpty()
    }


class Comment(Model):
    tablename = "comments"
    fields = [
        Field("author", "reference auth_user",
              default=lambda: session.auth.user.id),
        Field("post", "reference posts"),
        Field("text", "text"),
        Field("date", "datetime", default=lambda: request.now)
    ]
    visibility = {
        "author": (False, False),
        "post": (False, False),
        "date": (False, False)
    }
    validators = {
        "text": isntEmpty()
    }

#: init db and auth
db = DAL(app)
auth = Auth(app, db, usermodel=User)
db.define_models([Post, Comment])


#: setup helping function
def setup():
    # create the user
    user = db.User.validate_and_insert(
        email="walter@massivedynamics.com",
        first_name="Walter",
        last_name="Bishop",
        password="pocketuniverse"
    )
    # create an admin group
    admins = auth.add_group("admin")
    # add user to admins group
    auth.add_membership(admins, user.id)

#: handlers
app.expose.common_handlers = [
    SessionCookieManager('Walternate'),
    db.handler, auth.handler
]


#: exposing functions
@app.expose("/")
def index():
    posts = db(db.Post.id > 0).select(orderby=~db.Post.date)
    return dict(posts=posts)


@app.expose("/post/<int:pid>")
def one(pid):
    def _validate_comment(form):
        # manually set post id in comment form
        form.vars.post = pid
    # get post and return 404 if doesn't exist
    post = db.Post(id=pid)
    if not post:
        abort(404)
    # get comments and create a form
    comments = db(db.Comment.post == post.id).select(orderby=~db.Comment.date)
    form = Comment.form(onvalidation=_validate_comment)
    return locals()


@app.expose("/new")
@requires(lambda: auth.has_membership('admin'), url('index'))
def new_post():
    form = Post.form()
    if form.accepted:
        redirect(url('one', form.vars.id))
    return dict(form=form)


@app.expose('/account(/<str:f>)?(/<str:k>)?')
def account(f, k):
    form = auth(f, k)
    return dict(form=form)
