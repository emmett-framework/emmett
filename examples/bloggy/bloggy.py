from weppy import App, request, session, url, redirect, abort
from weppy.dal import DAL, Field, Model, belongs_to, has_many
from weppy.tools import requires
from weppy.tools.auth import Auth, AuthUser
from weppy.sessions import SessionCookieManager


app = App(__name__)


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
        'date': lambda: request.now
    }
    validation = {
        'title': {'presence': True},
        'text': {'presence': True}
    }
    form_rw = {
        'user': False,
        'date': False
    }


class Comment(Model):
    belongs_to('user', 'post')

    text = Field('text')
    date = Field('datetime')

    default_values = {
        'user': lambda: session.auth.user.id,
        'date': lambda: request.now
    }
    validation = {
        'text': {'presence': True}
    }
    form_rw = {
        'user': False,
        'post': False,
        'date': False
    }

#: init db and auth
db = DAL(app)
auth = Auth(app, db, usermodel=User)
db.define_models(Post, Comment)


#: setup helping function
@app.command('setup')
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
    db.commit()

#: handlers
app.expose.common_handlers = [
    SessionCookieManager('Walternate'),
    db.handler, auth.handler
]


#: exposing functions
@app.expose("/")
def index():
    posts = db(Post.id > 0).select(orderby=~Post.date)
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
    # get comments and create a form for commenting
    comments = post.comments(orderby=~Comment.date)
    form = Comment.form(onvalidation=_validate_comment)
    if form.accepted:
        redirect(url('one', pid))
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
