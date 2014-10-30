
Getting started
===============

Ready to get started with weppy? This guide gives a good introduction to the framework.

An 'hello world' application
----------------------------
How a minimal application would look like in weppy?

```python
from weppy import App
app = App(__name__)

@app.expose("/")
def hello():
 return "Hello world!"

if __name__ == "__main__":
 app.run()
```

Here it is. Save it as *hello.py* and run it with your python interpreter:

```bash
$ python hello.py
App running on 127.0.0.1:8000
```

Now if you go to [http://127.0.0.1:8000](http://127.0.0.1:8000) you should see your 'Hello world!' message.

Expose and routing
------------------
As you seen from the 'Hello world' example, we have *exposed* the `hello()` function. What does it mean?

Actually it's quite simple: the expose decorator of the application object is used to define the routing of your app.

> – Wait, you mean there's no need of a routing table?   
> – *Nope.*   
> – And how should I define url variables, HTTP methods, ecc.?   
> – *Just use the expose decorator and his parameters.*   

In fact, `expose()` accepts different parameters. But let we proceed in order, starting with variables rules for routing your functions.

### Variable rules
To add variable parts to an URL you can mark these special sections as `<type:variable_name>` and the variables will be passed as a keyword argument to your functions. Let's see some examples:

```python
@app.expose('/user/<str:username>')
def user(username):
    return "Hello %s" % username

@app.expose('/double/<int:number>')
def double(number):
    return "%d * 2 = %d" % (number, number*2)
```

It's quite simple, isn't it? And which are the types of variables you can use? Here is the complete list:

| type | specification |
|---|---|
| int | accepts integers |
| str | accepts strings |
| date | accepts date strings in format *YYYY-MM-DD* |
| alpha | accepts strings containing only literals |
| any | accepts any path (also with slashes) |

So basically, if we try to open the url for the `double` function of the last example with a string, like '/double/foo', it won't match and weppy will return a 404 error.

> – Ok, fine. But, what if I want a conditional argument for my function?

Just write the url using the regex notation:

```python
@app.expose("/profile(/<int:user_id>)?")
def profile(user_id):
    if user_id:
        # get requested user
    else:
        # load current logged user profile
```
as you thought, when conditional arguments are not given in the requested url, your function's parameters will be `None`.

Now, it's time to see the `methods` parameter of `expose()`

### HTTP methods
HTTP knows different methods for accessing URLs. By default, a route only answers to GET and POST requests, but that can be changed by providing the methods argument to the `expose()` decorator. For example:

```python
@app.expose("/onlyget", methods="get")
def f():
    # code

@app.expose("/post", methods=["post", "delete"])
def g():
    # code
```

If you have no idea of what an HTTP method is, don't worry, [Wikipedia has good informations](http://en.wikipedia.org/wiki/Hypertext_Transfer_Protocol#Request_methods) about them.

> – Ok, I got it. What else can I do with expose?

Since this is a *quick overview* over weppy, you would check out the [appropriate chapter](./routing) of the documentation for the complete list of parameters accepted by the `expose()` decorator.

Let's we see how to build urls on our routing rules.

### Building URLs
Weppy provide a useful method to create urls, let's see how it works:

```python
from weppy import App, url
app = App(__name__)

@app.expose("/")
def index():
    # code

@app.expose("/anotherurl")
def g():
    #code

@app.expose("/find/<str:a>/<str:b>")
def f(a, b):
    # code

@app.expose("/post/<int:id>/edit")
def edit(id):
    # code

a = url('index')
b = url('g', vars={'u': 2})
c = url('f', ['foo', 'bar'])
d = url('edit', 123)
```
The above urls `a`, `b`, `c` and `d` will be respectively converted to:
* /
* /anotherurl?u=2
* /find/foo/bar
* /post/123/edit

which is quite handy instead of remember all the rules and manually write the links.

#### Static files
Quite often you will need to link static contents (images, CSS, JavaScripts) into your application. You would create a folder called *static* in your package or next to your module and it will be available at */static* on the application.

To generate URLs for static files, use the special `static` first argument:

```python
url('static', 'js/common.js')
```
that will point to the file in *static/js/common.js*

> – but maybe I can write directly */static/js/common.js* instead of using `url()` function?

Obviously you can. But weppy provide some useful stuffs on static files urls, like languages and versioning which are automatically applied based on you application configuration. You can find more information in the [appropriate chapter](./routing) of the documentation.

Rendering the output
--------------------
Now that you've discovered how weppy core works, let's find out how to render our content. We will see how to generate an HTML response with a template and how to generate a JSON response.

### The templating system
weppy provides the same templating system of *web2py*, which means that you can use python code directly into your HTML files.
Let's see it with an example. We can make a new application with this structure:

```
/myapp.py
/templates
    echo.html
```
with *myapp.py* looking like this:

```python
from weppy import App
app = App(__name__)

@app.expose("/<str:msg>")
def echo():
    return dict(message=msg)
```
and *echo.html*:

```html
<html>
    <body>
        {{=message}}
    </body>
</html>
```
> – wait, the `message` I've put in the template is the returned value from my `echo()` function?   
> – *you got it!*

The dictionary returned by your functions is the *context* of the template, in which you can insert the values defined in python code.
In addition, since everything you write inside `{{ }}` brackets is evaluated as normal python code you can easily generate html with conditions and cycles:

```html
<div class="container">
{{for post in posts:}}
    <div class="post">{{=post.text}}</div>
{{pass}}
</div>
{{if user_logged_in:}}
<div class="cp">User cp</div>
{{pass}}
```
As you can see the only difference between the weppy template and a pure python code is that you have to write `pass` after the statements to tell weppy where the python block ends – normally we have indentation under python, but we can't have it under HTML.

The templating system has many more features: explore them in the [appropriate chapter](./templates) of the documentation.

### Other rendering options
Quite often you would need to render output of your functions in different formats than HTML, for example JSON.

weppy can help you with the *service* decorator:

```python
from weppy import App
from weppy.tools import service

app = App(__name__)

@app.expose("/json")
@service.json
def f():
    l = [1, 2, {'foo': 'bar'}]
    return dict(status="OK", data=l}
```
The output will be a JSON object with the converted content of your python dictionary:

```json
{
    "status": "OK",
    "data": [
        1,
        2,
        {
            "foo": "bar",
        }
    ]
}
```

The `service` module has other helpers, like *xml* format: go further in the [Services chapter](#) of the documentation.

Dealing with requests
---------------------
Now let's try to go somewhere deeper in weppy core logic.

> – How can my application react to requests of a client?   
> – *you can start with the `request` object*

### The request object
You can access the weppy's  `request` object just with an import:

```python
from weppy import request
```
It contains useful information about the current processing request, let's see some of them:

| attribute | description |
| --- | --- |
| scheme | could be *http* or *https*|
| method | the request HTTP method |
| now | a python datetime object created with request|
| vars | an object containing url params |

Let's focus on `request.vars` object, and understand it with an example:

```python
from weppy import App, request

app = App(__name__)

@app.expose("/post/<int:id>")
def post(id):
    editor = request.vars.editor
    if editor == "markdown":
        # code
    elif editor == "html":
        # code
    #..
```
Now, when a client call the url */post/123?editor=markdown*, the `editor` parameter will be mapped into `request.vars` and we can access its value simply calling the parameter name as an attribute.

> – wait, what happens if client call */post/123* and my app try to access *request.vars.editor* which is not in the url?

Simple, the attribute will be `None`, so it's completely safe to call it, it wont raise an exception.

More information about the `request` object could be found in the [Request chapter](./request) of the documentation.

### Handlers: perfoming operations with requests

> – What if I want to do something before and after the request?   
> – *You can use an Handler*.

weppy uses Handlers to perform operations before and after running the functions defined with your routing rules.
Let's see how to create one of them:

```python
from weppy import Handler

class MyHandler(Handler):
    def on_start(self):
        # code
    def on_success(self):
        # code
    def on_failure(self):
        # code
```
As you can see `Handler` provide methods to run your code before the request is processed by your function (with the `on_start` method) and after your function were executed, providing different methods depending on what happened on your function: if an exception is occurred weppy will call the `on_failure` method, otherwise the `on_success` method.

To register your handler to a function you just need to write:

```python
@app.expose("/url", handlers=[MyHandler()])
def f():
    #code
```
And if you need to register your handler to all your application functions, you can omit the handler from the `expose()` decorator writing instead:

```python
app.expose.common_handlers = [MyHandler()]
```

weppy also provides a Helper handler, which is designed to add helping methods to the templates. Explore the [Handlers chapter](./request#handlers-and-helpers) of documentation for more informations.

### Redirects and errors
Taking again the example given for the `request.vars`, we can add a redirect on the missing url param:

```python
from weppy import redirect, url

@app.expose("/post/<int:id>")
def post(id):
    editor = request.vars.editor
    if editor == "markdown":
        # code
    elif editor == "html":
        # code
    else:
        redirect(url('post', id, vars={'editor': 'markdown'}))
```
which means that when the `editor` var is missing we force the user to the markdown one.

Another way would be returning a 404 error:

```python
from weppy import abort

@app.on_error(404):
def not_found():
    #code

@app.expose("/post/<int:id>")
def post(id):
    editor = request.vars.editor
    if editor == "markdown":
        # code
    elif editor == "html":
        # code
    else:
        abort(404)
```
As you can see weppy applications can handle specific actions on HTTP errors. For more informations, checkout the [Error handling chapter](./request#errors-and-redirects) of the documentation.

Sessions
--------
An essential feature for a web application is the ability to store specific informations about the client from a request to the next one. Accordingly to this need, weppy provides another object beside the `request` one called `session`.
Session contents can be stored in a several ways, using file or redis for example. In this quick start we will see how to use the `session` and store its contents directly in the cookies of the client.

You need to use the `SessionCookieManager` handler provided by weppy:

```python
from weppy import App, session
from weppy.sessions import SessionCookieManager

app = App(__name__)
app.common_handlers = [SessionCookieManager('myverysecretkey')]

@app.expose("/")
def count():
    session.counter = (session.counter or 0) + 1
    return "This is your %d visit" % session.counter
```
The above code is quite simple: the app increments the counter every time the user visit the page and return this number to the user.
So basically, you can store a value to the user session and retrieve it whenever the session is kept.

> – and if I try to access an attribute not existent in session?   
> – *same as `request.vars`: the attribute will be `None` and you don't have to catch any exception*

More information and storing systems are available in the [Session chapter](./sessions) of the documentation.

Using a database
-----------------
> – Ok, what if I need to use a database in my application?   
> – *you can use the included DAL*

In fact, weppy integrates the Database Abstraction Layer (formerly *DAL*) of *web2py*, which gives you the ability to write the same code independently on which of the [available adapters](#) you want to use for deploy your app.
Let's see how it works:

```python
from weppy import App, DAL

app = App(__name__)
app.config.db.uri = "sqlite://storage.sqlite"

db = DAL(app)
db.define_table('post',
   Field('author'),
   Field('title'),
   Field('body', 'text'))

app.common_handlers = [db.handler]

@app.expose('/posts/<str:author>')
def post_by(author):
    posts = db(db.post.author == author).select()
    return dict(posts=posts)
```
The above code is quite simple: the `post_by()` function list posts from a specific author.
Let's reconstruct what we done in those simple lines:

* we added an *sqlite* database to our application, stored on file *storage.sqlite*
* we defined the table *post* and it's fields
* we did a select on the table querying the *author* column of *post* table

As you noticed, the fields defined for the table are available for queries as attributes, and calling *db* with a query as argument provides you a set on which you can do operations like the `select()`.

Let's focus a bit more on tables definition, because weppy provides also another way to do it: the models.

### The models layer
weppy provides a *models* structuring layer upon the web2py's DAL; we encourage the use of models since they make easy to organize all the database entities for the applications. Also, models provides an easier syntax to use many DAL's features, like fields computations.

So, how a weppy model look like? Using the upper example for the posts table in a blog, and adding more features, an example model would be like this:

```python
from markdown2 import markdown
from weppy.dal.models import Model, computation
from weppy.validators import IS_NOT_EMPTY

class Post(Model):
    tablename = "post"

    fields = [
        Field("author"),
        Field("title"),
        Field("body", "text"),
        Field("slug")
    ]

    representation = {
        "body": lambda row, value: markdown(value)
    }

    validators = {
        "title": IS_NOT_EMPTY(),
        "body": IS_NOT_EMPTY()
    }

    @computation('slug')
    def make_slug(self, row):
        # custom code to create the slug

```

As you can see, we added validators, representation rules (in this example we parse the markdown text in the database to produce html in templates), and a `computation` on the `slug` field.

To see more about DAL and dive into features and commands, read the complete documentation for the DAL available in the [appropriate chapter](#).

Creating forms
--------------
Once you have defined your data structures, you will need a method to insert and edit data in your application. The obvious once is using forms, and weppy provides two classes to help you: `Form` and `DALForm`.   
They works in the same way: the only difference, as names suggest, is that the second use DAL tables to create forms.

Let's see how to use them with an example:

```python
form weppy import Field, Form, DALForm
from weppy.validators import IS_IN_SET

# create a form without a database table
@app.expose('/form')
def a():
    name_field = Field('name')
    type_field = Field('type')
    type_field.requires = IS_IN_SET(['type1', 'type2'])
    simple_form = Form([name_field, type_field])
    if simple_form.accepted:
        #do something
    return dict(form=simple_form)

# create a form for db.post table
@app.expose('/dalform')
def b():
    form = DALForm(db.post)
    if form.accepted:
        #do something
    return dict(form=form)
```

As you can see the `Form` class accepts a list of fields for the input, and the `DALForm` takes a table.

> – Wait, and if I need to edit a record?   

You can pass the record as the second argument of `DALForm`

```python
record = db(db.post.id == someid).select().first()
form = DALForm(db.post, record)
```

or, if you prefer, you can use a record id:

```python
form = DALForm(db.post, record_id=someid)
```

weppy forms has many options, for example you can set an `onvalidation` method to run additional validation besides the fields' requirements; you can also customize the form rendering and styling. Check out the [Forms chapter](#) of the documentation and the [weppy BS3 extension](#) which add bootstrap3 style to your forms.

> – Ok, so if I need a form to provide login to my users, I can write my user table or model and then use the Form class with, for example, the *email* and *password* fields?   
> – *Yes. Or you can use the included authorization system.*

The authorization layer
-----------------------
weppy includes an useful authorization system, based on the once available on *web2py*, which automatically creates required database tables, and generate forms for access control in the application.

So how do you use it? Let's find out with an example:

```python
from weppy import App, DAL
from weppy.tools import Auth
from weppy.sessions import SessionCookieManager

app = App(__name__)
app.config.db.uri = "sqlite://storage.sqlite"

db = DAL(app)
auth = Auth(app, db, base_url='/account')

app.common_handlers = [
    SessionCookieManager('myverysecretkey'),
    db.handler,
    auth.handler
]

@app.expose('/account(/<str:f>)?(/<str:k>)?')
def account(f, k):
    form = auth(f, k)
    return dict(form=form)
```

That's it.   
Write a template page for the account function including the returned form and open [http://127.0.0.1:8000/account](http://127.0.0.1:8000/account) in your browser. weppy should redirect you to the login page and showing you the relative form.

As you've figured out, the exposed `account` function will be responsible of the authorization flow in your app.   
The `Auth` module of weppy exposes (with the default settings):

* http://.../{baseurl}/login
* http://.../{baseurl}/logout
* http://.../{baseurl}/register
* http://.../{baseurl}/verify_email
* http://.../{baseurl}/retrieve_username
* http://.../{baseurl}/retrieve_password
* http://.../{baseurl}/reset_password
* http://.../{baseurl}/change_password
* http://.../{baseurl}/profile

and it also creates all the database tables needed, from users to groups and memberships, working also with DAL models layer.

You can heavily customize the module settings and the user table on your needs. Go deep and explore all the features and settings of the authorization system in the [dedicated chapter](#) of the documentation.

Languages and translation
-------------------------

weppy provides an integrated powerful multi-language system, based on the *web2py's* one, which helps you to write application supporting different languages.   
But how does it works?

```python
from weppy import App, T
app = App(__name__)

app.languages = ['en', 'it']
app.language_default = 'en'

@app.route("/")
def index():
    hello = T('Hello, my dear!')
    return dict(hello=hello)
```

As you can see, weppy provide a language translator with the `T` object. We also defined which languages our app supports and which is the default language (that tells weppy how to behave when user request a language not defined in the app).   
So what you should do with languages? You can just write in *languages/it.py* file in your application:

```python
{
"Hello, my dear!": "Ciao, mio caro!"
}
```

and the hello message will be translated when the user request the italian language.   
On default settings, the user's requested language is determined by the "Accept-Language" field in the HTTP header, which means that if *user1* has its browser accepting italian language, visiting 'http://127.0.0.1:8000/' he will see the italian version, while *user2* that has its browser accepting any other language different from italian will see the english one.

The translation system has another way to behave, in fact if we put in the prior example this line:

```python
app.language_force_on_url = True
```

weppy uses the url to determine the language instead of the HTTP "Accept-Language" header. This means that weppy will automatically add the support for language on your routing rules to the follow:

| requested url | behaviour |
| --- | --- |
| /anexampleurl | shows up the contents with the default language |
| /it/anexampleurl | shows up the contents with the italian language |

To see more about languages and dive into translator features, read the complete documentation available in the [Languages chapter](#).

Debugging and logging
---------------------
*Section under writing*

Go ahead
--------

Congratulations! You've read everything you need to run a simple but functional weppy application. Use this *quick-start guide* as your manual, and refer to the [complete documentation](./) for every in-depth aspect you may encounter.
