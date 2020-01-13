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
