Handling requests
=================

Emmett provides several instruments to help you dealing with requests in your
application. Let's see them. 

The request object
------------------
When a request comes from a client, Emmett binds useful informations about it
within the `request` object, which can be accessed just with an import:

```python
from emmett import request
```

It contains useful information about the current processing request, in particular:

| attribute | description |
| --- | --- |
| scheme | could be *http* or *https*|
| method | the request HTTP method |
| now | a pendulum Datetime object created with request|
| headers | the headers of the request |
| cookies | the cookies passed with the request |
| client | the IP Address of the client doing the request (if available) |
| environ | contains raw environment variables of the request |
| isajax | boolean which states if the request was made in AJAX (check for *xmlhttprequest* presence in headers) |

Please keep in mind that the `now` attribute will always use the UTC timezone, by default.

If you need to access the *local* time of the request you can use `now_local`:

```python
# request datetime in local machine timezone
request.now_local
```

> **Note:** since `now` is a [pendulum Datetime](https://pendulum.eustace.io/) object, you can easily change the timezone using the `in_timezone` method, like `request.now.in_timezone('Europe/Berlin')`.

Now, let's see how to deal with request variables.

### Request variables

Emmett's `request` object also provides three important attributes about the
active request:

| attribute | awaitable | description |
| --- | --- | --- |
| query_params | no | contains the URL query parameters |
| body_params | yes | contains parameters passed into the request body |
| params | yes | contains both the query parameters and the body parameters |

All three attributes work in the same way, within the exception of requiring `await` or not, and an example may help you understand their dynamic:

```python
from emmett import App, request

app = App(__name__)

@app.route("/post/<int:id>")
async def post(id):
    editor = (await request.params).editor
    if editor == "markdown":
        # code
    elif editor == "html":
        # code
    #..
```

Now, when a client calls the URL */post/123?editor=markdown*, the `editor` parameter
will be mapped into `request.params` and we can access its value simply calling
the parameter name as an attribute.

When the URL doesn't contain the query parameter you're trying to look at, this
will be `None`, so it's completely safe to call it. It wont raise an exception.

Now, what happens when the client does a *POST* request with the following body
on the URL */post/123?editor=markdown*?

```json
{
    "text": "this is an example post",
    "date": "2014-10-15"
}
```

Simple: the three `request` attributes will look like this:

```
>>> request.params
<sdict {'date': '2014-10-15', 'text': 'this is a sample post', 'editor': 'markdown'}>
>>> request.query_params
<sdict {'editor': 'markdown'}>
>>> request.body_params
<sdict {'date': '2014-10-15', 'text': 'this is a sample post'}>
```
You can always access the variables you need.

Pipeline
--------

*Changed in 1.0*

Quite often, you will need to perform operations during the request flow, for example you might need to verify certain authorization conditions before your exposed method is invoked by Emmett when the request is routed trough it, or you may want to close a database connection once the request flow is ended and the response is ready to be transmitted to the client.

Emmett uses a *pipeline* to handle the request flow trough your application, and like a water pipeline is composed of several pipes. You've already encountered some of them in the tutorial, the database and the auth ones. But how this pipes works inside the pipeline?

You can imagine the pipeline as a real water pipeline, composed of several pipes one after another:

```
          |<----  pipeline   ---->|
          |-------|-------|-------|
[request] -> pipe -> pipe -> pipe -> [route]
          |-------|-------|-------| 
```

The request will *flow* trough the pipeline, which means will flow trough every pipe in the pipeline, and will reach the method you've exposed for that specific route.

> – Ok dude. So the pipeline is just an array of functions that will perform some actions on the request?   
> – *Not really.*

The pipes are not just functions but actually objects. In fact, these pipes won't just *pipe* the request trough the pipeline flow, but will have several options and responsibilities on the pipeline. Emmett will use several functions on these objects during the request, so the application can customize the request flow based on its needs.

Any pipe can, in fact, perform operations before the request will be piped, during the flow, or after the flow has been completed. This is because any request in Emmett can be sketched in several steps above the pipeline.

First of all, Emmett will open up all the pipes in the pipeline:

```
         open   open   open
          |------|------|------|
[request] | pipe | pipe | pipe | [route]
          |------|------|------| 
```

You can imagine the pipes have *bulkheads* on their *entrance* and before the request is actually processed all these bulkheads are opened so that the request can flow trough the pipes.

After this first step, Emmett will push the request trough the pipeline:

```
         ->     ->     ->     ->
          |------|------|------|
[request] | pipe | pipe | pipe | [route]
          |------|------|------| 
```

During this step, all the pipes will *pipe* the request trough the next step in the pipeline. Every step in the pipeline will compose the final flow of the request from the client to the routed method.

Then the route method will compose a response, that will flow back trough the pipeline:

```
           <-     <-     <-     <-
           |------|------|------|
[response] | pipe | pipe | pipe | [route]
           |------|------|------| 
```

So the pipeline is actually walked by both sides and the pipes have access to the response as well.

Finally, Emmett will close all the pipes and send the response to the client:

```
          close  close  close  
           |------|------|------|
[response] | pipe | pipe | pipe | [route]
           |------|------|------| 
```

The *bulkheads* we imagined on the first step will be closed since the request *flow* is ended and nothing have to pass trough the pipeline.

All these steps lead to have this `Pipe` class that you can extend to build your custom pipelines:

```python
from emmett import Pipe

class MyPipe(Pipe):
    async def open(self):
        pass
    async def close(self):
        pass
    async def pipe(self, next_pipe, **kwargs):
        return await next_pipe(**kwargs)
    async def on_pipe_success(self):
        pass
    async def on_pipe_failure(self):
        pass
```

As we seen in the steps, the `open` and `close` method will be called before the request will flow trough the pipeline and after the response is built.

The `pipe` method is the one called by Emmett to *pipe* the request trough the pipeline: this means that every pipe is actually responsible to build the flow to the next pipe. And, this also means every pipe can alter the normal flow of the pipeline if needed.

The `on_pipe_success` and `on_pipe_failure` will be called as soon as the flow gets back to the pipe: the failure one will be invoked in case of an exception in any subsequent point of the pipeline, otherwise the success one will be invoked.

Notice that the `close` method will be always invoked on the pipeline, even if an exception occurred.

So how you can use these pipes functions? Let's see some examples.

A pipe responsible of connecting to the database will need to open the connection on a new request, and close the connection when the request flow is ended. Then we can write a pipe like this:

```python
class DBPipe(Pipe):
    def __init__(self, db):
        self.db = db
    async def open(self):
        self.db.open_connection()
    async def close(self):
        self.db.close_connection()
```

But we also can make it more smart, and have it commit what happened on the database when everything went right, or rollback the changes if something wrong happened:

```python
class DBPipe(Pipe):
    def __init__(self, db):
        self.db = db
    async def open(self):
        self.db.open_connection()
    async def close(self):
        self.db.close_connection()
    async def on_pipe_success(self):
        self.db.commit()
    async def on_pipe_failure(self):
        self.db.rollback()
```

Then we can add this pipe to a single route:

```python
@app.route(pipeline=[DBPipe(db)])
async def foo():
    #code
```

or on every route of our application:

```python
app.pipeline = [DBPipe(db)]
```

This makes you sure every request that have this pipeline will have a correct behaviour with the database. And this is more or less what the `Database.pipe` attribute does.

A second example could be a pipe that verifies the request authorization checking the value of a specific header. In this case we want to break the request flow if the client is not authorized and return an error instead of the content of the route. We can modify the `pipe` method for this:

```python
from emmett import Pipe, request, abort

class AuthPipe(Pipe):
    async def pipe(self, next_pipe, **kwargs):
        if self.valid_header():
            return await next_pipe(**kwargs)
        return "Bad auth"
        
    def valid_header(self):
        return request.headers.get("my-header", "") == "MY_KEY"
```

Adding this pipe to a route pipeline will make you sure the request will never flow trough the next pipe unless the condition is verified. In case of an abort the response that will be available to the pipes before the one interrupting the flow will be the content returned by this pipe.

For example, in case the `AuthPipe` is in the second position of our pipeline and the request is not authorized, the flow can be sketched like this:

```
1)
         open   open   open
          |------|------|------|
[request] | pipe | pipe | pipe | [route]
          |------|------|------| 
2)
         ->     ->
          |------|------|------|
[request] | pipe | pipe | pipe | [route]
          |------|------|------|
3)
           <-     <-
           |------|------|------|
[response] | pipe | pipe | pipe | [route]
           |------|------|------|
4)
          close  close  close  
           |------|------|------|
[response] | pipe | pipe | pipe | [route]
           |------|------|------| 
```

The last example is about the use of a pipe in order to change the parameters passed to the routed method. Let's say, for example that you have some routes that accept a `date` variable:

```python
@app.route("/foo/<date:start>")
async def foo(start):
    # code
```

and you often need to build a strict period starting from the `start` parameter, so your code looks like this:

```python
@app.route("/foo/<date:start>")
async def foo(start):
    end = start.add(days=7)
```

Then you can easily inject this to your routes writing a pipe:

```python
class PeriodPipe(Pipe):
    def __init__(self, days):
        self.dt = timedelta(days=days)

    async def pipe(self, next_pipe, **kwargs):
        kwargs['end'] = kwargs['start'] + self.dt
        return await next_pipe(**kwargs)
```

and using it on every route you need:

```python
@app.route("/foo/daily/<date:start>", pipeline=[PeriodPipe(1)])
async def foo_daily(start, end):
    # code
    
@app.route("/foo/weekly/<date:start>", pipeline=[PeriodPipe(7)])
async def foo_weekly(start, end):
    # code
    
@app.route("/foo/monthly/<date:start>", pipeline=[PeriodPipe(30)])
async def foo_monthly(start, end):
    # code
```

### A peculiar pipe: the Injector class

Another common scenario you may encounter while building your application is
when you need to add the same contents to your exposed functions' outputs,
to make them available for the templates.

For example, let's say you have a function that makes your datetimes objects prettier:

```python
>>> prettydate(datetime.now()-timedelta(days=1))
'One day ago'
```

And you want to use it in your templates:

```html
{{ for post in posts: }}
<div class="post">
  <div class="post-date">{{ =prettydate(post.date) }}</div>
  <div class="post-content">{{ =post.text }}</div>
</div>
{{ pass }}
```

Instead of adding `prettydate` to every exposed function, you can write down an injector:

```python
from emmett import Injector

class DateInjector(Injector):
    @staticmethod
    def prettydate(d):
        # your prettydate code

app.injectors = [DateInjector()]
```

and you can access your `prettydate` function in every template.

So, basically, the `Injector` class of Emmett adds everything you define inside it (functions and attributes) into your exposed functions' returning dictionary.

Errors and redirects
--------------------
Speaking of handling requests, you would like to perform specific actions on errors.

If we look at the given example for the `request.params` again, what happens when
the user calls the URL without passing the `editor` query parameter?

Maybe you want to redirect the client with a default parameter:

```python
from emmett import redirect, url

@app.route("/post/<int:id>")
async def post(id):
    editor = (await request.params).editor
    if editor == "markdown":
        # code
    elif editor == "html":
        # code
    else:
        redirect(url('post', id, params={'editor': 'markdown'}))
```

which means that, when the `editor` var is missing, we force the user to markdown.

The `redirect` function of Emmett accepts a string for the URL, and acts like
an exception, interrupting the execution of your code.

Maybe, you prefer to show your 404 page:

```python
from emmett import abort

@app.on_error(404)
async def not_found():
    return app.render_template("404.html")

@app.route("/post/<int:id>")
async def post(id):
    editor = request.params.editor
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

[next](response.md)
[index](README.md)