Building responses
==================

As we seen in the [Request chapter](./request), weppy provides several tools for handling requests from clients.

But, since your application has to produce responses to these requests, weppy also supplies some tools for that.

The response object
-------------------
As for the `request` object, weppy stores some data into the `response` object, data which will be used when the request has been processed and the output is pushed back to the client. 

Accessing the `response` object is as simple as for the `request` one:

```python
from weppy import response
```
and this is the list of attributes you can deal with:

| attribute | description |
| --- | --- |
| status | HTTP status for the response, set on 200 unless an exception/redirect/abort occurs |
| cookies | contains the cookies that will be pushed to the client |
| headers | HTTP headers for the response |
| meta | meta tags for the response |
| meta_prop | meta properties tags for the response |

So if you need to set a cookie you can just do:

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
they can be very helpful for correctly use SEO on your application.

Instead of manually write them in your templates, you can add these tags to your response in an easier way. Lets say, for example, that we have a blog and we want to automatically add our meta tags on a single post:

```python
@app.route("/p/<int:post_id>")
def single(post_id):
    post = somedb.findmypost(post_id)
    response.meta.title = "MyBlog - "+post.title
    response.meta.keywords = ",".join(key for key in post.keywords)
    response.meta_prop["og:title"] = response.meta.title
```
then in your template you can just do:

```html
<html>
    <head>
        <title>{{=current.response.meta.title}}</title>
        {{include_meta}}
    </head>
```

and you will have all the meta tags written down in your html.

Message flashing
----------------

When you need to store a message a the end of a request, and access it at the next one, to show, for example, a success alert to the user, weppy's `response.alerts()` became quite handy.

Let's say you have function which exposes a form, you can use message flashing to alert the user the form was accepted:

```python
from weppy.helpers import flash

@app.route("/someurl")
def myform():
    form = Form()
    if form.accepted:
        flash("We stored your question!")
    return dict(form=form)
```

then in your template you can access the flashed messages using `response`:

```html
<div class="container">
    {{for flash in response.alerts():}}
    <div class="myflashstyle">{{=flash}}</div>
    {{pass}}
</div>
```
and style them as you prefer.

`flash()` and `response.alerts()` also accepts a category filtering, so you can do:

```python
flash('message1', 'error')
response.alerts(category_filter=["error"])
``` 

or you can receive all flash messages with their category:

```
>>> response.alerts(with_categories=True)
[('error', 'message1')]
```
