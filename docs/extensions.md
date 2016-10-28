Extensions
==========

weppy extensions extend the functionality of weppy in various different ways.

Extensions are listed on the [Extension Registry](#) and can be downloaded with
`easy_install` or `pip`. When adding extensions to your application, it is a
good habit to declare them as dependencies in your *requirements.txt* or *setup.py*
file: this way, they can be installed with a simple command or when your application installs.

Using extensions
----------------

An extension typically has accompanying documentation that shows how to use it
correctly. In general, weppy extensions should be named with the format `weppy-foo`
and have a package-name like `weppy_foo`, replacing foo with the desired name.
If the extension is written according to the suggested pattern, using it in your 
application will be quite easy:

```python
from weppy import App
from weppy_foo import Foo

app = App(__name__)

# configure the extension
app.config.Foo.someparam = "something"
# add the extension to our app
app.use_extension(Foo)
# access extension attributes and methods
app.ext.Foo.bar()
```

That's all.   

As you can see, extensions have a *namespace* that accesses your app's configuration,
and after you have added the extension to your application using the `use_extension()`
method, you can access the extension instance at `app.ext.<extension_name>`.


Building extensions
-------------------

The first step in creating a new extension for weppy is writing an `Extension` subclass:

```python
from weppy.extensions import Extension

class Awesomeness(Extension):
    default_config = {}

    def on_load(self):
        # pass
```

As you can see, the `Extension` class in actually quite simple, since you just have to write down the default configuration (if needed) and override the `on_load` method, that will be called by the framework when the extension will be initialised.

You can access three attributes of the extension instance, that are injected by weppy before calling the `on_load` method, in particular you will have:

| attribute | description |
| --- | --- |
| app | the application on which the extension is loaded |
| config | a `sdict` containing the configuration |
| env | a `sdict` reserved to the extension where data can be stored |

The `config` attribute will contain the configuration defined by the developer using the extension, with the default attributes you defined in the `default_config` if not specified differently.

The developer will access `app.config.Awesomeness` in order configure the extension, in fact weppy uses the name of your class as namespace for the configuration and environment objects. If you want to specify a different namespace, you can use the relevant attribute:

```python
class Awesomeness(Extension):
    namespace = "Foobar"
```

just remember to update the documentation of your extension accordingly.

Since the extension can access the application object, it can easily do anything, for example it may define a route:

```python
class Awesomeness(Extension):
    def on_load(self):
        self.app.route('/somepath')(awesome_route)

def awesome_route():
    return {'message': 'Awesome!'}
```

or add a custom handler:

```python
class AwesomeHandler(Handler):
    # some code
    
class Awesomeness(Extension):
    def on_load(self):
        self.app.common_handlers.append(
            AwesomeHandler()
        )
```

### Template extensions

*section under development*
