# -*- coding: utf-8 -*-

from weppy import App, session, now, url, redirect, abort
from weppy.orm import Database, Model, Field, belongs_to, has_many
from weppy.tools import requires
from weppy.tools.auth import Auth, AuthUser
from weppy.sessions import SessionCookieManager


app = App(__name__)
app.config.auth.single_template = True
app.config.auth.registration_verification = False
app.config.auth.hmac_key = "MassiveDynamicRules"


#: define models
class User(AuthUser):
    # will create "auth_user" table and groups/permissions ones
    has_many('posts', 'comments')


class Post(Model):
    belongs_to('user')
    has_many('comments')

    title = Field()
    text = Field('text')
    date = Field('datetime')

    default_values = {
        'user': lambda: session.auth.user.id,
        'date': now
    }
    validation = {
        'title': {'presence': True},
        'text': {'presence': True}
    }
    fields_rw = {
        'user': False,
        'date': False
    }


class Comment(Model):
    belongs_to('user', 'post')

    text = Field('text')
    date = Field('datetime')

    default_values = {
        'user': lambda: session.auth.user.id,
        'date': now
    }
    validation = {
        'text': {'presence': True}
    }
    fields_rw = {
        'user': False,
        'post': False,
        'date': False
    }


#: init db and auth
db = Database(app, auto_migrate=True)
auth = Auth(app, db, user_model=User)
db.define_models(Post, Comment)


#: setup helping function
def setup_admin():
    # create the user
    user = User.create(
        email="walter@massivedynamics.com",
        first_name="Walter",
        last_name="Bishop",
        password="pocketuniverse"
    )
    # create an admin group
    admins = auth.create_group("admin")
    # add user to admins group
    auth.add_membership(admins, user.id)
    db.commit()


@app.command('setup')
def setup():
    setup_admin()


#: pipeline
app.pipeline = [
    SessionCookieManager('Walternate'), db.pipe, auth.pipe
]


#: exposing functions
@app.route("/")
def index():
    posts = Post.all().select(orderby=~Post.date)
    return dict(posts=posts)


@app.route("/post/<int:pid>")
def one(pid):
    def _validate_comment(form):
        # manually set post id in comment form
        form.params.post = pid
    # get post and return 404 if doesn't exist
    post = Post.get(pid)
    if not post:
        abort(404)
    # get comments and create a form for commenting
    comments = post.comments(orderby=~Comment.date)
    form = Comment.form(onvalidation=_validate_comment)
    if form.accepted:
        redirect(url('one', pid))
    return locals()


@app.route("/new")
@requires(lambda: auth.has_membership('admin'), url('index'))
def new_post():
    form = Post.form()
    if form.accepted:
        redirect(url('one', form.params.id))
    return dict(form=form)


auth_routes = auth.module(__name__)
