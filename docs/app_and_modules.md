Applications and modules
========================

Emmett applications are based on the `App` core class. Let's focus on this fundamental component and on the convenient application modules.

The App object
--------------

*Changed in version 1.3*

As you learned from the [Getting Started](./quickstart) chapter, your application is defined using Emmett's `App` class:

```python
from emmett import App

app = App(__name__)
```

The signature of this class's `__init__` method looks like this:

```python
def __init__(
    self,
    import_name: str,
    root_path: Optional[str] = None,
    url_prefix: Optional[str] = None,
    template_folder: str = 'templates',
    config_folder: str = 'config'
):
    # internal code
```

Let's see the full parameters list in detail:

| parameter | explanation |
| --- | --- |
| import_name | gives Emmett an idea of what belongs to your application, usually using `__name__` will work out of the box, but you can hardcode the name of your application package if you wish |
| root_path | allows you to set a custom root path for your application, which is usually unnecessary |
| url_prefix | allows you to set a global url prefix for routing |
| template_folder | allows you to set a different folder for your application's templates (by default Emmett uses the *templates* folder |
| config_folder | allows you to set a different configuration folder for your application, if you wish to load your configuration from files |

Since we introduced the `config_folder` parameter, let's see some details about application configuration.

### Application's configuration

The `App` object provides a `config` attribute to let you configure your application easily. The `config` object is something like a Python dictionary, with a friendly syntax and the characteristic of *sub-namespace auto-creation*.   
What does that mean? That you likely want to have the configuration divided into *categories*, separating the database configuration values from the particulars of your authorization layer or an extension. 
You can simply write:

```python

from emmett import App
app = App(__name__)

app.config.foo = "bar"
app.config.db.adapter = "mysql"
app.config.db.host = "127.0.0.1"
app.config.Haml.set_as_default = True
```

without creating dictionaries for `db` or `Haml` directly.

You can also load configuration from external files like *yaml*, so let's see an example. With this application structure:

```
/app.py
/config
    app.yml
    db.yml
```

and *app.yml* looking something like this:

```yaml
foo: bar
Haml:
  set_as_default: True
```

and *db.yml* looking like this:

```yaml
adapter: mysql
host: 127.0.0.1
```

you can write in your *app.py*:

```python
app.config_from_yaml('app.yml')
app.config_from_yaml('db.yml', 'db')
```

and your configuration will be loaded. As you can see, when calling `config_from_yaml()`, you can pass the name of the namespace under which Emmett should load the configuration.

Application modules
-------------------

*Changed in version 2.2*

When your app's structure starts to come together, you might benefit of packing routes together in common structures, so you can use the same route prefix or hostname, or to have a common pipeline.

Emmett provides application modules for this. You can create new modules using the `module` method of your application object. For example, let's say you have a minimal blog into your application. Then might be convenient create a module for it:

```python
blog = app.module(__name__, name="blog", url_prefix="blog")
```

With this single line we created a new module for our blogging system, that will have all the routes prefixed by the */blog* url we provided. Now, in order to add a new route to the module, we can use its `route` method, which has the same syntax of the application one:

```python
@blog.route("/")
async def index():
    # code
```

The resulting route will respond to the */blog* path, since the module have a defined prefix. For instance, if we define an archive route:

```python
@blog.route()
async def archive():
    # code
```

the final route will be */blog/archive*.

A part from the prefix, you can use several parameters when creating modules. Here is the complete list:

| parameter | explaination |
| --- | --- |
| import_name | same as we seen for the `App` object |
| name | name for the module, will be used by Emmett as the namespace for internal routing |
| template_folder | allows you to set a specific sub-folder of your application template path for module templates |
| template_path | allows you to set a specific folder inside your module root path for module templates |
| static_folder | allows you to set a specific sub-folder of your application static path for module assets |
| static_path | allows you to set a specific folder inside your module root path for module assets |
| url_prefix | allows you to set a prefix path for module URLs |
| hostname | allows you to set a specific hostname for module |
| root_path | same as we seen for the `App` object |

As you can see, we can bind the module to a specific host with the `hostname` parameter, instead of using `url_prefix`. Considering our blog example, we can bind it to *blog.ourhost.tld*.

