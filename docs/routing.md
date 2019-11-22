Routing system
==============

As introduced in the [Getting Started](./quickstart) chapter, the Emmett routing
system doesn't use a table or separated file logic, but it's explicit indeed, 
using the `route` decorator on your functions.

Exposing functions
------------------

*Changed in 1.0*

The `route` method of the `App` object accepts several parameters,
as you can see from the source code:

```python
def route(
    self, path=None, name=None, template=None, pipeline=None, injectors=None,
    schemes=None, hostname=None, methods=None, prefix=None, 
    template_folder=None, template_path=None):
```

Let's see them in detail.

### Path

The `path` parameter is the first and the most important parameter you can
pass to `route`. In fact, it tells Emmett which URL should the function been
exposed on; still, you've seen from the code that `path` is `None` by default.
What does this mean? Simply, when you don't pass the `path` parameter to route,
it will route your function on the URL with the same name of your function.
So if you write:

```python
@app.route()
async def user():
    # code
```

your `user()` function will be routed on */user*.

To add variable parts to a path, you can mark these special sections as
`<type:variable_name>` and the variables will be passed as a keyword argument
to your functions. Let's see some examples:

```python
@app.route('/user/<str:username>')
async def user(username):
    return "Hello %s" % username

@app.route('/double/<int:number>')
async def double(number):
    return "%d * 2 = %d" % (number, number*2)
```

It's quite simple, isn't it? Here is the complete list of types of variables
you can use:

| type | specification |
|---|---|
| int | accepts integers |
| float | accepts floats in dot notation |
| str | accepts strings |
| date | accepts date strings in format *YYYY-MM-DD* |
| alpha | accepts strings containing only literals |
| any | accepts any path (also with slashes) |

So, basically, if we try to open the URL for the `double` function of the last
example with a string, like '/double/foo', it won't match and Emmett will 
return a 404 error.

> **Note:** the *int*, *float* and *date* variables are casted to the relevant objects, so the parameters passed to your function will be of tipe `int`, `float` and `pendulum.Datetime`.

Sometimes you also need your variable rules to be conditional, and accept
requests on the same function with, for example, */profile/123432* and */profile*. 
Emmett allows you to do that using conditional regex notation:

```python
@app.route("/profile(/<int:user_id>)?")
async def profile(user_id):
    if user_id:
        # get requested user
    else:
        # load current logged user profile
```

As you thought, when conditional arguments are not given in the requested URL,
your function's parameters will be `None`.

Now, it's time to see the `methods` parameter of `route()`

### Methods

HTTP knows different methods for accessing URLs. By default, an Emmett route only
answers to GET and POST requests, but that can be changed easily. Use a list if
you want to accept more than one kind of list:

```python
@app.route("/onlyget", methods="get")
async def f():
    # code

@app.route("/post", methods=["post", "delete"])
async def g():
    # code
```

### Template

The `template` parameter allows you to set a specific template for the function 
you're exposing. By default, Emmett searches for a template with the same 
name as the function:

```python
@app.route()
async def profile():
    # code
```

will search for the *profile.html* template in your application's *templates* 
folder. When you need to use a different template name, just tell Emmett to load it:

```python
@app.route(template="mytemplate.html")
```

### Other parameters

Emmett provides the *Pipe* class to perform operations during requests. The `pipeline` and `injectors` parameters of `route()` allows you to bind them on the exposed function.

Similar to the `methods` parameter, `schemes` allows you to tell Emmett
on which HTTP schemes the function should answer. By default, both *HTTP* and
*HTTPS* methods are allowed. If you need to bind the exposed function to
a specific host, you can use the `hostname` parameter.

The `prefix`, `template_path`, and `template_folder` parameters are specific to [application modules](./app_and_modules#application-modules), and there's no specific need to use them directly in the `app.route()` function.

The url() function
------------------
Emmett provides a useful method to create URLs for your exposed functions. Let's
see how it works:

```python
from emmett import App, url

app = App(__name__)

@app.route("/")
async def index():
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

The above URLs `a`, `b`, `c` and `d` will be respectively converted to:

* /
* /anotherurl?u=2
* /find/foo/bar
* /post/123/edit

Basically, you just need to call `url()` with the name of your function, 
and the arguments needed by the function.

Here is the complete list of `url` accepted parameters:

| parameter | description |
| --- | --- |
| path | name of the route or absolute path |
| args | list of route variables (single string argument accepted) |
| params | dictionary of query parameters |
| anchor | anchor(s) for the url |
| sign | a callable method that should produce a signature for the url |
| scheme | scheme for the url (can be http or https) |
| host | host for the url |
| language | specify a language of the application to localize the url |

### URLs with application modules
As we seen in the [Application modules](./app_and_modules#application-modules)
chapter, above, the `name` parameter of the `AppModule` object is used by Emmett for
the *namespacing* of the URLs. What does this mean? When you call the Emmett
`url()` helper, you send the name of the function you have exposed as the first 
parameter. However, if you have an `index` function in your main application file,
and another `index` function in your module, what will you pass to the `url()`?
This is why `AppModule` requires the `name` parameter, as it will be used for the
module functions' URLs.

In fact, when you have modules in your application there are two additional notations 
for the `url()` function:

| call | end point |
| --- | --- |
| `url('index')` | index function in the main application file |
| `url('blog.index')` | index function in the module with `name="blog"` |
| `url('.index')` | index function of the same module where you call `url()` |

We need to clarify that the third notation can be used only during the
*request&nbsp;flow*, which translates into this statement:

> You can use `url()` dot notation only inside exposed methods (or methods invoked by these) and templates

### Static files
Quite often, you will need to link static contents (images, CSS, JavaScript)
into your application. After creating a folder called *static* in your package
or next to your module, it will be available at */static* on the application.

To generate URLs for static files, use the special `static` first argument:

```python
url('static', 'js/common.js')
```

that will point to the file in *static/js/common.js*

Calling `url()` for static files instead of manually write the URL for the file
is useful because you can enable the static *versioning* in your Emmett application.

When an application is in development, static files can change often, but when 
your application goes to *production* static files tend to be stable. You may
want to serve static files with cache headers to prevent un-necessary downloads,
saving bandwidth and load. However, browsers should load the latest versions
and not the old cached ones. Emmett solves the problem for you, 
allowing you to configure your application with a `static_version`:

```python
app.config.static_version_urls = True
app.config.static_version = "1.0.0"
```

then a call to `url('static', 'myfile.js')` will produce the URL
*/static/1.0.0/myfile.js* automatically. When you release a new version 
of your application with changed static files, you just need to update 
the `static_version` string.


Multiple paths
--------------

*New in version 1.0*

Sometimes you might need to route several paths to the same exposed method. Whenever you need this, you can specify a list of paths for the involved route.

Let's say, for example, you need to route a method that expose the comments of your blog, and you want to use the same method both in case the client needs all the comments, or just the ones referred to a specific post. Then you can write:

```python
@app.route(['/comments', '/post/<int:pid>/comments'])
async def comments(pid=None):
    if pid:
        # code to fetch the post comments
    else:
        # code to fetch all the comments
```

> **Note:** mind that both the paths will have the same routing pipeline.

Under the default behavior, Emmett will use the first path for building urls, while the other ones are accessible with a dot notation and the array position. For instance, for the example route we just defined above, you can build these urls:

```python
>>> url('comments')
/comments
>>> url('comments.1', 12)
/post/12/comments
```
