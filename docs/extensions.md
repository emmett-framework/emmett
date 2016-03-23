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

*section under development*
