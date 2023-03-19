Tutorial
========

So, you want to develop an application with Python and Emmett, huh? We should
start with an example.

We will create a simple microblog application, using Emmett and a database.
SQLite comes out of the box with Python, so you won't need to download anything
other than Emmett.

If you want the full source code in advance, check out the [example source](https://github.com/emmett-framework/emmett/tree/master/examples/bloggy).

Bloggy: a micro blog
--------------------

We will call our blogging application *bloggy* and, basically, we want it to do
the following things:

* let users sign up and then sign in and out with their own credentials
* let only an admin user add new posts (consisting of a title and a text body)
* show all posts' titles in reverse order (newest on top) to everyone on the index page
* show the entire post on a specific page and allow registered users to comment

> – hem, dude.. seems like quite a lot of stuff for a "micro" blogging application   
> – *relax! you'll see that every feature will be short work with Emmett*

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

After you create the above folders, create an *app.py* file inside your
*bloggy* application:

```python
from emmett import App

app = App(__name__)
```

so you should end with this directory structure:

```
/bloggy
    app.py
    /static
    /templates
```

Now you can test your application simply issuing the following command (inside
the *bloggy* folder):

```bash
> emmett develop
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
all the schema about users since Emmett includes an authorization module that
creates the tables we need automatically.

So, how will we build our schema? We will use the default `AuthUser` class for
the users table and authorization system, and the `Model` class for the other
tables:

```python
from emmett import session, now
from emmett.orm import Model, Field, belongs_to, has_many
from emmett.tools.auth import AuthUser

class User(AuthUser):
    # will create "users" table and groups/permissions ones
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
```

That's it. You can see we defined some *relations* between our models,
which will be a relationships between the tables, so we have these conditions:

* a post always have one author, and an author can have many posts
* a comment always have one author and always refers to one post,
and a post can have many comments

Moreover, we have set some *default* values (like the dates and the authors) and we have hidden some fields in forms to the users using the `fields_rw` attribute: it would be pointless to have an *user* field if the user could set this value to whatever he or she wanted. Accordingly, we're telling to Emmett to auto-set those values to the right ones.

We've also added some validation, so we can prevent users from sending empty
posts or comments.

> **Note:** as you can see we imported the `now` method for the deault values of the datetime fields. This method can be quite useful since it will return alternatively the time of the request or the system current time, depending on the context. You can safely use it in your application whenever you need the actual time and you have no ensurance a request context is available.

Initialize the database and the auth module
-------------------------------------------

We've defined our schema, so now it's time to add the database and the authorization system to bloggy. First, let's configure the auth module a bit:

```python
app.config.auth.single_template = True
app.config.auth.registration_verification = False
app.config.auth.hmac_key = "november.5.1955"
```

These options allow us to use a single template file for everything regarding the auth, and, since we're writing just a simple application, prevent it to use a mailer system for validating our users. The `hmac_key` will be used to crypt the passwords into our database.

Now, we can write down the code to use the database and the auth. Just the next few lines are enough:

```python
from emmett.orm import Database
from emmett.tools import Auth

db = Database(app)
auth = Auth(app, db, user_model=User)
db.define_models(Post, Comment)
```

As you can see we configured the database to use the models we defined, and passed our `User` model to the auth module. Now it's time to generate our first [migration](./orm/migrations):

```bash
> emmett migrations generate -m "First migration"
```

This will produce a migration file inside the *migrations* folder, that will apply all the needed schema changes to our database. Let's apply them:

```bash
> mkdir -p databases
> emmett migrations up
```

Now the database of our application is ready. But, wait, how do we add an admin user who can write posts? We can write a `setup` function which allows us to do that. Let's write:

```python
@app.command('setup')
def setup():
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
```

The code is quite self-explanatory: it will add an user who can sign in with the *doc@emmettbrown.com* email and *fluxcapacitor* password, then it creates an admin group and adds the *Emmett* user to this group.

Also, notice that we added the `@app.command` decorator, which allow us to run our setup function using the *emmett* command shell:

```bash
> emmett setup
```

Now that the backend is ready, we can prepare to write and *expose* our functions.

Exposing routes
---------------

Before we can start writing the functions that will handle the clients' requests, we need to add the database and authorization **pipes** to our application, so that we can use them with our functions following the request flow.

Moreover, to use the authorization module, we need to add a **session manager** to the application's pipeline, too. In this tutorial, cookie support for session will be enough, and we will use *GreatScott* as a secret key for encrypting cookies.

```python
from emmett.sessions import SessionManager
app.pipeline = [
    SessionManager.cookies('GreatScott'),
    db.pipe,
    auth.pipe
]
```

Then, we can start writing the function for our index page, which will list all
the posts in reverse chronological order.

```python
@app.route("/")
async def index():
    posts = Post.all().select(orderby=~Post.date)
    return dict(posts=posts)
```

Since this list will only show up the posts' titles, we also write a function
to retrieve details for a single post:

```python
from emmett import abort

@app.route("/post/<int:pid>")
async def one(pid):
    def _validate_comment(form):
        # manually set post id in comment form
        form.params.post = pid
    # get post and return 404 if doesn't exist
    post = Post.get(pid)
    if not post:
        abort(404)
    # get comments
    comments = post.comments(orderby=~Comment.date)
    # and create a form for commenting if the user is logged in
    if session.auth:
        form = await Comment.form(onvalidation=_validate_comment)
        if form.accepted:
            redirect(url('one', pid))
    return locals()
```

As you can see, the `one` function will show the post text, the comments users
have written about it, and a form that allows users to add new comments.

We also need to expose a function to write posts, and it will be available only
to users in the "admin" group, thanks to the `requires` decorator:

```python
from emmett import redirect, url
from emmett.tools import requires

@app.route("/new")
@requires(lambda: auth.has_membership('admin'), url('index'))
async def new_post():
    form = await Post.form()
    if form.accepted:
        redirect(url('one', form.params.id))
    return {'form': form}
```

If a user tries to open the "/new" address without being a member of the *admin* group, Emmett will redirect them to the index page.

Finally, we should expose the auth module routes, in order to let users sign up and sign in on bloggy. Since the auth module provides a convenient application module, we can just initialize it:

```python
auth_routes = auth.module(__name__)
```

and the auth module will expose everything for us.

Now that we have all the main code of our application ready to work, we need the templates to render the content to the clients.

The templates
-------------

We should create a template for every function we exposed. However, since the
Renoir templating system supports blocks and nesting, and we don't really want
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
        <a href="{{=url('auth.login')}}">log in</a>
        {{else:}}
        <a href="{{=url('auth.logout')}}">log out</a>
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

The remaining template for our blogging app is the one for the posts creation, that will show the form. It's the simplest template since we can just write down in *new_post.html* these lines:

```html
{{extend 'layout.html'}}

<h1>Create a new post</h1>
{{=form}}
```

We still need a template for the auth module. We should create an *auth* folder inside the templates one, and, since we configured the module to use just one template, we can write down these lines in the *auth.html* file inside it:

```html
{{extend 'layout.html'}}

<h1>Account</h1>

{{for flash in current.response.alerts(category_filter='auth'):}}
    <div class="flash_message">{{=flash}}</div>
{{pass}}

{{=form}}
```

As you can see, the only difference from the template we wrote before to create new posts are the lines to *flash* messages from the auth module. This will be quite handy to display errors or notify the user.

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
with the Emmett workflow and its syntax, so feel free to start writing your own applications!

To explore all the features of Emmett, and better understand what you've done in
this tutorial, you should read the [complete documentation](./),
and try to expand this simple application with more features,
so that it can better meet your needs.
