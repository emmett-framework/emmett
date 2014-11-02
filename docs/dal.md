The Database Abstraction Layer
==============================

> – Ok, what if I need to use a database in my application?   
> – *you can use the included DAL*

weppy integrates the Database Abstraction Layer (formerly *DAL*) of *web2py*, which gives you the ability to use a database in your application, writing the same code and using the same syntax independently on which of the available adapters you want to use for deploy your app (you just need to install one of the supported drivers):

| Supperted DBMS | python driver(s) |
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
| IMAP | imaplib |

But how do you use it? Let's see it with an example:

```python
from weppy import App, DAL

app = App(__name__)
app.config.db.uri = "sqlite://storage.sqlite"

db = DAL(app)
db.define_table('post',
   Field('author'),
   Field('title'),
   Field('body', 'text'))

app.common_handlers = [db.handler]

@app.expose('/posts/<str:author>')
def post_by(author):
    posts = db(db.post.author == author).select()
    return dict(posts=posts)
```
The above code is quite simple: the `post_by()` function list posts from a specific author.
Let's reconstruct what we done in those simple lines:

* we added an *sqlite* database to our application, stored on file *storage.sqlite*
* we defined the table *post* and it's properties
* we did a select on the table querying the *author* column of *post* table

As you noticed, the fields defined for the table are available for queries as attributes, and calling *db* with a query as argument provides you a set on which you can do operations like the `select()`.

