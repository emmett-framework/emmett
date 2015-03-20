Upgrading to newer releases
===========================

Just like any software, weppy is changing over time, and most of these changes we introduce don't require you to change anything into your application code to profit from a new release.

Sometimes, indeed, there are changes in weppy source code that do require some changes or there are possibilities for you to improve your own code quality, taking advantage of new features in weppy.

This section of the documentation reports all the main changes in weppy from one release to the next and how you can (or you *should*) update your application's code to have the less painful upgrade experience.

Just as a remind, you can update weppy using *easy_install*:

```bash
$ easy_install -U weppy
```

or *pip*:

```bash
$ pip install -U weppy
```

Version 0.3
-----------

weppy 0.3 introduces a caching system for the templates. This change add a new configuration value under `app.config.templates_auto_reload` which is default set to `False`.   
This means that, under default behavior, in production weppy won't re-process the template files when modified, unless you reload the wsgi process. If you want to have the old behavior, so that weppy re-process the template file when it's modified, simply set the `templates_auto_reload` variable to `True`.   
Also remind that when your application is in *debug* mode – which means when it's loaded with the builtin wsgi server – the configuration setting is ignored and templates are auto reloaded by default.


Version 0.2
-----------

weppy 0.2 introduces some major changes in the code that break backward compatibility among the 0.1 *developer preview*. These changes were made to simplify the coding flow for developers and to have more consistent APIs.

If you're upgrading your application from weppy 0.1, next paragraphs describe the changes relevant for your application.

### sdict in place of Storage

The `Storage` class previously available under `weppy.storage` has moved to the more convenient `sdict` one. `sdict` behaves exactly the same as `Storage`, you just need to update references you have in your application, and the imports. You can import `sdict` directly from weppy writing:

```python
from weppy import sdict
```

### DAL changes
weppy 0.2 uses new [pyDAL](https://github.com/web2py/pydal) package instead of the old fork of the *web2py*'s DAL. Due to this new implementation, we removed the old `ModelsDAL` class and unified the two classes under the `DAL` one. Moreover, the `weppy.dal.modules` package will no longer exists, so you should rewrite all your imports since everything that was in that package can be imported directly from `weppy.dal`:

```python
from weppy.dal import DAL, Field, Model, after_insert
```

Also, the old `ModelsDAL.define_datamodels()` method is now available as `DAL.define_models()`, please update the relevant line in your application:

```python
db.define_models([MyModel1, MyModel2])
```

Finally, the `Model` class now has only one `setup` method instead of the old list of `set_` methods. Please use only this method to configure your tables.

### Auth module changes
Due to `ModelsDAL` and `DAL` merge, we did the same to `ModelsAuth`. Now you should use `Auth` with the `usermodel` parameter, like this:

```python
auth = Auth(app, db, usermodel=User)
```

### Validators
We renamed **all** the validators available in weppy. We changed the nomenclature we were keeping from *web2py* to a *simpler* one (under our point of view *at least*). Here is the complete list of old names vs the new ones:

| old name | new name |
| --- | --- |
| IS_ALPHANUMERIC | isAlphanumeric |
| IS_INT_IN_RANGE | isIntInRange |
| IS_FLOAT_IN_RANGE | isFloatInRange 
| IS_DECIMAL_IN_RANGE | isDecimalInRange |
| IS_TIME | isTime |
| IS_DATE | isDate |
| IS_DATE_IN_RANGE | isDateInRange |
| IS_DATETIME | isDatetime |
| IS_DATETIME_IN_RANGE | isDatetimeInRange |
| IS_EMAIL | isEmail |
| IS_LIST_OF_EMAILS | isEmailList |
| IS_URL | isUrl |
| IS_JSON | isJSON |
| IS_IMAGE | isImage |
| IS_IPV4 | isIPv4 |
| IS_IPV6 | isIPv6 |
| IS_IPADDRESS | isIP |
| IS_LIST_OF | isListOf |
| IS_STRONG | isStrong |
| IS_EMPTY_OR | isEmptyOr |
| IS_NOT_EMPTY | isntEmpty |
| IS_IN_DB | inDb |
| IS_NOT_IN_DB | notInDb |
| IS_IN_SET | inSet |
| IS_LENGTH | hasLength |
| IS_EQUAL_TO | Equals |
| IS_MATCH | Matches |
| IS_UPLOAD_FILENAME | FilenameMatches |
| ANY_OF | anyOf |
| CLEANUP | Cleanup |
| CRYPT | Crypt |
| IS_LOWER | Lower |
| IS_UPPER | Upper |
| IS_SLUG | Slug |

Please not that we also removed the `IS_EXPR` validator. The reason for the removal is that we had to run an `exec` on the expression, which is not a *so good* operation, and you can actually achieve the same result writing your own validator. As an example, if you were writing this before:

```python
IS_EXPR('str(form.vars.a).endswith("asd")')
```

you can better define a custom validator:

```python
from weppy.validators import Validator

class EndsWithAsd(Validator):
    def __call__(self, value):
        if str(value).endswith('asd'):
            return (value, None)
        return (value, "value has to end with 'asd'")
```

### Streaming files from DAL
We renamed the old `stream_file()` method under `weppy.helpers` to the more convenient `stream_dbfile()`, plase update the lines involved in your code.   
The usage remains the same.

### New features
weppy 0.2 also introduces some new features you may want to take advantage of:

* json POST requests are now parsed to make the message data available into `request.post_vars`. If you want to use this feature, ensure to send the content to weppy with the *Content-Type* header set to *"application/json"*.   
* `SessionFSManager` is now available to store sessions on server's filesystem. For the complete usage please check the [Session chapter](./sessions) of the documentation.   
* `stream_file()` method under `weppy.helpers` allows you to stream a file stored into your application path, simply passing the location as the parameter: `stream_file("myfiles/book.pdf")`.   
* `xml` is now available under services to allow rendering content as XML
