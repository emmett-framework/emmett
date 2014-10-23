Extensions
==========

weppy extensions extend the functionality of weppy in various different ways.

Extensions are listed on the [Extension Registry](#) and can be downloaded with `easy_install` or `pip`. A good habit in adding extension to your application would be to declare them as dependencies in your *requirements.txt* or *setup.py* file: this way they will be installed with a simple command or when your application installs.

Using extensions
----------------

Extensions typically have documentation that goes along and shows how to correctly use them. In general, weppy extensions should be named in the format `weppy-Foo` and have a package-name like `weppy_foo`. If the extensions is written following the suggested pattern, using it in your application will be quite easy:

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
As you can see from the example, extensions have a *namespace* that access your app's configuration, and after you added the extension to your application using the `use_extension()` method, you can access the extension instance at `app.ext.<extension_name>`.


Building extensions
-------------------

*section under writing*
