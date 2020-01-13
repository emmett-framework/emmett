Caching
=======

When you code a dynamic application, you will soon face its trade-off: **it is** dynamic.

Each time a user does a request, your server makes all sorts of calculations – database queries, template rendering and so on – to create the final response. For most web applications, this is not a big deal, but when your application starts becoming big and highly visited you will want to limit the overhead on your machines.

That's where caching comes in.

The main idea behind cache is simple: we store the result of an expensive calculation somewhere to avoid repeating the calculation if we can. But, sincerely speaking, designing a good caching scheme is mainly a *PITA*, since it involves many complex evaluations about what you should store, where to store it, and so on.

So how can Emmett help you with this? It provides some tools out of the box that let you focus your development energy on *what* to cache and not on *how* you should do that.

Configuring cache
-----------------

The caching system in Emmett consist of a single class named `Cache`. Consequentially, the first step in configuring cache in your application is to create an instance of this cache in your application:

```python
from emmett.cache import Cache

cache = Cache()
```

By default, Emmett stores your cached content into the RAM of your machine, but you can also use the disk or redis as your storage system. Let's see these three handlers in detail.

### RAM cache

As we just saw, this is the default cache mechanism of Emmett. Initializing a `Cache` instance without arguments would be the same of using the `RamCache` handler:

```python
from emmett.cache import Cache, RamCache

cache = Cache(ram=RamCache())
```

The `RamCache` also accepts some parameters you might take advantage of:

| parameter | default value | description |
| --- | --- | --- |
| prefix | | allows to specify a common prefix for caching keys |
| threshold | 500 | set a maximum number of objects stored in the cache |
| default\_expire | 300 | set a default expiration (in seconds) for stored objects |

> **Note on multi-processing:**
> When you store data in RAM cache, you are actually using the python process' memory. If you're running your web application using multiple processes/workers, every process will have its own cache and the data you store wont be available to the other ones.  
> If you need to have a shared cache between processes, you should use the *disk* or *redis* ones.

### Disk cache

The disk cache is actually slower than the RAM or the redis ones, but if you need to cache large amounts of data, it fits the role perfectly. Here is how to use it:

```python
from emmett.cache import Cache, DiskCache

cache = Cache(disk=DiskCache())
```

The `DiskCache` class accepts some parameters too:

| parameter | default value | description |
| --- | --- | --- |
| cache\_dir | `'cache'` | allows to specify the directory in which data will be stored |
| threshold | 500 | set a maximum number of objects stored in the cache |
| default\_expire | 300 | set a default expiration (in seconds) for stored objects |

### Redis Cache

