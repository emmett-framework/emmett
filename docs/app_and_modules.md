Applications and modules
========================

weppy applications are based on the `App` core class. Let's focus on this 
fundamental component and on the convenient `AppModule`.

The App object
--------------

As you learned from the [Getting Started](./quickstart) chapter, your application is defined using weppy's `App` class:

```python
from weppy import App
app = App(__name__)
```

The signature of this class's `__init__` method looks like this:

```python
def __init__(self, import_name, root_path=None,
             template_folder='templates', config_folder='config'):
    # internal code
```

Let's see the full parameters list in detail:

| parameter | explanation |
| --- | --- |
| import_name | gives weppy an idea of what belongs to your application, usually using `__name__` will work out of the box, but you can hardcode the name of your application package if you wish |
| root_path | allows you to set a custom root path for your application, which is usually unnecessary |
| template_folder | allows you to set a different folder for your application's templates (by default weppy uses the *templates* folder |
| config_folder | allows you to set a different configuration folder for your application, if you wish to load your configuration from files |

Since we introduced the `config_folder` parameter, let's see some details
about application configuration.

### Application's configuration

The `App` object provides a `config` attribute to let you configure your
application easily. The `config` object is something like a Python dictionary,
with a friendly syntax and the characteristic of *sub-namespace auto-creation*.   
What does that mean? That you likely want to have the configuration
divided into *categories*, separating the database configuration values
from the particulars of your authorization layer or an extension. 
You can simply write:

```python

from weppy import App
app = App(__name__)

app.config.foo = "bar"
app.config.db.adapter = "mysql"
app.config.db.host = "127.0.0.1"
app.config.Haml.set_as_default = True
```

without creating dictionaries for `db` or `Haml` directly.

You can also load configuration from external files like *yaml*, 
so let's see an example. With this application structure:

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

and your configuration will be loaded. As you can see, 
when calling `config_from_yaml()`, you can pass the name
of the namespace under which weppy should load the configuration.


Application modules
-------------------

When your app's structure starts to come together, having all the functions 
under a single file can be quite inconvenient. When you reach this level 
of complexity, or even if you just want to improve your application's 
organization, you can use the `AppModule` class provided by weppy.

How does this work? Let's see an example. We can structure our application 
using a Python package like this:

```
/myapp
    __init__.py
    blog.py
    templates/
```

Our *app.py* has become our new *\_\_init\_\_.py*:

```python
from weppy import App
app = App(__name__)

@app.route("/")
def index():
    # code

import blog
```

*blog.py* looks like this:

```python
from weppy import AppModule
from myapp import app

blog = AppModule(app, "blog", __name__)

@blog.route("/blog")
def index():
    # code
```

The blog code has now been separated from the core application.
As you may have noticed, the `AppModule` object provides its own `route` method,
which you would have seen before in the [Getting Started](./quickstart) chapter.
The route is included with the `AppModule` constructor so that we can 
re-write the *blog.py* module like this:

```python
blog = AppModule(app, "blog", __name__, url_prefix="blog")

@blog.route("/")
def index():
    # code
```
to get the same result as before, but with the syntax reduced conveniently
to route functions exposed by the blog module to */blog/[route]* automatically.

This is the complete list of parameters accepted by `AppModule`:

| parameter | explaination |
| --- | --- |
| app | the weppy application to load module on |
| name | name for the module, it will used by weppy as the namespace for building URLs on internal routing |
| import_name | same as we seen for the `App` object |
| template_folder | allows you to set a specific sub-folder of your application template path for module templates |
| template_path | allows you to set a specific folder inside your module root path for module templates |
| url_prefix | allows you to set a prefix path for module URLs |
| hostname | allows you to set a specific hostname for module |
| root_path | same as we seen for the `App` object |

As you can see, we can bind the module to a specific host with the `hostname` 
parameter, instead of using `url_prefix`. Considering our blog example, 
we can bind it to *blog.ourhost.tld*.

We mentioned that the `name` parameter of `AppModule` object is instead used 
by weppy for the *namespacing* of the URLs. To completely understand this 
and to dive into subsequent considerations, you can read the 
[Routing](./routing) chapter.
