# -*- coding: utf-8 -*-

from emmett import App, session, now, url, redirect, abort
from emmett.orm import Database, Model, Field, belongs_to, has_many
from emmett.tools import requires
from emmett.tools.auth import Auth, AuthUser
from emmett.sessions import SessionManager


app = App(__name__)
app.config.auth.single_template = True
app.config.auth.registration_verification = False
app.config.auth.hmac_key = "november.5.1955"


#: define models
class User(AuthUser):
    # will create "auth_user" table and groups/permissions ones
    has_many('posts', 'comments')


class Post(Model):
    belongs_to('user')
    has_many('comments')

    title = Field()
    text = Field.text()
    date = Field.datetime()

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

    text = Field.text()
    date = Field.datetime()

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
db = Database(app)
auth = Auth(app, db, user_model=User)
db.define_models(Post, Comment)


#: setup helping function
def setup_admin():
    with db.connection():
        # create the user
        user = User.create(
            email="doc@emmettbrown.com",
            first_name="Emmett",
            last_name="Brown",
            password="fluxcapacitor"
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
    SessionManager.cookies('GreatScott'), db.pipe, auth.pipe
]


#: exposing functions
@app.route("/")
async def index():
    posts = Post.all().select(orderby=~Post.date)
    return dict(posts=posts)


@app.route("/post/<int:pid>")
async def one(pid):
    def _validate_comment(form):
        # manually set post id in comment form
        form.params.post = pid
    # get post and return 404 if doesn't exist
    post = Post.get(pid)
    if not post:
        abort(404)
    # get comments and create a form for commenting
    comments = post.comments(orderby=~Comment.date)
    form = await Comment.form(onvalidation=_validate_comment)
    if form.accepted:
        redirect(url('one', pid))
    return locals()


@app.route("/new")
@requires(lambda: auth.has_membership('admin'), url('index'))
async def new_post():
    form = await Post.form()
    if form.accepted:
        redirect(url('one', form.params.id))
    return dict(form=form)


auth_routes = auth.module(__name__)
