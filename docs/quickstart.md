Getting started
===============

Ready to get started with Emmett? This guide gives a good introduction to the framework.

A 'Hello world!' application
----------------------------

How would a minimal application look like in Emmett?

```python
from emmett import App

app = App(__name__)

@app.route("/")
async def hello():
    return "Hello world!"
```

Here it is. Save it as *app.py* and run it with Emmett:

```bash
> emmett develop
App running on 127.0.0.1:8000
```

Now if you go to [http://127.0.0.1:8000](http://127.0.0.1:8000) you should see your 'Hello world!' message.

Routing
-------

As you've seen from the 'Hello world!' example, we have *routed* the `hello()` function. What does it mean?

Actually it's quite simple: the route decorator of the application object is used to define the routing of your app.

> – Wait, you mean there's no need of a routing table?   
> – *Nope.*   
> – And how should I define URL variables, HTTP methods, etc.?   
> – *Just use the route decorator and his parameters.*   

In fact, `route()` accepts different parameters. But let's proceed in order, starting with variable rules for routing your functions.

### Variable rules

To add variable parts to an URL, you can mark these special sections as `<type:variable_name>` and the variables will be passed as keyword arguments to your functions. Let's see some examples:

```python
@app.route('/user/<str:username>')
async def user(username):
    return "Hello %s" % username

@app.route('/double/<int:number>')
async def double(number):
    return "%d * 2 = %d" % (number, number*2)
```

It's quite simple, isn't it? What types of variables can you use? Here is the complete list:

| type | specification |
|---|---|
| int | accepts integers |
| float | accepts floats in dot notation |
| str | accepts strings |
| date | accepts date strings in format *YYYY-MM-DD* |
| alpha | accepts strings containing only literals |
| any | accepts any path (also with slashes) |

So, basically, if we try to open the URL for the `double` function of the last example with a string, like '/double/foo', it won't match and Emmett will return a 404 error.

> – OK, fine. But, what if I want a conditional argument for my function?

Just write the URL putting the conditional part between parenthesis and a question mark at the end:

```python
@app.route("/profile(/<int:user_id>)?")
async def profile(user_id):
    if user_id:
        # get requested user
    else:
        # load current logged user profile
```

As you thought, when conditional arguments are not given in the requested URL, your function's parameters will be `None`.

Now, it's time to see the `methods` parameter of `route()`

### HTTP methods

HTTP knows different methods for accessing URLs. By default, a route only answers to GET and POST requests, but that can be changed by providing the methods argument to the `route()` decorator. For example:

```python
@app.route("/onlyget", methods="get")
async def f():
    # code

@app.route("/post", methods=["post", "delete"])
async def g():
    # code
```

If you have no idea of what an HTTP method is – don't worry – [Wikipedia has good information](http://en.wikipedia.org/wiki/Hypertext_Transfer_Protocol#Request_methods) about them.

> – OK, I got it. What else can I do with route?

Since this is a *quick overview* over Emmett, you would check out the [Routing chapter](./routing) of the documentation for the complete list of parameters accepted by the `route()` decorator.

Let's we see how to build URLs with our routing rules.

### Building URLs

Emmett provides a useful method to create URLs.

```python
from emmett import App, url

app = App(__name__)

@app.route("/")
async def index():
    # code

@app.route("/anotherurl")
async def g():
    #code

@app.route("/find/<str:a>/<str:b>")
async def f(a, b):
    # code

@app.route("/post/<int:id>/edit")
async def edit(id):
    # code

a = url('index')
b = url('g', params={'u': 2})
c = url('f', ['foo', 'bar'])
d = url('edit', 123)
```

The above URLs `a`, `b`, `c` and `d` will be respectively converted to:

- /
- /anotherurl?u=2
- /find/foo/bar
- /post/123/edit

which is quite handy instead of remembering all the rules and manually writing the links.

#### Static files

Quite often, you will need to link static contents (images, CSS, JavaScript) into your application. You would create a folder called *static* in your package or next to your module and it will be available at */static* on the application.

To generate URLs for static files, use the special `static` first argument:

```python
url('static', 'js/common.js')
```
that will point to the file in *static/js/common.js*

> – But maybe I can write directly */static/js/common.js* instead of using
`url()` function?

Obviously, you can. However, Emmett provides some useful features for static files URLs, like languages and versioning, which are automatically applied based on your application configuration. You can find more information in the [Routing chapter](./routing#the-url-helper) of the documentation.

Rendering the output
--------------------

Now that you've discovered how Emmett core works, let's find out how to render our content. We will see how to generate an HTML response with a template and how to generate a JSON response.

### The templating engine

Emmett provides the *Renoir* templating engine, which means that you can use Python code directly into your HTML files. Let's see it with an example.   
We can make a new application with this structure:

```
/myapp.py
/templates
    echo.html
```

with *myapp.py* looking like this:

```python
from emmett import App
app = App(__name__)

@app.route("/<str:msg>")
async def echo(msg):
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

> – wait, the `message` I've put in the template is the returned value from my
`echo()` function?   
> – *you got it!*

The dictionary returned by your functions is the *context* of the template, in which you can insert the values defined in Python code. In addition, since everything you write inside `{{ }}` brackets is evaluated as normal Python code you can easily generate HTML with conditions and cycles:

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

As you can see the only difference between the Renoir template and a pure Python code is that you have to write `pass` after the statements to tell Renoir where the Python block ends – normally we have indentation under Python, but we can't have it under HTML.

The templating system has many more features: explore them in the [Templates chapter](./templates) of the documentation.

### Other rendering options

Quite often, you will need to render output from your functions in formats other than HTML, such as JSON.

Emmett can help you with the *service* decorator

```python
from emmett import App
from emmett.tools import service

app = App(__name__)

@app.route("/json")
@service.json
async def f():
    l = [1, 2, {'foo': 'bar'}]
    return dict(status="OK", data=l)
```

The output will be a JSON object with the converted content of your Python dictionary.

The `service` module has other helpers, like *XML* format: go further in the [Services chapter](./services) of the documentation.

Dealing with requests
---------------------

Now let's try to go somewhere deeper in Emmett core logic.

> – How can my application react to client requests?   
> – *you can start with the `request` object*

### The request object

You can access the Emmett's `request` object with just an import:

```python
from emmett import request
```

It contains useful information about the current processing request, let's see some of them:

| attribute | description |
| --- | --- |
| scheme | could be *http* or *https* |
| method | the request HTTP method |
| now | a pendulum Datetime object created with request |
| query_params | an object containing URL params |

Let's focus on the `request.query_params` object, and understand it with an example:

```python
from emmett import App, request

app = App(__name__)

@app.route("/post/<int:id>")
async def post(id):
    editor = request.query_params.editor
    if editor == "markdown":
        # code
    elif editor == "html":
        # code
    #..
```

Now, when a client call the URL */post/123?editor=markdown*, the `editor` parameter will be mapped into `request.query_params` and we can access its value simply calling the parameter name as an attribute.

> – Wait, what happens if the client calls */post/123* and my app tries to access *request.query_params.editor*, which is not in the URL?

Simple! The attribute will be `None`, so it's completely safe to call it. It won't raise any exception.

More information about the `request` object could be found in the [Request chapter](./request) of the documentation.

### Pipeline: performing operations with requests

> – What if I want to do something before and after the request?   
> – *You can use the pipeline.*

Emmett uses the pipeline to perform operations before and after running the functions defined with your routing rules.

The pipeline is a list of *pipes*, objects of the `Pipe` class. Let's see how to create one of them:

```python
from emmett import Pipe

class MyPipe(Pipe):
    async def open(self):
        # code
    async def close(self):
        # code
    async def on_pipe_success(self):
        # code
    async def on_pipe_failure(self):
        # code
```

As you can see `Pipe` provide methods to run your code before the request is processed by your function (with the `open` method) and after your function were executed, providing different methods depending on what happened on your function: if an exception is occurred Emmett will call the `on_pipe_failure` method, otherwise the `on_pipe_success` method. The `close` method is **always** called after every request has been processed, *after* the response has been created and *before* sending it to the client.

To register your pipe to a function you just need to write:

```python
@app.route("/url", pipeline=[MyPipe()])
async def f():
    #code
```

And if you need to register your pipe to all your application functions, you can omit the pipe from the `route()` decorator writing instead:

```python
app.pipeline = [MyPipe()]
```

Emmett also provides an `Injector` pipe, which is designed to add helping methods to the templates. Explore the [Pipeline chapter](./request#pipeline) of the documentation for more informations.

### Redirects and errors

Taking again the example given for the `request.query_params`, we can add a redirect on the missing URL param:

```python
from emmett import redirect, url

@app.route("/post/<int:id>")
async def post(id):
    editor = request.query_params.editor
    if editor == "markdown":
        # code
    elif editor == "html":
        # code
    else:
        redirect(url('post', id, params={'editor': 'markdown'}))
```

which means that when the `editor` var is missing we force the user to the markdown one.

Another way would be returning a 404 error:

```python
from emmett import abort

@app.on_error(404)
async def not_found():
    #code

@app.route("/post/<int:id>")
async def post(id):
    editor = request.query_params.editor
    if editor == "markdown":
        # code
    elif editor == "html":
        # code
    else:
        abort(404)
```

As you can see Emmett applications can handle specific actions on HTTP errors. For more information, check out the [Error handling chapter](./request#errors-and-redirects) of the documentation.

Sessions
--------

An essential feature for a web application is the ability to store specific informations about the client between multiple requests. Accordingly, Emmett provides another object besides the `request`, called `session`.

Session contents can be stored in several ways, such as using file or redis. In this quick start, we will see how to use the `session` and store its contents directly in the cookies of the client.

We're going to use the `SessionManager` class provided by Emmett, and write a very simple route which interacts with the session:

```python
from emmett import App, session
from emmett.sessions import SessionManager

app = App(__name__)
app.pipeline = [SessionManager.cookies('myverysecretkey')]

@app.route("/")
async def count():
    session.counter = (session.counter or 0) + 1
    return "You have visited %d times" % session.counter
```

The above code is quite simple: the app increments the counter every time the user visits the page and return this number to the user. Basically, you can store a value to the user session and retrieve it whenever the session is kept.

> – and what if I try to access an attribute not existent in session?   
> – *same as `request.query_params`: the attribute will be `None` and you don't have to catch any exception*

More information about storing systems is available in the [Session chapter](./sessions) of the documentation.

Creating forms
--------------

You will probably need to build forms for your web application often. Emmett provides the `Form` class to help you doing that.

Let's see how to use it with an example:

```python
from emmett import Field, Form

# create a form
@app.route('/form')
async def a():
    simple_form = await Form({
        'name': Field(),
        'number': Field.int(),
        'type': Field(
            validation={'in': ['type1', 'type2']}
        )
    })
    if simple_form.accepted:
        #do something
    return dict(form=simple_form)
```

As you can see, the `Form` class accepts a list of fields for the input, and you can add validation to your fields. The `Form` class comes with many options. For example, you can set an `onvalidation` method to run additional validation besides the fields' requirements.   

You can also customize the form rendering and styling, or generate forms from database tables created with the integrated [ORM](./orm). Check out the [Forms chapter](./forms) of the documentation.

Languages and internationalization
----------------------------------

Emmett provides *Severus* as its integrated internationalization engine, which helps you to write applications supporting different languages.   
But how does it work?

```python
from emmett import App, T
app = App(__name__)

@app.route("/")
async def index():
    hello = T('Hello, my dear!')
    return dict(hello=hello)
```

As you can see, Emmett expose a language translator with the `T` object.   
So what you should do with languages? You can just write your translation in a *json* or *yaml* file within your application *languages* folder, naming it for the language code you want to use. That's "it" for Italian, so our *it.json* file will look like:

```json
{
    "Hello, my dear!": "Ciao, mio caro!"
}
```

The "hello" message will be translated when the user requests the Italian language.

On default settings, the user's requested language is determined by the "Accept-Language" field in the HTTP header, but the translation engine has another way to behave, in fact if we put this line in the prior example:

```python
app.language_force_on_url = True
```

Emmett uses the URL to determine the language instead of the HTTP "Accept-Language" header. This means that Emmett will automatically add the support for language on your routing rules.

To see more about languages and dive into translator features, read the complete documentation available in the [Languages chapter](./languages).

Go ahead
--------

Congratulations! You've read everything you need to run a simple but functional Emmett application. Use this *quick-start guide* as your manual, and refer to the [complete documentation](./) for every in-depth aspect you may encounter.
