Upgrading to newer releases
===========================

Just like any software, Emmett is changing over time, and most of these changes we introduce don't require you to change anything into your application code to profit from a new release.

Sometimes, indeed, there are changes in Emmett source code that do require some changes or there are possibilities for you to improve your own code quality, taking advantage of new features in Emmett.

This section of the documentation reports all the main changes in Emmett from one release to the next and how you can (or you *should*) update your application's code to have the less painful upgrade experience.

Just as a remind, you can update Emmett using *pip*:

```bash
$ pip install -U emmett
```

Version 2.0
-----------

*Section under development*

Version 1.3
-----------

In weppy 1.3 we didn't introduced any breaking change or deprecation.

Still, version 1.3 removed any previous deprecation, so mind to remove any code deprecated in 1.2 version.

Upon this, weppy 1.3 introduces some new features you might be interested into:

- An additional parameter in ORM configuration to use [big integer fields](./dal/connecting#additional-configuration-parameters) for id and reference columns
- An `url_prefix` parameter to the application object to specify a [global prefix](./app_and_modules#the-app-object) for routing.
- A `migrations_folder` parameter in ORM configuration to specify specific folder to use with [migrations](./dal/migrations#using-custom-migration-folders).

weppy 1.3 also introduces official support for Python 3.7.


Version 1.2
-----------

In weppy 1.2 we rewritten the core logic of the templates engine. This won't change anything if you written an application with weppy, but if you built an extension using templates features, you should check out the [extensions](./extensions#building-extensions) chapter and inspect changes that may have possibly broke your code. Also, if your application uses templates extensions, please check out with the extension maintainer and be sure to upgrade it to the latest version.

Upon this, weppy 1.2 also introduces some deprecations you should be aware of, and some new features you might been interested into.

### Deprecation of session managers classes

In the previous versions, several classes were available to control sessions, in particular `SessionCookiesManager`, `SessionFSManager` and `SessionRedisManager` in the `sessions` module. 

Since we performed a rewrite of the code behind sessions management, we ended up building a single manager to simplify the usage for developers. The new syntax expects the usage of three class methods of the new available class `SessionManager`, so you can migrate your code as follows:

| old class | new implementation |
| --- | --- |
| `SessionCookiesManager` | `SessionManager.cookies` |
| `SessionFSManager` | `SessionManager.files` |
| `SessionRedisManager` | `SessionManager.redis` |

The old arguments are still valid, but we're also providing some new ones you might be interested into; please check the [Sessions chapter](./sessions) for more details.

The old classes are deprecated in weppy 1.2, so you can still use them, but we really suggest to update your application code to the new naming since the old ones will be definitely removed in the next version.

### New features

weppy 1.2 also introduces some new features:

- An additional parameter in ORM configuration to specify [time-based recycling](./dal/connecting) for pooled connections
- [Nested transactions](./dal/connecting#transactions) support in ORM
- Caching now allows decoration syntax and routes caching. Checkout [caching chapter](./caching) for details.


Version 1.1
-----------

weppy 1.1 introduces some minor breaking changes you should be aware of, and some new features you might been interested into.

### Breaking changes

#### Default value for Content-Type header

Before weppy 1.1 the *Content-Type* header value in the response was inflated considering an eventual extension format in the url. Since this operation wasted some time on the request flow, and due to the fact in a typical weppy application url extensions are not common, with this version we removed this functionality. 

Please note that the *Content-Type* header values are still set to the correct ones when using templates or the weppy services, so you won't have to change anything.

An edit is required only if you have routes where you used this feature. You just need to set the content type manually:

```python
from weppy import response

response.headers['Content-Type'] = 'application/xml'
```

Mind that you can also re-implement the old behavior manually using the `contenttype` method available in weppy libraries:

```python
from weppy import request, response
from weppy.libs.contenttype import contenttype

response.headers['Content-Type'] = contenttype(request.environ['PATH_INFO'])
```

### New features

With weppy 1.1 we introduced some new features:

- the forms now have a default widget for *decimal* fields
- auth module now supports [custom paths](./auth#change-routes-paths) for its routes
- the `Field` class now has methods to create fields with specific types: you can use the new syntax instead of using the old string argument


Version 1.0
-----------

weppy 1.0 introduces some deprecations and breaking changes you should be aware of, and some new features you might been interested into.

Next paragraphs describe all these relevant changes.

### Handlers deprecation in favour of pipeline

weppy 1.0 introduces the [pipeline](./request#pipeline), a revisited and better implementation of the old handlers.

While everything from the old implementation still works, we really suggest to update your code to the new implementation.

We changed the application and modules attributes and the `route` parameters as follows:

| old attribute or parameter | new name |
| --- | --- |
| common_handlers | pipeline |
| common_helpers | injectors |
| handlers | pipeline |
| helpers | injectors |

We also renamed the old handlers on database and auth instances, so you have to change this code:

```python
app.common_handlers = [db.handler, auth.handler]
```

to:

```python
app.pipeline = [db.pipe, auth.pipe]
```

In the case you wrote your own handlers with previous versions of weppy, you should now use the `Pipe` class instead of the `Handler` one:

```python
# old code
from weppy.handlers import Handler

class MyHandler(Handler):
    # some code

# new code
from weppy.pipeline import Pipe

class MyPipe(Pipe):
    # some code
```

and you should update the old methods with new ones (the usage is still the same):

| old method | new method |
| --- | --- |
| on\_start | open |
| on\_success | on\_pipe\_success |
| on\_failure | on\_pipe\_success |
| on\_end | close |

Moreover, if you customized the old `wrap_call` method in handlers, you should now use the `pipe` one, which doesn't require to wrap the input method into something else. In fact, with the `pipe` method, the code you write is already the wrapper for the next method in the pipeline. For example, this code:

```python
class MyHandler(Handler):
    def wrap_call(self, f):
        def wrapped(**kwargs):
            kwargs['foo'] = 'bar'
            return f(**kwargs)
        return wrapped
```

should now be written:

```python
class MyPipe(Pipe):
    def pipe(self, next_pipe, **kwargs):
        kwargs['foo'] = 'bar'
        return next_pipe(**kwargs)
```

Learn more about the pipeline in the [relevant chapter](./request#pipeline) of the documentation.

### DAL deprecation in favour of the orm module

Since the first version, the module relevant to database utilities was named *dal* in weppy. So it was for the class responsible of creating database instance, where *DAL* was an acronym for *Database Absraction Layer*.

We think this nomenclature wasn't immediate at all; moreover, during releases weppy built a real orm above pyDAL, and we felt the old name had to be changed.

Since weppy 1.0 all the imports from `weppy.dal` should be moved to `weppy.orm`, and the `DAL` class is now the more convenient `Database` class.

The old module and class are still available, but we suggest you to change the relevant code in your application since in the next versions of weppy these won't be available.

### form\_rw deprecation in favour of fields\_rw in Model

We changed the attribute for the fields accessibility in the `Model` class from `form_rw` to the proper `fields_rw` one.

While the old attribute still works in weppy 1.0, we suggest you to upgrade your models to the new attribute.

### Breaking changes

#### Automatic migrations disabled by default

In weppy 1.0 the `auto_migrate` parameter of the `Database` class has changed its default value from `True` to `False`. If your application relies on automatic migrations, please change the initialization of the database passing the new value for the parameter:

```python
db = Database(app, auto_migrate=True)
```

#### Auth module and mailer refactoring

In weppy 1.0 the auth system and the mailer available under the *tools* module have been completely rewritten from scratch.

While quite a lot of APIs can be used in the same way of the old modules, there are some big differences that breaks the compatibility with applications written with previous weppy versions.

The first breaking change regards the columns' names in the auth tables, that should be migrated before the upgrade as follows:

| table | old column name | new column name |
| --- | --- | --- |
| auth\_memberships | authgroup | auth\_group |
| auth\_permissions | authgroup | auth\_group |

This means also the many relations in the models has changed:

| old name | new name |
| --- | --- |
| authgroups | auth\_groups |
| memberships | auth\_memberships |
| permissions | auth\_permissions |
| events | auth\_events |

The other two major breaking changes are the parameter name for the user model when you instantiate the module, changed from `usermodel` to `user_model`:

```python
auth = Auth(app, db, user_model=User)
```

And the way of exposing routes, that now uses a module. Please, inspect the [appropriate chapter](./auth) of the documentation to better understand this and other changes.

Now the documentation offers also a [dedicated chapter](./mailer) for the mailing system, check it out to learn how it works in the new version.

#### Renamed tags module into html

Prior to weppy 1.0 all the code to generate html components from weppy was under the debatable `tags` module. Since the naming led to ambiguities, we changed the name to the more correct `html` one.

Please update your code accordingly.

#### Removed the bind\_to\_model option from virtual decorators

Prior to weppy 1.0 you had the option to not bind the virtual attributes to the model namespace on selections:

```python
@rowattr('name', bind_to_model=False)
def eval_name(self, row):
    return row.users.first_name * row.users.last_name
```

In weppy 1.0 we removed this option since the real use-case scenario for this option was too limited. Moreover, this change allowed several optimizations on the injection of these attributes over the rows, increasing the general performance of the select operations.

If you used anywhere in your code this option, please update it accordingly.

#### Preserving the attributes types for relations on joined selects

Prior to weppy 1.0 you had different type for the relation attributes on the records depending on the use of `join` or `including` options during selection:

```python
>>> type(User.first().posts)
<class 'weppy.dal.objects.HasManySet'>
>>> type(User.all().select(including='posts').first().posts)
<class 'pydal.objects.Rows'>
```

Although this was a *design decision* in weppy, to easily locate where the code was using joined references or not, we considered the best thing overall is to have consistency over the ORM types.

In weppy 1.0 the type is always kept the same, independently on how you selected records:

```python
>>> type(User.first().posts)
<class 'weppy.orm.objects.HasManySet'>
>>> type(User.all().select(including='posts').first().posts)
<class 'weppy.orm.objects.HasManySet'>
>>> type(User.first().posts())
<class 'weppy.orm.objects.Rows'>
>>> type(User.all().select(including='posts').first().posts())
<class 'weppy.orm.objects.Rows'>
```

Please update your code to the new design. The most common scenario is to change something like this:

```python
for user in User.all().select(including='posts'):
    print(user.name)
    for post in user.posts:
        print(post.name)
```

to add the parenthesis:

```python
for user in User.all().select(including='posts'):
    print(user.name)
    for post in user.posts():
        print(post.name)
```

#### Automatic casting of route variables

In weppy 1.0 the route variables of *int* and *date* types are automatically casted to the relevant objects.

While for the *int* variables this won't break your code, you should check wheter you expected a string object in routes for dates:

```python
@app.route('/dateroute/<date:d>')
def dateroute(d):
    d = datetime.strptime(d, "%Y-%m-%d")
    # code
```

This would produce errors in weppy 1.0 since the `d` argument is already a `Pendulum` object. Just be sure to remove the parsing from your code.

### New features

weppy 1.0 introduces some new features you may take advantage of:

- Application [modules](./app_and_modules#application-modules) now allow nesting and inheritance
- The float type is now available in [route variables](./routing#path)
- *int*, *float* and *date* route variable types are now automatically casted to the relevant objects
- [Multiple paths](./routing#multiple-paths) can be specified for a single route
- A `now` method is now available in weppy that returns `request.now` or `Pendulum.utcnow` values depending on the context
- Computed fields values are now accesible within insert and update callbacks
- A `headers` attribute is now available on the request object to easily access the headers sent by the client
- An `anchor` parameter is now available in the `url` method
- Signal [bindings](./extensions#building-extensions) is now available for extensions


Version 0.8
-----------

weppy 0.8 introduces some minor breaking changes you should be aware of, and some new features you might been interested into.

### Breaking changes

#### Default serialization and validation of datetime fields

In weppy 0.8 the default serialization and validation of `datetime` fields has been changed in order to be compliant to the RFC3339 standard. This is due to better embrace developers who uses weppy to write REST APIs, and more generally, to simplify the compatibility with the Javascript world and third party services.

Practically speaking, while in weppy 0.7 and below versions, the format of `datetime` objects in serialization and validation was like this:

```json
{
    "dt": "2016-10-31 15:37:30.997128"
}
```

in weppy 0.8 is changed to:

```json
{
    "dt": "2016-10-31T15:37:30.997128+00:00"
}
```

Note that this also affects the format in forms, so if you want to stick with the previous notation for validation, add a `format` option to your validation rules:

```python
class SomeModel(Model):
    dt = Field('datetime')
    
    validation = {
        'dt': {'is':
            {'datetime': {'format': '%Y-%m-%d %H:%M:%S'}}}
    }
```

#### Upgraded default postgres adapters

The pyDAL library contains three different adapters for postgres databases, and the default one appears to be quite old.

In order to enhance performance and reliability of weppy ORM above postgres setups, we changed the default adapter to be the newest one. The main breaking differences between the adapters are the postgres types used for fields:

| field type | weppy 0.7 | weppy 0.8 |
| --- | --- | --- |
| bool | CHAR(1) | BOOLEAN |
| list:string | TEXT | TEXT[] |

Since the migrator won't see the change, you have two ways to adapt your old code to weppy 0.8:

- run a custom migration where you manually migrate the affected columns to the new types and use the new adapter
- change the adapter in your database configuration from `postgres` to `postgres3` in order to use the old adapter

#### has_one relations in join and including selections

In weppy 0.7 and below versions, when you performed some select with a join of a `has_one` relation, it appeared to be a list:

```python
>>> rows = User.all().join('profile').select()
>>> rows[0].profile
[<Row {...}>]
```

In weppy 0.8 this is correctly added to the row attribute as a `Row` object instead of a list with a single `Row` object.

Please check your code for these conditions and update it accordingly.

### New features

With weppy 0.8 we introduced some new features:

- the forms now support and display readable-only fields
- the `'in'` validator now [supports](./validations#value-inclusion) a `'dbset'` notation to validate the presence of the record into a specific database set
- the migrator now supports `bigint` fields

Version 0.7
-----------

weppy 0.7 introduces some deprecations you should be aware of, and some new features you might been interested into.

### Deprecation of virtual decorators in models

In the previous versions, the decorators used to make computation on existing fields and to define virtual attributes and methods for the row were available as `computation`, `virtualfield` and `fieldmethod`. Since we think this naming was not the best option, in weppy 0.7 these decorators were renamed as follows:

| old name | new name |
| --- | --- |
| computation | compute |
| virtualfield | rowattr |
| fieldmethod | rowmethod |

We think the new nomenclature is more self-explainatory and will make the code of weppy applications more readable.

All these variables are deprecated in weppy 0.7, so you can still use them, but we really suggest to update your application code to the new naming since the old ones will be definitely removed in the next version.

### New features

weppy 0.7 introduces official support to database indexes, integrating them with your models and the migration engine, read more about them in the [appropriate chapter](./dal/models#indexes) of the documentation.

Also, with weppy 0.7 we introduced some other small new features:

- `has_one` and `has_many` helpers now support [scope](./dal/relations#scoped-relations) and [where](./dal/relations#where-condition-on-relations) options
- `has_one` and `has_many` helpers now can be [used as decorators](./dal/advanced#customize-has_one-and-has_many-sets) to create custom relations
- fields of type *password* now have a default validation
- the *shell* command now loads the entire application context instead of just the application object
- a *routes* command is now available to easily get the routing table of the entire application

Version 0.6
-----------

weppy 0.6 introduces some deprecations and changes you should be aware of, and some new features you might been interested into.

Next paragraphs describe all these relevant changes.

### Deprecation of expose

Since the first version of weppy, the decorator used to expose functions outside was, indeed, `expose`:

```python
@app.expose()
def foo():
    pass

@mymodule.expose()
def bar():
    pass
```

Since the majority of frameworks use, instead, the `route` word for the same purpose, and we wanted to make easier for developers to move from one framework to another, we also adopted this *naming*. With weppy 0.6 you should change all your `expose` calls with `route`:

```python
@app.route()
def foo():
    pass

@mymodule.route()
def bar():
    pass
```

All the usages remain the same of `expose`.   
Since it's deprecated, you can still use `expose` in weppy 0.6, but you have to remember this will be definitely removed in the next version.

### Drepecation of vars in request, forms and urls

In the previous versions, the parameters of the url's query string and the ones contained in the request body were stored in the `request.get_vars`, `request.post_vars` and `request.vars` attributes. Since this naming could be quite misleading for developers, in weppy 0.6 these attributes were renamed as follows:

| old name | new name |
| --- | --- |
| vars | params |
| get\_vars | query\_params |
| post\_vars | body\_params |

We think the new nomenclature is more self-explainatory and will make the code of weppy applications more readable.

Following the same rationale, we also changed the `Form.vars` and `Form.input_vars` in `Form.parameters` and `Form.input_parameters`.    
Also the named `vars` parameter of the `url()` method is changed to `params` to avoid confusion.

All these variables are deprecated in weppy 0.6, so you can still use them, but we really suggest to update your application code to the new naming since the old ones will be definitely removed in the next version.

### Breaking changes

weppy 0.6 introduces some minor breaking changes: here we list the upgrades you should perform on your application in order to have the same behavior with the new version of the framework.

#### Relations with has\_one

In weppy 0.5 the `has_one` helper produced nested rows on the results of select operations for these kind of relations: this behavior is changed in weppy 0.6 in order to prevent performance issues. In fact, in the new version of the framework, the attribute responsible of the relation on the selected rows is now a `Set`.

The immediate consequence is that you have to change the code of your application when you want to effectively access the referred row with a call of the attribute:

```python
# weppy 0.5
referred_row = row.hasonerelation
# weppy 0.6
referred_row = row.hasonerelation()
```

You can find more about this in the [appropriate chapter](./dal/relations#operations-with-relations) of the documentation.

#### Model virtual decorators

The `virtualfield` and `fieldmethods` decorators were changed in order to bind the current model when accessing the row. This change was performed in order to simplify the code in these methods, since in weppy 0.5 you had to write code like this:

```python
class Post(Model):
    title = Field()

    @fieldmethod('short_title')
    def build_short_title(self, row):
        # notice we have to access the field using the tablename
        return row.posts.title[:100]
```

In weppy 0.6 you can rewrite the decorated method just like this:

```python
@fieldmethod('short_title')
def build_short_title(self, row):
    return row.title[:100]
```

You can restore the old behavior using the `current_model_only` parameter:

```python
@fieldmethod('short_title', current_model_only=False)
```

More details are available under the [appropriate chapter](./dal/virtuals) of the documentation.

#### Methods of has\_many sets

In weppy 0.5 the sets produced by `has_many` relations had an `add` with different behaviors depending on the `via` options:

- without the `via` option, the `add` method was performing an insert of an object referred to the current row
- with the `via` option, the `add` method was performing an insert of a record on the join table, reffered to the other two tables

Since weppy 0.6 introduces the `create` method on these sets, now the behavior of the `add` method is always the same, since it always accepts a record of the related table and will just create the relation with it.

If you used the `add` method of the `has_many` sets without `via` option in your application, you should change these calls with the `create` one.

You can find more about this in the [appropriate chapter](./dal/relations#operations-with-relations) of the documentation.

### New features

weppy 0.6 introduces some big new features you may take advantage of:

- a [testing client](./testing) to better support application tests
- a brand new [migration engine](./dal/migrations) for the included ORM

Also, with weppy 0.6 we introduced a lot of small new features on the ORM:

- [scopes](./dal/scopes) on models to simplify filtering
- the [join method and including option of select](./dal/relations#operations-with-relations) to simplify join and left join operations with relations
- the support for [custom naming](./dal/relations#naming-and-advanced-relations) on `has_many` relations
- the [refers_to](./dal/relations#refers_to) relation helper
- the [self keyword support](./dal/relations#naming-and-advanced-relations) for self-references in models
- the [pagination option](./dal/operations#selecting-records) on the selects
- the `where`, `all`, `first`, `last` and `get` methods to the models
- the `create`, `add` and `remove` methods on the sets produced by many relations

Since we introduced a lot of changes on the ORM, we also completely rewritten the involved chapters of the documentation. You may check them out in order to have a deepen view of all the features of the weppy ORM.


Version 0.5
-----------

weppy 0.5 introduces python 3 support. Fortunately, there are no changes in the main code that require changes in your application code.

> **Note:**   
> Internally, weppy dropped an old library for utf8 utilities, needed for the translator. Since this part of weppy had been rewritten for python 3 support, the usage of that library (`Utf8` class) is no longer required. If you used it in your own code, please make the appropriate changes in order to drop it.


Version 0.4
-----------

weppy 0.4 introduces a lot of major changes that break backward compatibility on the `DAL`, `Auth`, validation and forms modules among all the prior versions. These changes are a consequence of the introduction of a real ORM inside weppy (while prior versions just had a layer of abstraction over the database).

Please also keep in mind that weppy 0.4 **dropped support of python 2.6.x**. Please upgrade your python interpreter to 2.7.

Next paragraphs describe the relevant changes for your application in order to upgrade the code from weppy 0.3.

### Field class without name parameter

The `Field` class previously required a `name` as first parameter. In weppy 0.4 the name is injected by weppy depending on the name of the variable you use for store the field instance.

As an immediate consequence, fields are now `Model` attributes, instead of elements of the `fields` attribute which is no more available. Your model should be upgraded from the old notation:

```python
class Thing(Model):
    fields = [
        Field('name'),
        Field('value', 'integer')
    ]
```

to the new (and more convenient):

```python
class Thing(Model):
    name = Field()
    value = Field('integer')
```

You should also update all your `Form` instances, since you should pass a `dict` of fields instead of a `list` as first parameter, so from:

```python
form = Form([Field('name'), Field('value', 'integer')])
```

to:

```python
form = Form({'name': Field(), 'value': Field('int')})
```

### Renamed attributes in Model class
We changed the nomenclature of the `Model` class attributes to a *proper* one. Here is the complete list of old names vs the new ones:

| old name | new name |
| --- | --- |
| validators | validation |
| defaults | default_values |
| updates | update_values |
| representation | repr_values |
| visibility | form_rw |
| labels | form_labels |
| comments | form_info |
| widgets | form_widgets |

Please, update your models to the new structure.   
Also, note that the previously available attribute `Model.entity` is now the more appropriate `Model.table`.

### New validation system

weppy 0.4 introduces a totally refactored validation mechanism, and a new syntax for validation. In particular, the suggested syntax now uses dictionaries instead of lists of validator classes for validation.

Since this change removed *quite a lot* of previously available validators, we suggest you to convert your validation to the new system, which is documented in the [appropriate chapter](./validations).

If you still want to use the old notation, here is the list of changes in validators classes:

| validator | change |
| --- | --- |
| isIntInRange | removed |
| isFloatInRange | removed |
| isDecimalInRange | removed |
| isDateInRange | removed |
| isDatetimeInRange | removed |
| isEmailList | removed |
| isListOf | renamed into `isList` |
| isStrong | deprecated (available under `weppy.validators._old`) |
| inDb | deprecated (available under `weppy.validators._old`) |
| notInDb | deprecated (available under `weppy.validators._old`) |
| FilenameMatches | deprecated (available under `weppy.validators._old`) |
| anyOf | renamed to `Any` |
| Slug | renamed to `Urlify` |

also, we added new validators that replace the removed ones:

| validator | in place of |
| --- | --- |
| inRange | all the old *range* validators |
| inDB | inDb |
| notInDB | notInDb |

### Changes in Auth tables

Since weppy 0.4 introduces a new naming convention for models and tables, the old authorization tables were rewritten.

The first consequence is that new `Auth` tables have changed names:

| old name | new name |
| --- | --- |
| auth\_user | auth\_users |
| auth\_group | auth\_groups |
| auth\_membership | auth\_memberships |
| auth\_permission | auth\_permissions |
| auth\_event | auth\_events |

Moreover, we also changed the name of the columns involved in relations, in particular:

- `auth_memberships` have changed `user_id` and `group_id` to `user` and `authgroup`
- `auth_permissions` have changed `group_id` to `authgroup`
- `auth_events` have changed `user_id` to `user`

We suggest you to **manually do these changes** executing the proper sql commands with your database.

If you're not sure on what to do, we also provide a migration script, which tries to migrate the data. Please, **do a full backup of your database before running the script**. You can use it as follows:

- Download the script [weppy_04_upgrade](https://raw.github.com/gi0baro/weppy/master/scripts/weppy_04_upgrade.py) and put it in the directory of your application
- Run the command `weppy --app yourappname shell` (with your application name) and in the console:

```python
>>> from yourappname import app, db
>>> from weppy_04_upgrade import before_upgrade
>>> before_upgrade(app, db)
done
```

- Rewrite your models to apply the correct changes mentioned above
- Run the command `weppy --app yourname shell` (with your application name) and in the console:

```python
>>> from yourappname import app, db, auth
>>> from weppy_04_upgrade import after_upgrade
>>> after_upgrade(app, db, auth)
done
```

Then your auth tables should be good. The script created a *03dump.json* into your application folder that you can safely delete among with the script itself.

### New features

weppy 0.4 also introduces some new features you may want to take advantage of:

- `Field` class now support pythonic naming for old *integer* and *boolean* types: you can now write *int* and *bool*
- `Model` class now auto-generate the name for the table, if not specified (read more in the [DAL chapter](./dal#models))
- `belongs_to`, `has_one` and `has_many` apis are now available for relations in your models (read more in the [DAL chapter](./dal#relations))
- You can now disable default validation in `Field` and `Model` (read more in the [DAL chapter](./dal#validation))
- The `abort` helper now also accept a `body` parameter which allows you to customize the body of the returned HTTP error

Version 0.3
-----------

weppy 0.3 introduces a caching system for the templates. This change add a new configuration value under `app.config.templates_auto_reload` which is default set to `False`.   
This means that, under default behavior, in production weppy won't re-process the template files when modified, unless you reload the wsgi process. If you want to have the old behavior, so that weppy re-process the template file when it's modified, simply set the `templates_auto_reload` variable to `True`.   
Also remind that when your application is in *debug* mode – which means when it's loaded with the builtin wsgi server – the configuration setting is ignored and templates are auto reloaded by default.


Version 0.2
-----------

weppy 0.2 introduces some major changes in the code that break backward compatibility among the 0.1 *developer preview*. These changes were made to simplify the coding flow for developers and to have more consistent APIs.

If you're upgrading your application from weppy 0.1, next paragraphs describe the relevant changes for your application.

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