[Redis](http://redis.io) is quite a good system for caching: is really fast – *really* – and if you're running your application with several workers, your data will be shared between your processes. To use it, you just initialize the `Cache` class with the `RedisCache` handler:

```python
from emmett.cache import Cache, RedisCache

cache = Cache(redis=RedisCache(host='localhost', port=6379))
```

As we saw with the other handlers, `RedisCache` class accepts some parameters too:

| parameter | default value | description |
| --- | --- | --- |
| host | `'localhost'` | the host of the redis backend |
| port | 6379 | the port of the redis backend |
| db | 0 | the database number to use on the redis backend |
| prefix | `'cache:'` | allows to specify a common prefix for caching keys |
| default\_expire | 300 | set a default expiration (in seconds) for stored objects |

### Using multiple systems together

As you probably supposed, you can use multiple caching system together. Let's say you want to use the three systems we just described. You can do it simply:

```python
from emmett.cache import Cache, RamCache, DiskCache, RedisCache

cache = Cache(
    ram=RamCache(),
    disk=DiskCache(),
    redis=RedisCache()
)
```

You can also tells to Emmett what handler should be used when not specified, thanks to the `default` parameter:

```python
cache = Cache(m=RamCache(), r=RedisCache(), default='r')
```

Basic usage
-----------

*Changed in version 2.0*

The quickier usage of cache is to just apply it on a simple *action*, such as a select on the database or a computation. Let's say, for example, that you have a blog and a certain function that exposes the last ten posts:

```python
@app.route("/last")
async def last():
    rows = Post.all().select(orderby=~Post.date, limitby=(0, 10))
    return dict(posts=rows)
``` 

Now, since the performance bottleneck here is the call to the database, you can limit the overhead by caching the select result for 30 seconds, so you decrease the number of calls to your database:

```python
@app.route("/last")
async def last():
    def _get():
        return Post.all().select(orderby=~Post.date, limitby=(0, 10))
    return dict(posts=cache('last_posts', _get, 30))
```

Here's how it works: you encapsulate the action you want to cache into a function, and then call your `cache` instance with a key, the function, and the amount of time in seconds you want to store the result of your function. Emmett will take care of the rest.

You can also put in cache results coming from `async` operations, you just need to be sure to pass a coroutine function to the cache call. In this case the syntax will be preserved, and you need to `await` the cache call:

```python
async def _get():
    return 'value'

@app.route()
async def data():
    return dict(data=await cache('last_data', _get, 30))
```

> – OK, dude. What if I have multiple handlers? where does Emmett store the result?   
> – *you can choose that*

As we saw before, by default Emmett stores your cached content into the handler chosen as default. But you can choose on which handler you want to store data:

```python
cache = Cache(
    ram=RamCache(),
    disk=DiskCache(),
    redis=RedisCache(),
    default='ram'
)
v_ram = cache('my_key', my_f, my_time)
v_ram = cache.ram('my_key', my_f, my_time)
v_disk = cache.disk('my_key', my_f, my_time)
v_redis = cache.redis('my_key', my_f, my_time)
```

Decorating methods
------------------

*Changed in version 2.0*

Emmett's cache can also be used as a decorator. For example, we can rewrite the above example as follows:

```python
@cache(duration=30)
def last_posts():
    return Post.all().select(orderby=~Post.date, limitby=(0, 10))

@app.route("/last")
async def last():
    return dict(posts=last_posts())
```

and the result would be the same. The notation, in the case you want to specify the handler to use, is the same:

```python
# use redis handler
@cache.redis()
# use ram handler
@cache.ram()
```

When using the decorator notation, Emmett will use the arguments you pass to the decorated method to build different results. This means that if we decorate a method that accepts arguments like:

```python
@cache()
def cached_method(a, b, c='foo', d='bar'):
    # some code
```

then Emmett will cache different contents in case you call `cached_method(1, 2, c='a')` and `cached_method(1, 3, c='b')`.

The cache decorator also supports `async` methods:

```python
@cache()
async def get_data(page=1):
    await some_data(page)

@app.routes()
async def data():
    return dict(data=await get_data(request.query_params.page or 1))
```

Caching routes
--------------

*New in version 1.2*

Sometimes you would need to cache an entire response from your application. Emmett provides the `Cache.response` decorator for that. Let's rewrite the example we used above: this time, instead of caching just the database selection, we will cache the entire page that Emmett will produce from our route:

```python
@app.route("/last")
@cache.response()
async def last():
    posts = Post.all().select(orderby=~Post.date, limitby=(0, 10))
    return dict(posts=posts)
```

The main difference from the above examples is that, in case of available cached content, everything that would happened inside your route and template code won't be executed; instead, Emmett will return the final response body and its headers from the ones available in the cache.

> **Note:** this means that also nothing contained in the `pipe`, `on_pipe_success` and `on_pipe_failure` methods of the pipes in your route pipeline won't be executed. In case you need execution of code on cached routes you should use the `open` and `close` methods of the pipes.

Mind that Emmett will cache only contents on *GET* and *HEAD* requests that returns a 200 response code. This is intended to avoid unwanted cached mechanism on your application.

The `Cache.response` method accepts also some parameters you might want to use:

| parameter | default value | description |
| --- | --- | --- |
| duration | `'default'` | the duration (in seconds) the cached content should be considered valid |
| query\_params | `True` | tells Emmett to consider the request's query parameters to generate different cached contents |
| language | `True` | tells Emmett to consider the clients language to generate different cached contents |
| hostname | `False` | tells Emmett to consider the path hostname to generate different cached contents |
| headers | `[]` | an additional list of headers Emmett should use to generate different cached contents |

### Caching entire modules

In some cases, you might need to cache all the routes contained in an application module. In order to achieve this, you can use the `cache` parameter when you define your module:

```
mod = app.module(__name__, 'mymodule', cache=cache.response())
```

Low-level cache API
-------------------

*Changed in version 1.2*

As we saw in the sections above, the common usage of cache is to call the `Cache` instance with a callable object that will produce the cached contents in case they are not available in the cache.

In all the cases you need to perform operations on the cache dirrently, you can use the exposed methods of the `Cache` instance and its handlers. Let's see them in detail.

### Get contents

Every time you need to access contents from cache, you can use the `get` method:

```python
value = cache.get('key')
```

If no contents are available, this method will return `None`.

### Set contents

When you need to manually set contents in cache, you can use the `set` method:

```python
cache.set('key', 'value', duration=300)
```

> **Note:** if you want to store the result of a callable object, you should invoke it yourself.

You can implement a manual check-and-set policy using `get` and `set` methods:

```python
value = cache.get('key')
if not value:
    value = 'somevalue'
    cache.set('key', value, duration=300)
```

### Get or set

The last example can be written in a compact way using the `get_or_set` method:

```python
value = cache.get_or_set('key', 'somevalue', duration=300)
```

> **Note:** as we saw for the `set` method, if you want to store the result of a callable object, you should invoke it yourself.

### Async get or set

*New in version 2.0*

The `get_or_set` behaviour can also be used with awaitable functions and objects, just use the provided `get_or_set_loop` method for that:

```python
async def somefunction():
    return 'value'

value = await cache.get_or_set_loop('key', somefunction, duration=300)
```

### Clearing contents

Whenever you need to manually delete contents from cache, you can use the `clear` method:

```python
cache.clear('key')
```

And if you need to clear **the entire cache** you can invoke the clear method without arguments.

> **Note:** on redis, a key containing * will mean clearing all the existing keys with that pattern. So calling `cache.clear('user*')` will delete all the contents for keys starting with *user*.
