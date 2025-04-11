Building responses
==================

As we saw in the [Request chapter](./request), Emmett provides several tools
for handling requests from clients.

However, since your application has to produce responses to these requests,
Emmett also supplies some tools for that.

The response object
-------------------
As for the `request` object, Emmett stores some data in the `response` object,
data which will be used when the request has been processed and the output
is pushed back to the client. 

Accessing the `response` object is as simple as accessing a `request`:

```python
from emmett import response
```

and this is the list of attributes you can deal with:

| attribute | description |
| --- | --- |
| status | HTTP status for the response, set on 200 unless an exception/redirect/abort occurs |
| cookies | contains the cookies that will be pushed to the client |
| headers | HTTP headers for the response |
| meta | meta tags for the response |
| meta_prop | meta properties tags for the response |

If you need to set a cookie you can just write:

```python
response.cookies['yourcookiename'] = 'yourdata'
response.cookies['yourcookiename']['path'] = '/'
```

or to set a header:

```python
response.headers['Cache-Control'] = 'private'
```

Meta properties
---------------
HTML has 2 kind of meta tags:

```html
<meta property="og:title" content="Walter Bishop's place" />
<meta name="description" content="A pocket universe" />
```

they can be very helpful for improving your application's SEO.

Instead of manually writing them in your templates, you can add these tags
to your response in an easier way. Lets say, for example, that we have a blog
and we want to automatically add our meta tags on a single post:

```python
@app.route("/p/<int:post_id>")
async def single(post_id):
    post = somedb.findmypost(post_id)
    response.meta.title = "MyBlog - "+post.title
    response.meta.keywords = ",".join(key for key in post.keywords)
    response.meta_prop["og:title"] = response.meta.title
```

Then, in your template, you can just write:

```html
<html>
  <head>
    <title>{{ =current.response.meta.title }}</title>
    {{ include_meta }}
  </head>
```

and you will have all the meta tags included in your HTML.

Wrapping methods
----------------

*New in version 2.6*

Emmett `Response` object also provides some *wrapping* methods in order to respond with files or streams of data, specifically:

- `wrap_iter`
- `wrap_aiter`
- `wrap_file`
- `wrap_io`

These methods can be used to produce responses from iterators and files.

### Iterable responses

The `wrap_iter` and `wrap_aiter` methods are very similar, both accepts iterables: you can use the latter for asynchronous iterators:

```python
def iterator():
    for _ in range(3):
        yield b"hello"

async def aiterator():
    for _ in range(3):
        yield b"hello"

@app.route()
async def response_iter():
    return response.wrap_iter(iterator())

@app.route()
async def response_aiter():
    return response.wrap_aiter(aiterator())
```

> **Note:** both `wrap_iter` and `wrap_aiter` perform the iteration outside of the [pipeline](./pipeline). Whenever you need to stream contents and keep the pipeline open or use the global context, you should use the [stream utilities](#streaming-responses) instead.

### File responses

You can produce responses from file using two different methods in Emmett:

- `wrap_file` when you want to create a response from a path
- `wrap_io` when you want to create a response from a *file-like* object

```python
@app.route("/file/<name:str>")
async def file(name):
    return response.wrap_file(f"assets/{name}")


@app.route("/io/<name:str>")
async def io(name):
    with open(f"assets/{name}", "rb") as f:
        return response.wrap_io(f)
```

Streaming responses
-------------------

*New in version 2.7*

Emmett `Response` object provides a `stream` awaitable method in order to stream content from a generator while keeping the [pipeline](./pipeline) open:

```python
async def iterator():
    for _ in range(3):
        yield b"hello"

@app.route()
async def response_stream():
    response.status = 200
    return await response.stream(iterator())
```

### Streaming utilities

On top of the `Response.stream` method, Emmett also provides a `StreamPipe` pipe and a `stream` decorator, so you can define your route function as the generator:

```python
from emmett.tools import StreamPipe, stream

# the following routes behave the same
@app.route(pipeline=[StreamPipe()])
async def stream_1():
    for _ in range(3):
        yield b"hello"

@app.route()
@stream()
async def stream_2():
    for _ in range(3):
        yield b"hello"
```

As you can't change the `Response` object directly in the route anymore, both `StreamPipe` and `stream` accept the same parameters to do so, specifically:

| parameter | type | default |
| --- | --- | --- |
| status | `int` | 200 |
| headers | `dict[str, str]` | `{}` |
| cookies | `dict[str, Any]` | `{}` |

> **Note:** while `status` will overwrite the existing value, both `headers` and `cookies` will be merged on top of the existing `Response` ones.

### Server-Sent Events

Emmett also provides some specific utilities to stream [Server-Sent Events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events):

```python
from emmett.tools import sse

@app.route()
@sse()
async def sse_stream():
    for _ in range(3):
        yield sse.Event(data={"msg": "hello"})
```

The `sse` decorator is based on the `stream` one but already configures some headers for you, like the `content-type` and caching. You can still use the same parameters of the `stream` decorator to customise the response.

Message flashing
----------------

When you need to store a message at the end of one request, and access it
during the next one, Emmett's `response.alerts()` become quite handy.

For example, you may want to send a success alert to the user. Let's say 
you have function which exposes a form, you can use message flashing to
alert the user the form was accepted:

```python
from emmett.helpers import flash

@app.route("/someurl")
async def myform():
    form = await Form()
    if form.accepted:
        flash("We stored your question!")
    return dict(form=form)
```

then, in your template, you can access the flashed messages using `response`:

```html
<div class="container">
  {{ for flash in current.response.alerts(): }}
  <div class="myflashstyle">{{ =flash }}</div>
  {{ pass }}
</div>
```

and style them however you prefer.

`flash()` and `response.alerts()` also accept category filtering, so you can do:

```python
flash('message1', 'error')
response.alerts(category_filter=["error"])
``` 

or you can receive all flash messages with their category:

```
>>> response.alerts(with_categories=True)
[('error', 'message1')]
```
