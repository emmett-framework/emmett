Routing system
==============

As introduced in the [Getting Started](./quickstart) chapter, the weppy routing system doesn't use a table or a separated file logic, but it's explicit indeed, using the `route` decorator on your functions.

Exposing functions
------------------

The `route` method of the `App` object accepts several parameters, as you can see from the source code:

```python
def route(self, path=None, name=None, template=None, handlers=None,
           helpers=None, schemes=None, hostname=None, methods=None,
           prefix=None, template_folder=None, template_path=None):
```

Let's see them in detail.

### Path

The `path` parameter is the first and the most important parameter you can pass to `route`, in fact it tells weppy on which url should the function been exposed; still, you seen from the code that is `None` by default. What does it mean? Simply, when you don't pass the `path` parameter to route, it will route your function on the url with the same name of your function. So if you write:

```python
@app.route()
def user():
    # code
```

your `user()` function will be routed on */user*.

To add variable parts to a path you can mark these special sections as `<type:variable_name>` and the variables will be passed as a keyword argument to your functions. Let's see some examples:

```python
@app.route('/user/<str:username>')
def user(username):
    return "Hello %s" % username

@app.route('/double/<int:number>')
def double(number):
    return "%d * 2 = %d" % (number, number*2)
```

It's quite simple, isn't it? And here is the complete list of types of variables you can use:

| type | specification |
|---|---|
| int | accepts integers |
| str | accepts strings |
| date | accepts date strings in format *YYYY-MM-DD* |
| alpha | accepts strings containing only literals |
| any | accepts any path (also with slashes) |

So basically, if we try to open the url for the `double` function of the last example with a string, like '/double/foo', it won't match and weppy will return a 404 error.

Sometimes you also need your variable rules to be conditional, and accepts requests on the same function with, for example, */profile/123432* and */profile*. weppy allows you to do that using the conditional regex notation:

```python
@app.route("/profile(/<int:user_id>)?")
def profile(user_id):
    if user_id:
        # get requested user
    else:
        # load current logged user profile
```
and as you thought, when conditional arguments are not given in the requested url, your function's parameters will be `None`.

Now, it's time to see the `methods` parameter of `route()`

### Template
The `template` parameter allows you to set a specific template for the function you're exposing.   
By default weppy search for a template with the same name of the function, so with an example:

```python
@app.route()
def profile():
    # code
```
will search for the *profile.html* template in your application's *template* folder. When you need to use a different template name, just tell weppy to load it:

```python
@app.route(template="mytemplate.html")
```

### Methods
HTTP knows different methods for accessing URLs. By default, a weppy route only answers to GET and POST requests, but that can be changed easily:

```python
@app.route("/onlyget", methods="get")
def f():
    # code

@app.route("/post", methods=["post", "delete"])
def g():
    # code
```

### Other parameters
If you read the [Getting started](./quickstart) chapter, you should know that weppy provides the *Handler* class to perform operations during requests. The `handlers` and `helpers` parameters of `route()` allows you to bind them on the exposed function.

Similarly to the `methods` parameter, the `schemes` one allows you to tell weppy on which HTTP schemes the function should answer (by default both *http* and *https* methods are allowed); while if you need to bind the exposed function to a specific host, you can use the `hostname` parameter.

The `prefix`, `template_path` and `template_folder` parameters are specific to [AppModules](./app_and_modules#application-modules) and there's no a specific need to use them directly in the `app.route()` function.

The url() function
------------------
weppy provides a useful method to create urls for your exposed functions, let's see how it works:

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
* /
* /anotherurl?u=2
* /find/foo/bar
* /post/123/edit

Basically, you just need to call `url()` with the name of your function, and eventually the arguments needed by the function.

### URLs with application modules
As we seen in the [Application modules](./app_and_modules#application-modules) chapter, above, the `name` parameter of `AppModule` object is used by weppy for the *namespacing* of the urls. What does it mean?   
When you call the weppy `url()` helper, you send as first parameter the name of the function you have exposed. But if you have and `index` function in your main application file, and another `index` function in your module, what will you pass to the `url()`? This is why `AppModule` requires the `name` parameter, as it will be used for the module functions urls.

In fact, when you have modules in your application there are two additional notations for the `url()` function:

| call | end point |
| --- | --- |
| `url('index')` | `index function in the main application file |
| `url('blog.index')` | index function in the module with `name="blog"` |
| `url('.index')` | index function of the same module where you call `url()` |

We need to clarify that the third notation can be used only during the *request flow*, which translates into this statement:

> You can use `url()` dot notation only inside exposed methods (or methods invoked by these) and templates

### Static files
Quite often you will need to link static contents (images, CSS, JavaScripts) into your application. You would create a folder called *static* in your package or next to your module and it will be available at */static* on the application.

To generate URLs for static files, use the special `static` first argument:

```python
url('static', 'js/common.js')
```
that will point to the file in *static/js/common.js*

Calling `url()` for static files is useful instead of manually write the url for the file because you can enable the static *versioning* in your weppy application.

When an application is in development, static files can change often, but when your application goes to *production* you may want to serve static files with cache headers to prevent un-necessary downloads, saving bandwidth and load, since static files do not change often. But when they do, browsers should load the new ones and not the old cached.   
weppy solves the problem for you, allowing you to configure your application with a `static_version`:

```python
app.config.static_version = "1.0.0"
```

then a call to `url('static', 'myfile.js')` will produce the url */static/1.0.0/myfile.js* automatically. And when you release a new version of your application with changed static files, you just need to change the `static_version` string.
