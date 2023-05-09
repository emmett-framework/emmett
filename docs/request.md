Handling requests
=================

Emmett provides several instruments to help you dealing with requests in your application. Let's see them.

The request object
------------------

When a request comes from a client, Emmett binds useful informations about it within the `request` object, which can be accessed just with an import:

```python
from emmett import request
```

It contains useful information about the current processing request, in particular:

| attribute | description |
| --- | --- |
| scheme | could be *http* or *https* |
| path | full path of the request |
| host | hostname of the request |
| method | the request HTTP method |
| now | a pendulum Datetime object created with request |
| headers | the headers of the request |
| cookies | the cookies passed with the request |
| body | the request body (if available) |
| client | the IP Address of the client doing the request (if available) |

Please keep in mind that the `now` attribute will always use the UTC timezone, by default.

If you need to access the *local* time of the request you can use `now_local`:

```python
# request datetime in local machine timezone
request.now_local
```

> **Note:** since `now` is a [pendulum Datetime](https://pendulum.eustace.io/) object, you can easily change the timezone using the `in_timezone` method, like `request.now.in_timezone('Europe/Berlin')`.

Now, let's see how to deal with request variables.

### Request variables

Emmett's `request` object also provides three important attributes about the active request:

| attribute | awaitable | description |
| --- | --- | --- |
| query_params | no | contains the URL query parameters |
| body_params | yes | contains parameters passed into the request body |
| files | yes | contains files passed into the request body |

All three attributes are `sdict` objects and they work in the same way, within the exception of requiring `await` or not, and an example may help you understand their dynamic:

```python
from emmett import App, request

app = App(__name__)

@app.route("/post/<int:id>")
async def post(id):
    editor = request.query_params.editor
    if editor == "markdown":
        text = (await request.body_params).text
    elif editor == "html":
        # code
    #..
```

Now, when a client calls the URL */post/123?editor=markdown*, the `editor` parameter will be mapped into `request.query_params` and we can access its value simply calling the parameter name as an attribute.

When the URL doesn't contain the query parameter you're trying to look at, this will be `None`, so it's completely safe to call it. It won't raise any exception.

Now, what happens when the client does a *POST* request with the following body on the URL */post/123?editor=markdown*?

```json
{
    "text": "this is an example post",
    "date": "2014-10-15"
}
```

Simple: the `request`'s params attributes will look like this:

```
>>> request.query_params
<sdict {'editor': 'markdown'}>
>>> await request.body_params
<sdict {'date': '2014-10-15', 'text': 'this is a sample post'}>
```

You can always access the variables you need.

Errors and redirects
--------------------

Speaking of handling requests, you would like to perform specific actions on errors.

If we look at the given example for the parameters again, what happens when the user calls the URL without passing the `editor` query parameter?

Maybe you want to redirect the client with a default parameter:

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

which means that, when the `editor` var is missing, we force the user to markdown.

The `redirect` function of Emmett accepts a string for the URL, and acts like an exception, interrupting the execution of your code.

Maybe, you prefer to show your 404 page:

```python
from emmett import abort

@app.on_error(404)
async def not_found():
    return app.render_template("404.html")

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

That's all it takes.

So you've just learned three handy aspects of Emmett:

* `redirect` and `abort` allow you to stop the execution of your code;
* you can set specific actions for your application to perform when it encounters a particular HTTP error code with `app.on_error()`;
* you can use `app.render_template()` to render a specific template without the presence of an exposed function or a specific context.

HTTP/2
------

*Changed in version 2.5*

Emmett supports serving requests following the HTTP/2 standard. In order for the browser to use HTTP/2 protocol, SSL should be enabled. SSL certificate and key should be passed to `develop` and `serve` commands using the relevant `--ssl-certfile` and `--ssl-keyfile` options.

> **Hint:** a self-signed SSL certificate can be generated for development purposes using the `openssl` command, like: `openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 365 -nodes`.

### Server push

Server push allows for the server to send responses to the client before the client sends the request itself. This is useful when the server can predict what the client will request, thereby saving time at the possible cost of bandwidth if the prediction is wrong.

Emmett supports HTTP/2 server push promises thanks to the `Request.push_promise` coroutine, which accepts as parameter the url of the static file to be sent. Here is an example:

```python
from emmett import request, url

@app.route("/")
async def index():
    await request.push_promise(url("static", "some_asset.js"))
    return {}
```

> **Note:** Emmett's integrated HTTP server doesn't support push promises. In order to use this feature you will need to serve your application with a 3rd party server like Hypercorn.
