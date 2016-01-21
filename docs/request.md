Handling requests
=================

weppy provides several instruments to help you dealing with requests in your application. Let's see them. 

The request object
------------------
When a request comes from a client, weppy binds useful informations about it on the `request` object, which can be accessed just with an import:

```python
from weppy import request
```
It contains useful information about the current processing request, in particular:

| attribute | description |
| --- | --- |
| scheme | could be *http* or *https*|
| method | the request HTTP method |
| now | a python datetime object created with request|
| client | the ip of the client doing the request (if available) |
| cookies | the cookies passed with the request |
| env | contains environment variables like HTTP headers and WSGI parameters |
| isajax | boolean which states if the request was made in ajax (check for *xmlhttprequest* presence in headers) |

Please keep in mind that the `now` attribute uses UTC timezone by default. You can instead using the machine timezone:

```python
app.now_reference = "local"
```

And if you need to access both the *local* time of the request and the *utc* one you can directly access these values on request using:

```python
# request datetime in UTC timezone
request.nowutc
# request datetime in local machine timezione
request.nowloc
```

Now, let's see how to deal with request variables.

### Request variables

weppy's `request` object also provides three important attributes about the active request, in particular:

| attribute | description |
| --- | --- |
| query_params | contains the url query parameters |
| body_params | contains parameters passed into the request body |
| params | contains both the query parameters and the body parameters |

All these three attributes work in the same way, and the better way to understand it is with an example:

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

When the url doesn't contain the query parameter you're trying to look at, this will be `None`, so it's completely safe to call it, it wont raise an exception.

Now, what happens when the client does a *POST* request with this body

```json
{
    "text": "this is an example post",
    "date": "2014-10-15"
}
```

on the url */post/123?editor=markdown* ? Simple: the three `request` attributes we have seen will look like this:

```
>>> request.params
<sdict {'date': '2014-10-15', 'text': 'this is a sample post', 'editor': 'markdown'}>
>>> request.query_params
<sdict {'editor': 'markdown'}>
>>> request.body_params
<sdict {'date': '2014-10-15', 'text': 'this is a sample post'}>
```
so you can always access the variables you need.

Handlers and Helpers
--------------------
Quite often your application needs to perform operations before and after the request is actually processed by weppy using your exposed function.   
weppy helps you doing this with the Hanlders:

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

To better understand the usage of all these methods, let's assume to write a database handler, so that it will connect to the database when a request arrive, will do a commit or a rollback depending on what happened during the request and finally will close the connection:

```python
class DBHandler(Handler):
    def on_start(self):
        # connect to the db
    def on_success(self):
        # commit to the db
    def on_failure(self):
        # rollback the operations
    def on_end(self):
        # close the connection
```
Now, to register your handler to a function you just need to write:

```python
@app.route("/url", handlers=[MyHandler()])
def f():
    #code
```
And if you need to register your handler to all your application functions, you can omit the handler from the `route()` decorator writing instead:

```python
app.common_handlers = [MyHandler()]
```

### A peculiar Handler: the Helper class

Another common scenario you may encounter building your application is when you need to add same contents to your exposed functions' outputs, to make them available for the templates.

For example, let's say you have a function that makes your datetimes objects prettier:

```python
>>> prettydate(datetime.now()-timedelta(days=1))
'One day ago'
```

And you would use it in your templates:

```html
{{for post in posts:}}
<div class="post">
    <div class="post-date">{{=prettydate(post.date)}}</div>
    <div class="post-content">{{=post.text}}</div>
</div>
{{pass}}
```

So, instead of adding `prettydate` to every exposed function, you can do this:

```python
from weppy import Helper

class MyHelper(Helper):
    @staticmethod
    def prettydate(d):
        # your prettydate code

app.common_helpers = [MyHelper()]
```
and you can access your `prettydate` function in every template.

So basically, the `Helper` class of weppy adds everything you define inside it (functions and attributes) into your exposed function returning *dict*.

Errors and redirects
--------------------
Now, talking about handling requests, you would like to perform actions on errors.

If we look again at the given example for the `request.params`, what happens when the user call the url without passing the `editor` query parameter?
Maybe you want to redirect the client on a default parameter:

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

The `redirect` function of weppy accepts a string for the url, and acts like an exception, interrupting the execution of your code.

Maybe, you prefer to show your 404 page:

```python
from weppy import abort

@app.on_error(404):
def not_found():
    app.render_template("404.html")

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
and that's it.

So you've just learned three handy things of weppy:

* `redirect` and `abort` allows you to stop the execution of your code;
* you can set specific actions for your application when it encounters a particular HTTP error code with `app.on_error()`;
* you can use `app.render_template()` to render a specific template without the presence of an exposed function or a specific context.
