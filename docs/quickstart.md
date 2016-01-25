Getting started
===============

Ready to get started with weppy? This guide gives a good introduction to the framework.

An 'hello world' application
----------------------------
How a minimal application would look like in weppy?

```python
from weppy import App
app = App(__name__)

@app.route("/")
def hello():
    return "Hello world!"

if __name__ == "__main__":
    app.run()
```

Here it is. Save it as *hello.py* and run it with your python interpreter:

```bash
> python hello.py
App running on 127.0.0.1:8000
```

Now if you go to [http://127.0.0.1:8000](http://127.0.0.1:8000) you should see your 'Hello world!' message.

Expose and routing
------------------
As you seen from the 'Hello world' example, we have *exposed* the `hello()` function. What does it mean?

Actually it's quite simple: the route decorator of the application object is used to define the routing of your app.

> – Wait, you mean there's no need of a routing table?   
> – *Nope.*   
> – And how should I define url variables, HTTP methods, ecc.?   
> – *Just use the route decorator and his parameters.*   

In fact, `route()` accepts different parameters. But let we proceed in order, starting with variables rules for routing your functions.

### Variable rules
To add variable parts to an URL you can mark these special sections as `<type:variable_name>` and the variables will be passed as a keyword argument to your functions. Let's see some examples:

```python
@app.route('/user/<str:username>')
def user(username):
    return "Hello %s" % username

@app.route('/double/<int:number>')
def double(number):
    number = int(number)
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

> **Note:**    
> the type specification won't change the type of the input variables, that will always be strings (as they are parts of the url). If you want to use these parts as real integers or dates, you have to parse them depending on your needs.

So basically, if we try to open the url for the `double` function of the last example with a string, like '/double/foo', it won't match and weppy will return a 404 error.

> – Ok, fine. But, what if I want a conditional argument for my function?

Just write the url using the regex notation:

```python
@app.route("/profile(/<int:user_id>)?")
def profile(user_id):
    if user_id:
        # get requested user
    else:
        # load current logged user profile
```
as you thought, when conditional arguments are not given in the requested url, your function's parameters will be `None`.

Now, it's time to see the `methods` parameter of `route()`

### HTTP methods
HTTP knows different methods for accessing URLs. By default, a route only answers to GET and POST requests, but that can be changed by providing the methods argument to the `route()` decorator. For example:

```python
@app.route("/onlyget", methods="get")
def f():
    # code

@app.route("/post", methods=["post", "delete"])
def g():
    # code
```

If you have no idea of what an HTTP method is, don't worry, [Wikipedia has good informations](http://en.wikipedia.org/wiki/Hypertext_Transfer_Protocol#Request_methods) about them.

> – Ok, I got it. What else can I do with route?

Since this is a *quick overview* over weppy, you would check out the [appropriate chapter](./routing) of the documentation for the complete list of parameters accepted by the `route()` decorator.

Let's we see how to build urls on our routing rules.

### Building URLs
Weppy provide a useful method to create urls, let's see how it works:

```python
from weppy import App, url
app = App(__name__)

@app.route("/")
def index():
    # code

@app.route("/anotherurl")
def g():
    #code

@app.route("/find/<str:a>/<str:b>")
def f(a, b):
    # code

@app.route("/post/<int:id>/edit")
def edit(id):
    # code

a = url('index')
b = url('g', params={'u': 2})
c = url('f', ['foo', 'bar'])
d = url('edit', 123)
```
The above urls `a`, `b`, `c` and `d` will be respectively converted to:

- /
- /anotherurl?u=2
- /find/foo/bar
- /post/123/edit

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

@app.route("/<str:msg>")
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

@app.route("/json")
@service.json
def f():
    l = [1, 2, {'foo': 'bar'}]
    return dict(status="OK", data=l}
```
The output will be a JSON object with the converted content of your python dictionary.

The `service` module has other helpers, like *xml* format: go further in the [Services chapter](.services) of the documentation.

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
| params | an object containing url params |

Let's focus on `request.params` object, and understand it with an example:

```python
from weppy import App, request

app = App(__name__)

@app.route("/post/<int:id>")
def post(id):
    editor = request.params.editor
    if editor == "markdown":
        # code
    elif editor == "html":
        # code
    #..
```
Now, when a client call the url */post/123?editor=markdown*, the `editor` parameter will be mapped into `request.params` and we can access its value simply calling the parameter name as an attribute.

> – wait, what happens if client call */post/123* and my app try to access *request.params.editor* which is not in the url?

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
    def on_end(self):
        # code
```
As you can see `Handler` provide methods to run your code before the request is processed by your function (with the `on_start` method) and after your function were executed, providing different methods depending on what happened on your function: if an exception is occurred weppy will call the `on_failure` method, otherwise the `on_success` method. The `on_end` method is **always** called after every request has been processed, in particular: *after* the response has been created and *before* sending it to the client.

To register your handler to a function you just need to write:

```python
@app.route("/url", handlers=[MyHandler()])
def f():
    #code
```

And if you need to register your handler to all your application functions, you can omit the handler from the `route()` decorator writing instead:

```python
app.common_handlers = [MyHandler()]
```

weppy also provides a Helper handler, which is designed to add helping methods to the templates. Explore the [Handlers chapter](./request#handlers-and-helpers) of documentation for more informations.

### Redirects and errors
Taking again the example given for the `request.params`, we can add a redirect on the missing url param:

```python
from weppy import redirect, url

@app.route("/post/<int:id>")
def post(id):
    editor = request.params.editor
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
from weppy import abort

@app.on_error(404):
def not_found():
    #code

@app.route("/post/<int:id>")
def post(id):
    editor = request.params.editor
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

@app.route("/")
def count():
    session.counter = (session.counter or 0) + 1
    return "This is your %d visit" % session.counter
```
The above code is quite simple: the app increments the counter every time the user visit the page and return this number to the user.
So basically, you can store a value to the user session and retrieve it whenever the session is kept.

> – and if I try to access an attribute not existent in session?   
> – *same as `request.params`: the attribute will be `None` and you don't have to catch any exception*

More information and storing systems are available in the [Session chapter](./sessions) of the documentation.

Creating forms
--------------
You will need quite often to build forms for your web application. weppy provides the `Form` class to help you doing that.

Let's see how to use it with an example:

```python
from weppy import Field, Form

# create a form
@app.route('/form')
def a():
    simple_form = Form({
        'name': Field(),
        'number': Field('int'),
        'type': Field(
            validation={'in': ['type1', 'type2']}
        )
    })
    if simple_form.accepted:
        #do something
    return dict(form=simple_form)
```

As you can see the `Form` class accepts a list of fields for the input, and you can add validation to your fields. The `Form` class comes with many options, for example you can set an `onvalidation` method to run additional validation besides the fields' requirements.   
You can also customize the form rendering and styling, or generate forms from database tables created with the integrated [DAL](./dal). Check out the [Forms chapter](./forms) of the documentation and the [weppy BS3 extension](#) which add bootstrap3 style to your forms.

Languages and translation
-------------------------

weppy provides an integrated powerful multi-language system, based on the *web2py's* one, which helps you to write application supporting different languages.   
But how does it works?

```python
from weppy import App, T
app = App(__name__)

@app.route("/")
def index():
    hello = T('Hello, my dear!')
    return dict(hello=hello)
```

As you can see, weppy provide a language translator with the `T` object.   
So what you should do with languages? You can just write in *languages/it.py* file in your application:

```python
{
"Hello, my dear!": "Ciao, mio caro!"
}
```

and the hello message will be translated when the user request the italian language.   
On default settings, the user's requested language is determined by the "Accept-Language" field in the HTTP header, but the translation system has another way to behave, in fact if we put in the prior example this line:

```python
app.language_force_on_url = True
```

weppy uses the url to determine the language instead of the HTTP "Accept-Language" header. This means that weppy will automatically add the support for language on your routing rules.

To see more about languages and dive into translator features, read the complete documentation available in the [Languages chapter](./languages).

Go ahead
--------

Congratulations! You've read everything you need to run a simple but functional weppy application. Use this *quick-start guide* as your manual, and refer to the [complete documentation](./) for every in-depth aspect you may encounter.