Since *DAL* is well documented in the *web2py* [reference manual](http://www.web2py.com/books/default/chapter/29/06/the-database-abstraction-layer), we wouldn't re-propose the complete documentation here. The only difference you have to remember looking at the *web2py* documentation is that the `DAL` class in weppy needs your `app` object as first parameter to work, and you store the configuration for dal in your `app.config`.

What we propose here it's an *additional layer* to use the *DAL*: the models one.

The models layer
----------------
weppy provides a *models* structuring layer upon the web2py's DAL; we encourage the use of models since they make easy to organize all the database entities for the applications. Also, models provides an easier syntax to use many DAL's features, like fields computations.

So, how a weppy model look like? Using the upper example for the posts table in a blog, and adding some features, an example model would be like this:

```python
from markdown2 import markdown
from weppy.dal.models import Model, computation
from weppy.validators import IS_NOT_EMPTY

class Post(Model):
    tablename = "post"

    fields = [
        Field("author"),
        Field("title"),
        Field("body"),
        Field("slug")
    ]

    representation = {
        "body": lambda row, value: markdown(value)
    }

    validators = {
        "title": IS_NOT_EMPTY(),
        "body": IS_NOT_EMPTY()
    }

    @computation('slug')
    def make_slug(self, row):
        # custom code to create the slug

```

As you can see, we added some validators, a representation rule to parse the markdown text of the post and produce html in the templates and a `computation` on the `slug` field. To use this model in your application you need to use the `ModelsDAL` class of weppy and its `define_datamodels()` method:

```python
from weppy import App, ModelsDAL
from mymodel import Post

app = App(__name__)
app.config.db.uri = "sqlite://storage.sqlite"

db = ModelsDAL(app)
db.define_datamodels([Post])

app.common_handlers = [db.handler]

@app.expose('/posts/<str:author>')
def post_by(author):
    posts = db(db.Post.author == author).select()
    return dict(posts=posts)
```

Now, let's see the complete list of attributes and helpers you can use with models.

### Model attributes

As you have seen in the example, when you define your model class, the first step you should do is to define the `tablename` and the `fields` attributes, which assign the name for the table in your DBMS, and the properties of your entity.

```python
class MyModel(Model):
    tablename = 'mytable'
    
    fields = [
        Field('one'),
        Field('two')]
```

#### Fields
The `fields` attribute has to be a list of `Field` objects. These objects define your entity's properties, so in general you would write the name of the property, the type and some additional parameters:

```python
Field('started', 'datetime', default=lambda: request.now)
```

as you can see we defined a default value for the field. The complete list of parameters accepted by `Field` class are available in the `DAL` documentation.

> **Warning:**   
> When you define a default value, if it's evaluated on request, like the request timestamp in this example, you have to use a `lambda` function; otherwise the value will be always the same as it will be evaluated only on model definition.

#### Validators

`validators` attribute is a `dict` mapping the names of the fields and the validator imported from `weppy.validators` you want to apply. They will be used to validate the forms created from the models on the user input:

```python
validators = {
    'started': IS_DATETIME_IN_RANGE(
        datetime(2014, 10, 12), 
        datetime(2014, 10, 15))
}
```
you can also define your custom validators:

```python
class MyValidator(object):
    def __init__(self, param):
        # code
    def __call__(self, value):
        # process value
        # if value is ok
        return (value, None)
        # if value is not ok
        return (value, "my error")
```
In general a validator is a class returning the tuple `(value, error)` on call.

#### Visibility

Visibility helps you to hide some attributes to users when you create forms:

```python
visibility = {
    'started': (False, False)
}
```
where the first value of the tuple define if the field should be visible, and the second if the field should be writable by user. By default, all fields are defined with visibility `(True, True)`.

#### Labels

Labels are useful to produce good titles for your fields in forms:

```python
labels = {
    'started': T("Opening date:")
}
```
The labels will decorate the input fields in your forms.

#### Comments

As for the labels, comments are useful to produce hints or helping blocks for your fields in forms:

```python
comments = {
    'started': T("Insert the desired opening date for your event in YYYY-MM-DD format.")
}
```

#### Updates
As for the `default` value we've seen before, `updates` helps you to set the default value for the field on record updates:

```python
updates = {
    'started': lambda: request.now
}
```

#### Representation

Sometimes you need to give a better representation for the value of your entity:

```python
representation = {
    'started': lambda row, value: prettydate(value)
}
```
and you can render it using:

```python
db.MyModel.started.represent(record, record.started)
```

#### Widgets

Widgets are used to produce the relevant input part in the form produced from your model. Every `Field` object has a default widget depending on the type you defined, for example the *datetime* has an `<input>` html tag of type *text*. When you need to customize the look of your input parts in the form, you can use your defined widgets and pass them to the model with the appropriate attribute:

```python
widgets = {
    'started': my_custom_widget
}
```
where `my_custom_widget` usually look like this:

```python
def my_custom_widget(field, value):
    # some processing
    return myhtmlinput
```

### 'set' helpers

Sometimes you need to access your model attributes when defining other features, but, until now, we couldn't access the class or the instance itself. An example are the `IS_NOT_IN_DB` and `IS_IN_DB` validators that needs the database instance and the field as parameters. To use these validators you can use the `set_validators` method of the model:

```python
def set_validators(self):
    self.entity.fieldname.requires = [IS_NOT_IN_DB(self.db, self.entity.fieldname)]
```

To allow you properly and completely customize your models definition, this is the complete list of `set` methods weppy runs when parsing the model (in this order):

* set_table()
* set_validators()
* set_visibility()
* set_representation()
* set_widgets()
* set_labels()
* set_comments()
* set_updates()

> *Note:*   
> You can define validators in any other *set* function,  weppy provides you separated methods so you can better organize your code.

### Computations

Sometimes you need some field values to be *computed* using other fields. For example:

```python
from weppy.models import Model, computation

class Item(Model):
    tablename = "items"

    fields = [
        Field('price','double'),
        Field('quantity','integer'),
        Field('total', 'double')]
    
    @computation('total')
    def total(self, row):
        return row.price*row.quantity
``` 
The function that does computation has to accept the row as parameter, and the computed value will be evaluated on both insert and updates.

### Callbacks

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

### Virtual fields

An alternative option to *computed* fields are the virtual ones. Considering the same example for the computations we can instead write:

```python
from weppy.models import Model, virtualfield

class Item(Model):
    tablename = "items"

    fields = [
        Field('price','double'),
        Field('quantity','integer')]
    
    @virtualfield('total')
    def total(self, row):
        return row.price*row.quantity
``` 
The difference between *computation* is that the virtual fields are computed only when the record is selected, and they are not stored into the database. You can access the values as the common fields:

```python
items = db(db.Item.price >= 2).select()
for item in items:
    print item.total
```

### Field methods

Another option for computed fields is to use the `fieldmethod` decorator:

```python
from weppy.models import Model, fieldmethod

class Item(Model):
    tablename = "items"

    fields = [
        Field('price','double'),
        Field('quantity','integer')]
    
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
from weppy.models import Model, fieldmethod

class Item(Model):
    tablename = "items"

    fields = [
        Field('price','double'),
        Field('quantity','integer')]
    
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

### Model methods

You can also define methods that will be available on the Model class itself. For instance, every weppy model comes with some pre-defined methods, for example:

```python
MyModel.form()
```
will create the form for the entity defined in your model.

Other methods pre-defined in weppy are:

| method | description |
| --- | --- |
| validate | process the values passed (field=value) and return None if they passes the validation defined in the model or a dictionary of errors |
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
> Accessing `Model.method()` refers to the model itself, while `db.Model.attribute` refers to the table instance you created whit your model.
