Applications and modules
========================

weppy applications are based on the `App` core class: let's focus on this foundamental component and on the convenient `AppModule`.

The App object
--------------

As you learned from the [Getting started](./quickstart) chapter, your application is defined using the `App` class of weppy:

```python
from weppy import App
app = App(__name__)
```

Actually, the `__init__` method of this class looks like this:

```python
def __init__(self, import_name, root_path=None,
             template_folder='templates', config_folder='config'):
    # internal code
```

let's see then the full parameters list in detail:

| parameter | explaination |
| --- | --- |
| import_name | gives weppy an idea what belongs to your application, usually using `__name__` will work out of the box, but you can hardcode the name of your application package for safety |
| root_path | allows you to set a custom root path for your application, this is most of times not needed |
| template_folder | allows you to set a different folder for your application's templates (by default weppy uses the *templates* folder |
| config_folder | allows you to set a different configuration folder for your application, in the case you load configuration form files |

Since we introduced the `config_folder` parameter, let's see some details about application configuration.

### Application's configuration

The `App` object provides a `config` attribute to let you configure your application easily. The `config` object is something like a python dictionary with a friendly syntax and the characteristic of *sub-namespace auto-creation*.   
What does it means? That you likely wants to have the configuration divided into *categories*, separating for example the database configuration values from the ones of the authorization layer or an extension. So you can simply write:

```python

from weppy import App
app = App(__name__)

app.config.foo = "bar"
app.config.db.adapter = "mysql"
app.config.db.host = "127.0.0.1"
app.config.Haml.set_as_default = True
```

without creating dictionaries for `db` or `Haml` directly.

You can also load configuration from external files like *yaml*, let's see an example. With this application structure:

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

and your config will be loaded. As you can see with the second line, when you call `config_from_yaml()` method, you can pass the namespace under which weppy should load the configuration.


Application modules
-------------------

When your app starts becoming quite structured, having all our functions under a single file can be quite painful. When you reach this level of complexity, or even if you just want to better organize your application, you can use the `AppModule` class provided by weppy.

How does them work? Let's see an example. We can structure our application using a python package like this:

```
/myapp
    __init__.py
    blog.py
    templates/
```

The *\_\_init\_\_.py* is now our prior *app.py* with:

```python
from weppy import App
app = App(__name__)

@app.route("/")
def index():
    # code

import blog
```

and we can write in *blog.py*:

```python
from weppy import AppModule
from myapp import app

blog = App(app, "blog", __name__)

@blog.route("/blog")
def index():
    # code
```

And we now have a better organization as we have separated our blog code from the core application. As you have noticed, the `AppModule` object provides its own `route` method (you should heard of this method in the [Getting Started](./quickstart) chapter). Why is that?   
The main reason is that `AppModule` paramters accepts routing prefixes and hosts configuration, so that we can re-write *blog.py* module like this:

```python
blog = App(app, "blog", __name__, url_prefix="blog")

@blog.route("/")
def index():
    # code
```
and we get the same result as before, but with the convenient reduced syntax to route all the function we expose from blog module to */blog/[route]*.

This is the complete list of parameters accepted by `AppModule`:

| parameter | explaination |
| --- | --- |
| app | the weppy application to load module on |
| name | name for the module, it will used by weppy as the namespace for building urls on internal routing |
| import_name | same as we seen for the `App` object |
| template_folder | allows you to set a specific sub-folder of your application template path for module templates |
| template_path | allows you to set a specific folder inside your module root path for module templates |
| url_prefix | allows you to set a prefix path for module urls |
| hostname | allows you to set a specific hostname for module |
| root_path | same as we seen for the `App` object |

As you can see with the `hostname` parameter we can bind the module to a specific host, instead of using the url prefix. Considering our blog example we can bind it to *blog.ourhost.tld*.

We wrote that the `name` parameter of `AppModule` object is instead used by weppy for the *namespacing* of the urls. To completely understand this and to dive more in subsequents considerations, we remind you to the [Routing](./routing) chapter.
