The Database Abstraction Layer
==============================

> – Ok, what if I need to use a database in my application?   
> – *you can use the included DAL*

weppy integrates [pyDAL](https://github.com/web2py/pydal) as the preferred database abstraction layer, which gives you the ability to use a database in your application, writing the same code and using the same syntax independently on which of the available adapters you want to use for deploy your app (you just need to install one of the supported drivers):

| Supported DBMS | python driver(s) |
| --- | --- |
| SQLite | sqlite3, pysqlite2, zxjdbc |
| PostgreSQL | psycopg2, pg8000, zxjdbc |
| MySQL | pymysql, mysqldb |
| Oracle | cxoracle |
| MSSQL | pyodbc |
| FireBird | kinterbasdb, fdb, pyodbc |
| DB2 | pyodbc |
| Informix | informixdb |
| Ingres | ingresdbi |
| Cubrid | cubridb |
| Sybase | Sybase |
| Teradata | pyodbc |
| SAPDB | sapdb |
| MongoDB | pymongo |

But how do you use it? Let's see it with an example:

```python
from weppy import App
from weppy.dal import DAL, Model, Field

app = App(__name__)
app.config.db.uri = "sqlite://storage.sqlite"

class Post(Model):
    author = Field()
    title = Field()
    body = Field('text')

db = DAL(app)
db.define_models(Post)

app.common_handlers = [db.handler]

@app.expose('/posts/<str:author>')
def post_by(author):
    posts = db(Post.author == author).select()
    return dict(posts=posts)
```
The above code is quite simple: the `post_by()` function list posts from a specific author.
Let's reconstruct what we done in those simple lines:

* we added an *sqlite* database to our application, stored on file *storage.sqlite*
* we defined the *Post* model and its properties, which will create a *posts* table
* we registered the database handler to our application so that it will be available during requests
* we did a select on the *posts* table querying the *author* column

As you noticed, the fields defined for the table are available for queries as attributes, and calling *db* with a query as argument provides you a set on which you can do operations like the `select()`.

Since *pyDAL* is well documented in the *web2py* [reference manual](http://www.web2py.com/books/default/chapter/29/06/the-database-abstraction-layer), we wouldn't re-propose the complete documentation here, but will focus on the particular implementations you will find in weppy.   
The main differences between using *web2py* or *pyDAL* directly, in comparison with weppy, differences that you should remember when looking at their documentations, are:

- `DAL` class needs your `app` object as first parameter to work, and you store the configuration for the database in your `app.config` attribute
- `Field` class in weppy doesn't accept the name for the field as the first parameter. This is because when you define your fields the name is captured by the attribute itself.

Let's go further and inspect the models layer provided by weppy.

Models
------
So, how a weppy model looks like? Using the upper example for the post inside a blog, and adding some features, an example model would be like this:

```python
from markdown2 import markdown
from weppy.dal import Field, Model, computation

class Post(Model):
    author = Field()
    title = Field()
    body = Field('text')
    summary = Field('text')
    
    repr_values = {
        "body": lambda row, value: markdown(value)
    }

    validation = {
        "title": {'presence': True},
        "body": {'presence': True}
    }

    @computation('summary')
    def make_summary(self, row):
        # custom code to create the summary from the text

```

As you can see, we added some validation rules, a representation rule to parse the markdown text of the post and produce html in the templates and a `computation` on the `summary` field. To use this model in your application you can use the `define_models()` method of the `DAL` class of weppy, as we seen in the example above:

```python
db.define_models(Post)
```

### Tables naming
Under default behavior, weppy will create the table using the name of the class and making it plural, so that the class `Post` will create the table *posts*, `Comment` will create table *comments* and so on.   
If you want to customize the name of the table, you can use the `tablename` attribute inside your model:

```python
Class Post(Model):
    tablename = "myposts"
```

just ensure the name is valid for the DBMS you're using.

> **Warning:**    
> weppy doesn't have a *real* pluralization system to evaluate names, so in case the name you've chosen for your model doesn't have a *regular* plural in english, you should write down the correct plural with the `tablename` attribute. Just as an example, a model named `Mouse` will be translated in the *horrible* `"mouses"` tablename, so you should assign:   
> `tablename = "mice"`

Fields
------
`Field` objects define your entity's properties, and will create the appropriate columns inside your tables, so in general you would write the name of the property and its type:

```python
started = Field('datetime')
```

Available types for Field definition are:

| Field type | mapped to python object |
| --- | --- |
| string | `str` |
| text | `str` |
| blob | `str` |
| bool | `bool` |
| int | `int` |
| float | `float` |
| decimal(n,m) | `decimal.Decimal` |
| date | `datetime.date` |
| time | `datetime.time` |
| datetime | `datetime.datetime` |
| password | `str` |
| upload | `str` |
| reference *tablename* | `int` or `pydal.objects.Row` (depends on context) |
| list:string | `list` of `str` |
| list:integer | `list` of `int` |
| list:reference *tablename* | `list` of `int` or `pydal.objects.Rows` |
| json | `json` |

Using the right field type ensure the right columns types inside your tables, and allows you to benefit from the default validation implemented by weppy.

Validators
----------

To implement a validation mechanism for your fields, you can use the `validation` parameter of the `Field` class, or the mapping `dict` with the name of the fields at the `validation` attribute inside your Model. Both method will produce the same result, just pick the one you prefer:

```python
title = Field(validation={'presence': True})
```

```python
validation = {
    'title': {'presence': True}
}
```

The validation rules you define will be used to validate the forms created from the models on the user input and inserts.   
While you can find the complete list of available validators in the [appropriate chapter](./validation) of the documentation, here we list the default validation implemented by weppy on fields:

| Field type | default validation | allow blank value |
| --- | --- | --- |
| string | `{'len': {'lt': 255}}` | yes |
| text | `{'len': {'lt': 65536}}` | yes |
| bool | `{'in': (False, True)}` | no |
| int | `{'is': 'int'}` | no |
| float | `{'is': 'float'}` | no |
| decimal | `{'is': 'decimal'}` | no |
| date | `{'is': 'date'}` | no |
| time | `{'is': 'time'}` | no |
| datetime | `{'is': 'datetime'}` | no |
| reference *tablename* | `{'presence': True}` | no |
| list:reference *tablename* | `None` | no |
| json | `{'is': 'json'}` | no |

> **Tip:**    
> When you want to allow your fields been empty, you can use the *allow* validator:   
> `{'allow': 'blank'}` or `{'allow': 'empty'}`

### Disable default validation
Sometimes you may want to disable the default validation implemented by weppy. Depending on your needs, you have two different ways.   
When you need to disable the default validation on a single `Field`, you can use the `auto_validation` parameter:

```python
a = Field(auto_validation=False)
```

Otherwise, if you want to disable the default validation on every field of your `Model`, the `auto_validation` attribute is handy:

```python
class MyModel(Model):
    auto_validation = False
```

Relations
---------
As you've seen from the `Field` types, weppy provides the `reference` field type to create relationships between tables. So how you should use them?   
Let's say we want to create some membership system of users in groups. We probably end up writing something like this:

```python
class User(Model):
    name = Field()
    age = Field('int')

class Group(Model):
    name = Field()

class Membership(Model):
    user = Field('reference users', unique=True)
    group = Field('reference groups')
```

Now we have `1:N` relationship between `Group` and `Membership` and `1:1` relationship between `User` and `Membership`. To select from the database the rows that match some of the relationships, we should write the queries using the referenced attributes and the id's of the record involved.   
Or we can use another way.

### The easy way: belongs\_to, has\_one, has\_many

The simple and *magic* way is the usage of these three helpers. So how do they works? Let's see it with the same example, rewritten:

```python
class User(Model):
    has_one('membership')
    name = Field()
    age = Field('int')

class Group(Model):
    has_many('memberships')
    name = Field()

class Membership(Model):
    belongs_to('user', 'group')
    validation = {
        'user': {'unique': True}
    }
```

> – Dude, wait.. This is not more compact. I see more lines to do the same thing.

Right, we wrote more lines to do the same thing as above, but we have some advantages over the first method. In particular if we want to get all the memberships of a certain group, with the first notation we should write:

```python
group = db.Group(name="admins")
memberships = db(db.Membership.group == group.id).select()
for membership in membership:
    user = membership.user
```

while the `has_many` helper implements the `memberships` method on the `Group` model:

```python
group = db.Group(name="admins")
for membership in group.memberships():
    user = membership.user
```

In the same way, if you want to get the group of a certain user, with the first method you have to write:

```python
user = db.User(name="mario")
membership = db.Membership(user=user.id)
group = membership.group
```

while with the `has_one` helper:

```python
user = db.User(name="mario")
group = user.membership.group
```

So, if you use relationships quite often in your code, you will end with less lines of code.

> *Technical note:*   
> `has_one` and `has_many` don't create columns inside your tables. While `belongs_to` adds a `reference` Field inside your model, and you will have a column for the id of the referenced record, `has_one` will create a `Field.Virtual` object that will be computed on selects, and `has_many` will create a `Field.Method` object that will be computed on call.

Obviously, you can use `reference` fields and write down your own `Model` methods as we will se in the next paragraphs; so finally, you can choose whatever way fits good for your project.

Forms read-writes
-----------------

`form_rw` attribute of `Model` class helps you to hide some attributes to users when you create forms:

```python
form_rw = {
    'started': False,
    'open': (True, False)
}
```
Any item of the dictionary can be a `tuple`, where the first value define if the field should be readable by the user and the second value define if the field should be writable, or `bool` that will set both values to the one given. By default, all fields are defined with *rw* at `True`.

Form labels
-----------
Labels are useful to produce good titles for your fields in forms:

```python
form_labels = {
    'started': T("Opening date:")
}
```
Labels will decorate the input fields in your forms. In this example we used the [weppy translator](./languages) object to automatically translate the string in the correct language.

Form info
---------
As for the labels, `form_info` attribute is useful to produce hints or helping blocks for your fields in forms:

```python
form_info = {
    'started': T("Insert the desired opening date for your event in YYYY-MM-DD format.")
}
```

Default values
--------------
Helps you to set the default value for the field on record insertions:

```python
default_values = {
    'started': lambda: request.now
}
```

Update values
-------------
As for the `default_values` attribute we've seen before, `update_values` helps you to set the default value for the field on record updates:

```python
update_values = {
    'started': lambda: request.now
}
```

Representation
--------------

Sometimes you need to give a better representation for the value of your entity:

```python
repr_values = {
    'started': lambda row, value: prettydate(value)
}
```

and you can render it using:

```python
MyModel.started.represent(record, record.started)
```

Widgets
-------

Widgets are used to produce the relevant input part in the form produced from your model. Every `Field` object has a default widget depending on the type you defined, for example the *datetime* has an `<input>` html tag of type *text*. When you need to customize the look of your input blocks in the form, you can use your own widgets and pass them to the model with the appropriate attribute:

```python
form_widgets = {
    'started': my_custom_widget
}
```

where `my_custom_widget` usually look like this:

```python
def my_custom_widget(field, value):
    # some processing
    return myhtmlinput
```

The 'setup' helper
------------------

Sometimes you need to access your model attributes when defining other features, but, until now, we couldn't access the class or the instance itself. To avoid this problem, you can use the `setup` method of the model:

```python
def setup(self):
    # you can access the database, the table and its fields
    db = self.db
    table = self.table
    field = self.table.fieldname
```

Computations
------------

Sometimes you need some field values to be *computed* using other fields. For example:

```python
from weppy.dal import Model, Field, computation

class Item(Model):
    price = Field('float')
    quantity = Field('int')
    total = Field('float')
    
    @computation('total')
    def total(self, row):
        return row.price*row.quantity
``` 
The function that does computation has to accept the row as parameter, and the computed value will be evaluated on both insert and updates.

Callbacks
---------

When you need to perform certain computations on specific conditions, weppy helps you with the callbacks decorators, which will be invoked automatically. Here is the complete list of available decorators, with the parameters that will be passed to your decorated function:

| decorator | parameters |
| --- | --- |
| before_insert | fields |
| after_insert | fields, id |
| before_update | set, fields |
| after_update | set, fields |
| before_delete | set |
| after_delete | set |

where `fields` is a dictionary containing fields and values passed to insert or update operations, `id` is the id of the newly inserted record, and `set` is the object used for the update or delete operation.

An example of usage can be a thumbnail function:

```python
@before_update
def update_avatar_thumb(self, s, fields):
    # process the image in fields['image']
    fields['image'] = thumbnail
```

Virtual fields
--------------

An alternative option to *computed* fields are the virtual ones. Considering the same example for the computations we can instead write:

```python
from weppy.dal import Model, Field, virtualfield

class Item(Model):
    price = Field('float')
    quantity = Field('int')
    
    @virtualfield('total')
    def total(self, row):
        return row.price*row.quantity
``` 
The difference between *computation* is that virtual fields are computed only when the record is selected, and they are not stored into the database. You can access the values as the common fields:

```python
items = db(db.Item.price >= 2).select()
for item in items:
    print item.total
```

Field methods
-------------

Another option for computed fields is to use the `fieldmethod` decorator:

```python
from weppy.dal import Model, Field, fieldmethod

class Item(Model):
    price = Field('float')
    quantity = Field('int')
    
    @fieldmethod('total')
    def total(self, row):
        return row.price*row.quantity
```
Field methods are evaluated *on demand* which means you have to invoke them when you want to access the values:

```python
item = db(db.Item.price > 2).select().first()
print item.total()
```

Field methods can be useful also to create query shortcuts on other tables. Let's say we have defined another model called `Warehouse` for the quantity of items available in the warehouse, and we want to check the availability directly when we have the selected item:

```python
from weppy.dal import Model, fieldmethod

class Item(Model):
    price = Field('float')
    quantity = Field('int')
    
    @fieldmethod('total')
    def total(self, row):
        return row.price*row.quantity
    
    @fieldmethod('availability')
    def avail(self, row):
        w = self.db(self.db.Warehouse.item == row.id).select().first()
        return w.in_store
```

and we can access the value simply doing:

```python
item = db(db.Item.price > 2).select().first()
print item.availability()
```

Model methods
-------------

You can also define methods that will be available on the Model class itself. For instance, every weppy model comes with some pre-defined methods, for example:

```python
MyModel.form()
```
will create the form for the entity defined in your model.

Other methods pre-defined in weppy are:

| method | description |
| --- | --- |
| validate | process the values passed (field=value) and return None if they pass the validation defined in the model or a dictionary of errors |
| create | insert a new record with the values passed (field=value) if they pass the validation |

But how you can define your methods?   
Let's say, for example that you want a shortcut for querying record in your model `Series` with the same basic condition, like the case when you need to call in several parts of your code only records owned by the authenticated user. Assuming you have your user id stored in session, you can write down something like this in your model:

```python
@modelmethod
def find_owned(db, entity, query=None):
    _query = (entity.owner == session.user)
    if query:
        _query = _query & query
    return db(_query).select()
```
now you can do:

```python
my_series = Series.find_owned()
```
and you're done.

As you observed, `modelmethod` decorator requires that your method accepts `db` and `entity` as first parameters. In fact, these methods are available on the class, and you don't have the `self` access to the instance. But weppy automatically provides you a shortcut to the database and the table with these parameters.

> **Note:**   
> Accessing `Model.method()` refers to the model itself, while `db.Model.attribute` refers to the table instance you created with your model.
