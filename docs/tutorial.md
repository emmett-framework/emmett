Tutorial
========

So, you want to develop an application with Python and weppy, huh? We should
start with an example. 

We will create a simple microblog application, using weppy and a database.
SQLite comes out of the box with Python, so you won't need to download anything
other than weppy.

If you want the full source code in advance, check out the [example 
source](https://github.com/gi0baro/weppy/tree/release/examples/bloggy).

Bloggy: a micro blog
--------------------

We will call our blogging application *bloggy* and, basically, we want it to do
the following things:

* let users sign up and then sign in and out with their own credentials
* let only an admin user add new posts (consisting of a title and a text body)
* show all posts' titles in reverse order (newest on top) to everyone on the index page
* show the entire post on a specific page and allow registered users to comment

> – hem, dude.. seems like quite a lot of stuff for a "micro" blogging application   
> – *relax! you'll see that every feature will be short work with weppy*

Application structure
---------------------

Let's start from the basis, and create this directory structure:

```
/bloggy
    /static
    /templates
```

The *bloggy* folder won't be a python package. It's just somewhere to drop our
files. In the next steps, we will build our application with a single python file,
since it's small. The files inside the *static* folder will be available to
clients via HTTP. This is the place where you should put the CSS and JavaScript
files. The templates you're gonna create later in this tutorial will go in the
*templates* directory instead.

After you create the above folders, create a *bloggy.py* file inside your
*bloggy* application:

```python
from weppy import App

app = App(__name__)
```

so you should end with this directory structure:

```
/bloggy
    bloggy.py
    /static
    /templates
```

Now you can test your application simply issuing the following command (inside
the *bloggy* folder):

```bash
> weppy --app bloggy.py run
```

and you will see a message telling you that the server has started, along with
the address at which you can access it.

When you head over to the server in your browser, you will get a 404 Page Not
Found error because we don’t have any exposed function yet. However, we will
attend to that a little later on. First, we should create the database for the
application.

Database schema
---------------

The first step in coding our application is to create the database schema.
In bloggy, we need at least 4 tables:

* The users table
* A users' groups/permission table (to allow only the admin user to write posts)
* The posts table
* The comments table

Now, this might sounds complicated, but it's actually not. In fact, we can skip
all the schema about users since weppy includes an authorization module that
creates the tables we need automatically.

So, how will we build our schema? We will use the default `AuthUser` class for
the users table and authorization system, and the `Model` class for the other
tables:

```python
from weppy import request, session
from weppy.dal import Field, Model, belongs_to, has_many
from weppy.tools.auth import AuthUser

class User(AuthUser):
    # will create "users" table and groups/permissions ones
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
```

That's it. You can see we defined some *relations* between our models,
which will be a relationships between the tables, so we have these conditions:

* a post always have one author, and an author can have many posts
* a comment always have one author and always refers to one post,
and a post can have many comments

Moreover, we have set some *default* values (like the dates and the authors) and
we have hidden some fields in forms to the users: it would be pointless to have
an *user* field if the user could set this value to whatever he or she wanted.
Accordingly, we're telling to weppy to auto-set those values to the right ones.

We've also added some validation, so we can prevent users from sending empty
posts or comments.

Initialize the database and the auth module
-------------------------------------

We've defined our schema, so now it's time to add the database and the
authorization system to bloggy. It's as simple as writing:

```python
from weppy import DAL
from weppy.tools import Auth

db = DAL(app)
auth = Auth(app, db, usermodel=User)
db.define_models(Post, Comment)
```

But, wait, how do we add an admin user who can write posts? We can write a
`setup` function which allows us to do that. Let's write:

```python
@app.command('setup')
def setup():
    # create the user
    user = User.create(
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
```

The code is quite self-explanatory: it will add an user who can sign in with the
"walter@massivedynamics.com" email and "pocketuniverse" as their password,
then it creates an admin group and adds the *Walter* user to this group.

Also, notice that we added the `@app.command` decorator, which allow us to run
our setup function using the *weppy* command shell:

```bash
> weppy --app bloggy.py setup
```

Now that the backend is ready, we can prepare to write and *expose* our functions.

Exposing functions
------------------

Before we can start writing the functions that will handle the clients' requests,
we need to add the database and authorization **handlers** to our application,
so that we can use them with our functions following the request flow.

Moreover, to use the authorization module, we need to add a **sessions manager**
to the application's handlers, too. In this tutorial, cookie support 
for session will be enough, and we will use "Walternate" as a secret key
for encrypting cookies.

```python
from weppy.sessions import SessionCookieManager
app.common_handlers = [
    SessionCookieManager('Walternate'),
    db.handler,
    auth.handler
]
```

Then, we can start writing the function for our index page, which will list all
the posts in reverse chronological order.

```python
@app.route("/")
def index():
    posts = Post.all().select(orderby=~Post.date)
    return dict(posts=posts)
```

Since this list will only show up the posts' titles, we also write a function
to retrieve details for a single post:

```python
from weppy import abort

@app.route("/post/<int:pid>")
def one(pid):
    def _validate_comment(form):
        # manually set post id in comment form
        form.params.post = pid
    # get post and return 404 if doesn't exist
    post = Post.get(pid)
    if not post:
        abort(404)
    # get comments and create a form
    comments = post.comments(orderby=~Comment.date)
    form = Comment.form(onvalidation=_validate_comment)
    if form.accepted:
        redirect(url('one', pid))
    return locals()
```

As you can see, the `one` function will show the post text, the comments users
have written about it, and a form that allows users to add new comments.

We also need to expose a function to write posts, and it will be available only
to users in the "admin" group, thanks to the `requires` decorator:

```python
from weppy import redirect, url
from weppy.tools import requires

@app.route("/new")
@requires(lambda: auth.has_membership('admin'), url('index'))
def new_post():
    form = Post.form()
    if form.accepted:
        redirect(url('one', form.params.id))
    return dict(form=form)
```

If a user tries to open the "/new" address without being a member of the *admin*
group, weppy will redirect them to the index page.

Finally, we should expose an *account* function to let users sign up and sign in
on bloggy:

```python
@app.route('/account(/<str:f>)?(/<str:k>)?')
def account(f, k):
    form = auth(f, k)
    return dict(form=form)
```

Now that we have all the main code of our application ready to work, we need the
templates to render the content to the clients.

The templates
-------------

We should create a template for every function we exposed. However, since the
weppy templating system supports blocks and nesting, and we don't really want 
to repeat ourselves when writing code, we will start with a main layout file
under *templates/layout.html*, and we will extend it with the functions' templates:

```html
<!DOCTYPE html>
<html>
    <head>
        <title>Bloggy</title>
        {{include_meta}}
        {{include_helpers}}
        {{include_static 'style.css'}}
    </head>
    <body>
        <div class="page">
            <a href="/" class="title"><h1>Bloggy</h1></a>
            <div class="nav">
            {{if not current.session.auth:}}
                <a href="{{=url('account', 'login')}}">log in</a>
            {{else:}}
                <a href="{{=url('account', 'logout')}}">log out</a>
            {{pass}}
            </div>
            {{block main}}
            {{include}}
            {{end}}
        </div>
    </body>
</html>
```

All the templates we will create from now, will start with an `extend` instruction.
Their contents will be injected on the `include` instruction of the main layout.

Starting with *index.html* (which will be used with our `index` function):

```html
{{extend 'layout.html'}}

<a href="{{=url('new_post')}}">Create a new post</a>
<ul class="posts">
{{for post in posts:}}
    <li>
        <h2>{{=post.title}}</h2>
        <a href="{{=url('one', post.id)}}">Read more</a>
        <hr />
    </li>
{{pass}}
{{if not posts:}}
    <li><em>No posts here so far.</em></li>
{{pass}}
</ul>
```

Then, the *one.html* template which, is the most complex:

```html
{{extend 'layout.html'}}

<h1>{{=post.title}}</h1>
{{=post.text}}
<br />
<hr />
<h4>Comments</h4>
{{if current.session.auth:}}
<h5>Write a comment:</h5>
{{=form}}
{{pass}}
<ul class="comments">
{{for comment in comments:}}
    <li>
        {{=comment.text}}
        <br />
        <em>by {{=comment.user.first_name}} on {{=comment.date}}</em>
    </li>
{{pass}}
{{if not comments:}}
    <li><em>No comments here so far.</em></li>
{{pass}}
</ul>
```

The two remaining templates are simpler and similar, since they will only
show one form each. So, the first, *new_post.html*, will be just:

```html
{{extend 'layout.html'}}

<h1>Create a new post</h1>
{{=form}}
```

and *account.html* will be:

```html
{{extend 'layout.html'}}

<h1>Account</h1>
{{=form}}
```

Some styling
------------

Now that everything works, it's time to add some style to bloggy. 
We just create a *style.css* file inside *static* folder and write down
something like this:

```css
body           { font-family: sans-serif; background: #eee; }
a, h1, h2      { color: #377ba8; }
h1, h2, h4, h5 { font-family: 'Georgia', serif; }
h1             { border-bottom: 2px solid #eee; }
h2             { font-size: 1.2em; }

.page          { margin: 2em auto; width: 35em; border: 5px solid #ccc;
                 padding: 0.8em; background: white; }
.title         { text-decoration: none; }
.posts         { list-style: none; margin: 0; padding: 0; }
.posts li      { margin: 0.8em 1.2em; }
.posts li h2   { margin-left: -1em; }
.posts li hr   { margin-left: -0.8em; }
.nav           { text-align: right; font-size: 0.8em; padding: 0.3em;
                 margin-bottom: 1em; background: #fafafa; }
```

Go ahead
--------

You've completed the tutorial, with a new blogging application
written in very few lines, and simple ones at that. You should be more confident
with the weppy workflow and its syntax, so feel free to start writing your own applications!

To explore all the features of weppy, and better understand what you've done in
this tutorial, you should read the [complete documentation](./),
and try to expand this simple application with more features,
so that it can better meet your needs.
