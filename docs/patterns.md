Patterns for weppy
==================

weppy is crafted to fit the needs of many applications, from the smallest to the
largest ones. Due to this, your application can be built up from a single Python
file and scale to a better organized structure.

In this section, we will cover some good *patterns* you may follow when your
application starts becoming large, or when you just need to organize your code 
better.

Package pattern
---------------

The package pattern will make your application a Python package instead of a module.
For instance, let's assume your original application is structured like that:

```
/myapp
    myapp.py
    /static
        style.css
    /templates
        layout.html
        index.html
        login.html
        ...
```

To convert it to a package application, you should create another folder inside
your original *myapp* one, and rename *myapp.py* to *\__init__.py*, ending up
with something like this:

```
/myapp
    /myapp
        __init__.py
        /static
            style.css
        /templates
            layout.html
            index.html
            login.html
            ...
```

> – OK, dude. But what did we gain by doing this?   
> – *well, now we can organize the code in multiple modules*

With this new structure, we can create a new *views.py* file inside the package
and we can move the routed functions to it. For example, your *\__init__.py* file
can look like this:

```python
from weppy import App

app = App(__name__)
import myapp.views
```

and your *views.py* could look like:

```python
from myapp import app

@app.route("/")
def index():
    # some code
```

Your final structure would be like this:

```
/myapp
    /myapp
        __init__.py
        views.py
        /static
            style.css
        /templates
            layout.html
            index.html
            login.html
            ...
```

> – That's nice, but how can I run my application now?

You can use the weppy command inside the original directory of your application:

```bash
$ weppy --app myapp run
```

or you can create a *run.py* file inside your tree:

```
/myapp
    run.py
    /myapp
        __init__.py
        views.py
        /static
            style.css
        /templates
            layout.html
            index.html
            login.html
            ...
```

which can look like this:

```python
from myapp import app

app.run()
```

> **A note regarding circular imports:**   
> Every Python developer hates them, and yet we just added some of them: *views.py* depends on *\__init\__.py* while *\__init\__.py* imports *views.py*. In general, this is a bad idea, but it is actually fine here because we are not actually using the views in *\__init\__.py*. We are ensuring that the module is imported to expose the functions; also, we are doing that at the bottom of the file.

MVC pattern
-----------
The **MVC** (Model-View-Controller) pattern, used widely in web applications,
is well structured and becomes handy when you have big applications. 
weppy does not provide controllers, but you can implement an MVC pattern using 
`AppModule` objects. An MVC structure for a weppy application can look something
like this:

```
/myapp
    __init__.py
    /controllers
        __init__.py
        main.py
        api.py
    /models
        __init__.py
        user.py
        article.py
    /templates
        layout.html
        index.html
        login.html
        ...
```

As you can see, it's an extension of the *package pattern*, where we added the 
two sub-packages *controllers* and *models*, each with an empty *\__init__.py* file.

With this structure, your application's *\__init__.py* would look like this:

```python
from weppy import app, DAL

app = App(__name__)
app.url_default_namespace = "main"

db = DAL()
from models.user import User
form models.article import Post
db.define_models([User, Post])

from controllers import main, api
```

We told weppy to use the *main.py* controller as default for urls, so we can just
call `url('index')` instead of `url('main.function')` in our application.

The main controller can look like this:

```python
from myapp import app

@app.route("/")
def index():
    # code
```

and the *api.py* controller can look like this:

```python
from weppy import AppModule
from myapp import app

api = AppModule(app, 'api', __name__, url_prefix='api')

@api.route()
def a():
    # code
```
