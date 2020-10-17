Extensions
==========

Emmett extensions extend the functionality of Emmett in various different ways.

Extensions are Python packages that can be downloaded with `pip`. When adding extensions to your application, it is a good habit to declare them as dependencies in your *requirements.txt* or *setup.py* file: this way, they can be installed with a simple command or when your application installs.

Using extensions
----------------

An extension typically has accompanying documentation that shows how to use it correctly. In general, Emmett extensions should be named with the format `emmett-foo` and have a package-name like `emmett_foo`, replacing foo with the desired name. If the extension is written according to the suggested pattern, using it in your 
application will be quite easy:

```python
from emmett import App
from emmett_foo import Foo

app = App(__name__)

# configure the extension
app.config.Foo.someparam = "something"
# add the extension to our app
app.use_extension(Foo)
# access extension attributes and methods
app.ext.Foo.bar()
```

That's all.   

As you can see, extensions have a *namespace* that accesses your app's configuration, and after you have added the extension to your application using the `use_extension()` method, you can access the extension instance at `app.ext.<extension_name>`.


Building extensions
-------------------

The first step in creating a new extension for Emmett is writing an `Extension` subclass:

```python
from emmett.extensions import Extension

class Awesomeness(Extension):
    default_config = {}

    def on_load(self):
        # pass
```

As you can see, the `Extension` class in actually quite simple, since you just have to write down the default configuration (if needed) and override the `on_load` method, that will be called by the framework when the extension will be initialised.

You can access three attributes of the extension instance, that are injected by Emmett before calling the `on_load` method, in particular you will have:

| attribute | description |
| --- | --- |
| app | the application on which the extension is loaded |
| config | a `sdict` containing the configuration |
| env | a `sdict` reserved to the extension where data can be stored |

The `config` attribute will contain the configuration defined by the developer using the extension, with the default attributes you defined in the `default_config` if not specified differently.

The developer will access `app.config.Awesomeness` in order configure the extension, in fact Emmett uses the name of your class as namespace for the configuration and environment objects. If you want to specify a different namespace, you can use the relevant attribute:

```python
class Awesomeness(Extension):
    namespace = "Foobar"
```

just remember to update the documentation of your extension accordingly.

Since the extension can access the application object, it can easily do anything, for example it may define a route:

```python
class Awesomeness(Extension):
    def on_load(self):
        self.app.route('/awesome')(awesome_route)

async def awesome_route():
    return {'message': 'Awesome!'}
```

### Using signals

*Changed in version 2.1*

Whenever you need to perform more specific actions depending on the status of the application, and the `on_load` method is not enough, you can use signals. Emmett provides these signal for extensions:

| signal name | parameters | description |
| --- | --- | --- |
| before\_routes | | triggered before the first route is defined in the application |
| before\_database | | triggered before the database is defined in the application |
| after\_database | database | triggered after the database has been defined in the application |
| before\_route | route, f | triggered before a single route is defined |
| after\_route | route | triggered after a single route is defined |
| after\_loop | loop | triggered after asyncio loop gets initialized |

Note that the `after_database` pass the database instance as parameter, the `before_route` the route instance and the decorated method, and the `after_route` just the route instance.

> **Note:** all the signals are referred to the application load, none of them will be triggered during the requests flow.

All these signals can be quite handy for specific operations. For example, let's say your extension wants to add a pipe into the application pipeline. Doing this within the `on_load` won't be safe, since you don't know if the developer will change the pipeline after the load of your extension on the application. It's, instead, more appropriate using the `before_routes` signal for this: 

```python
from emmett.pipeline import Pipe
from emmett.extensions import Extension, Signals, listen_signal

class AwesomePipe(Pipe):
    # some code
    
class Awesomeness(Extension):
    @listen_signal(Signals.before_routes)
    def inject_pipe(self):
        self.app.pipeline.append(
            AwesomePipe()
        )
```

And if you need the database, you can use the `after_database` method:

```python
class Awesomeness(Extension):
    @listen_signal(Signals.after_database)
    def bind_database(self, database):
        self.db = database
```

> **Warning:** the `listen_signal` decorator is usable only on methods of an `Extension` subclass.
