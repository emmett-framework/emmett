Pipeline
========

*Changed in 2.0*

Quite often, you will need to perform operations during the request flow, for example you might need to verify certain authorization conditions before your exposed method is invoked by Emmett when the request is routed trough it, or you may want to close a database connection once the request flow is ended and the response is ready to be transmitted to the client.

Emmett uses a *pipeline* to handle the request flow trough your application, and like a water pipeline is composed of several pipes. You've already encountered some of them in the tutorial, the database and the auth ones. But how this pipes works inside the pipeline?

The flow
--------

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

> **Note:** the order on which the `open` and `close` methods get called is not guaranteed. In general, if you need the execution order of your code to be preserved, use the `pipe` method instead of the `open` or `close` ones.

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

Requests and sockets
--------------------

*Added in version 2.0*

The `Pipe`'s methods we saw until now are commonly handled by Emmett on all the routes you define, without distinction between routes handling requests and routes handling websockets.

But since handling the former or the latter ones make a great difference in terms of *flow*, `Pipe`s objects also have two dedicated methods for websockets only, and in particular:

- on\_receive
- on\_send

These two methods accepts only one argument: the message; and they will be called sequentially when receiving or sending messages. Here is an example:

```python
class WSPipe(Pipe):
    def on_receive(self, data):
        return {'original_message': data, 'stripped_message': data.strip()}

    def on_send(self, data):
        return json.dumps(data)
```

Also, while your application scales and grows into complexity, you might need to have a single `Pipe` object behaving differently depending on when is applied on a request route or a websocket one. This is perfectly achievable in Emmett, since the majority of methods we saw in the previous section can also be specialized. For example, let's say we want to rewrite the authentication example from above in order to use it also on websockets:

```python
from emmett import request, websocket

class AuthPipe(Pipe):
    async def pipe_request(self, next_pipe, **kwargs):
        if self.valid_header(request):
            return await next_pipe(**kwargs)
        return "Bad auth"

    async def pipe_ws(self, next_pipe, **kwargs):
        if self.valid_header(websocket):
            return await next_pipe(**kwargs)
        return

    def valid_header(self, wrapper):
        return wrapper.headers.get("my-header", "") == "MY_KEY"
```

To summarize, here is the complete table of methods available on Emmett pipes:

| common | request | websocket |
| --- | --- | --- |
| open | open\_request | open\_ws |
| close | close\_request | close\_ws |
| pipe | pipe\_request | pipe\_ws |
| on\_pipe\_success | | |
| on\_pipe\_failure | | |
| | | on\_receive |
| | | on\_send |

Pipeline composition
--------------------

One of the advantages in using Emmett pipeline is the capability to compose different flows inside the application depending on the specific needs. Since routes and [modules](./app_and_modules#application-modules) can add their own pipes to the application pipeline, it gets very easy to modularize the pipeline of your application accordingly.

As an example, let's say your application has a group of routes rendering templates and another group consisting of APIs. Then maybe you won't need the sessions in your APIs module, and you want to use JSON for your APIs, and thus you can split the pipeline:

```python
app.pipeline = [db.pipe]


front = app.module(__name__, 'front')
front.pipeline = [SessionManager.cookies('GreatScott!')]

apis = app.module(__name__, 'apis', url_prefix='api')
apis.pipeline = [ServicePipe('json')]
```

and maybe you will use the included authentication system for the front part, while your own authentication system for the APIs, in which you have some authenticated endpoints and some of them open:

```python
front = app.module(__name__, 'front')
front.pipeline = [
    SessionManager.cookies('GreatScott!'),
    auth.pipe
]

apis = app.module(__name__, 'apis', url_prefix='api')
apis.pipeline = [ServicePipe('json')]

secure_apis = apis.module(__name__, 'secure')
secure_apis.pipeline[MyAuthPipe()]
```

As you can see the level of composition you can implement over your application's pipeline is limitless.

Injectors
---------

*Changed in version 2.0*

A common scenario you may encounter while building your application is when you need to add the same contents to your exposed functions' outputs, to make them available for the templates.

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

Instead of adding `prettydate` to every exposed function output, you can write down an injector:

```python
from emmett import Injector

class DateInjector(Injector):
    namespace = "dates"

    def pretty(d):
        # your prettydate code

app.injectors = [DateInjector()]
```

and access your helper in every template writing:

```html
<div>{{ =dates.pretty(object.created_at) }}</div>
```

So, basically, the `Injector` class of Emmett adds everything you define inside it (functions and attributes) into your exposed functions' returning dictionary under the namespace you defined.

You can also expose all the contents of your injectors without specifying the namespace attribute:

```python
from emmett import Injector

class CommonInjector(Injector):
    def pretty_date(d):
        # your prettydate code

app.injectors = [CommonInjector()]
```

and directly access them:

```html
<div>{{ =pretty_date(object.created_at) }}</div>
```

> **Note:** injectors without a namespace are significally slower than the other ones.