We mentioned that the `name` parameter of the application modules is instead used by Emmett for the URLs *namespacing*. To completely understand this 
and to dive into subsequent considerations, you can read the 
[Routing](./routing) chapter.

You can also define a specific [pipeline](./request#pipeline) for the module, or a list of injectors, so all the routes defined on the model will consequentially use those:

```python
blog.pipeline = [BlogPipe()]
blog.injectors = [BlogInjector()]
```

And finally, you can create sub-modules starting from other modules.

### Sub-modules

One of the benefits of using modules is that you can create a hierarchy of them inside your application, in order to easily manage paths and pipelines.

Let's say, for example, you are building some JSON APIs in your application, and you want every route is prefixed with */apis*. Then you can easily create a module for them:

```python
apis = app.module(__name__, 'apis', url_prefix='apis')
```

Also, since you're using JSON as serialization, you can add the appropriate [service pipe](./services) to the pipeline:

```python
from emmett.tools import ServicePipe

apis.pipeline = [ServicePipe('json')]
```

Then, let's say you want to build the first version of your apis, so that they will be accessible from the */apis/v1* endpoint. You can create a submodule from the one you've just created with the same syntax:

```python
v1_apis = apis.module(__name__, 'v1', url_prefix='v1')
```

Then you can create an endpoint for a specific entity, let's say you want to make operations above the users of your application:

```python
users = v1_apis.module(__name__, 'users', url_prefix='users')

@users.route('/')
async def index():
    # code to return a list of users
    
@users.route('/<int:user_id>', methods='put')
async def update(user_id):
    # code to edit a user
```

At this point, the final endpoints for the users' index and update routes will be */apis/v1/users* and */apis/v1/users/1*.

All the submodule inherit the properties of the parent module, so all the prefixes will be compose to the final one. The same happens for the internal routing, since the names of the two routes will be *apis.v1.users.index* and *apis.v1.users.update*.

Every submodule can have its pipeline, that will be added consequentially to the parent one. For example, you might have different authorization systems between the first version of your apis and a new one:

```python
from emmett.tools import ServicePipe

apis = app.module(__name__, 'apis', url_prefix='apis')
apis.pipeline = [ServicePipe('json')]

v1_apis = apis.module(__name__, 'v1', url_prefix='v1')
v1_apis.pipeline = [SomeAuthPipe()]

v2_apis = apis.module(__name__, 'v2', url_prefix='v2')
v2_apis.pipeline = [AnotherAuthPipe()]
```

Then all the routes defined in these modules or in sub-modules of these modules will have a final pipeline composed by the one of the `apis` module, and the one of the sub-module.

Modules groups
--------------

*New in version 2.5*

Once your application structure gets more complex, you might encounter the need of exposing the same routes with different pipelines: for example, you might want to expose the same APIs with different authentication policies over different endpoint. 

In order to avoid code duplication, Emmett provides you modules groups. Groups can be created from several modules and provide you the `route` and `websocket` method, so you can write routes a single time from the upper previous example:

```python
from emmett.tools import ServicePipe

apis = app.module(__name__, 'apis', url_prefix='apis')
apis.pipeline = [ServicePipe('json')]

v1_apis = apis.module(__name__, 'v1', url_prefix='v1')
v1_apis.pipeline = [SomeAuthPipe()]

v2_apis = apis.module(__name__, 'v2', url_prefix='v2')
v2_apis.pipeline = [AnotherAuthPipe()]

apis_group = app.module_group(v1_apis, v2_apis)

@apis_group.route("/users")
async def users():
    ...
```

> **Note:** even if the resulting route code is the same, Emmett `route` and `websocket` decorators will produce a number of routes equal to the number of modules defined in the group

### Nest modules into groups

Modules groups also let you define additional sub-modules. The resulting object will be a wrapper over the nested modules, so you can still customise their pipelines, and use the `route` and `websocket` decorators:

```python
apis_group = app.module_group(v1_apis, v2_apis)
users = apis_group.module(__name__, 'users', url_prefix='users')
users.pipeline = [SomePipe()]

@users.route("/")
async def index():
    ...
```

> **Note:** *under the hood* Emmett will produce a nested module for every module defined in the parent group
