Models
======

A model is the single, definitive source of information about your data. It contains the essential all the informations and behaviors of the data you’re storing. Practically speaking, a model maps a database table and define what should happen to the data it contains.

So, how an Emmett model looks like? Thinking of a post inside a blog, an example model would be like this:

```python
from emmett.orm import Field, Model

class Post(Model):
    author = Field()
    title = Field()
    body = Field.text()
    
    validation = {
        "title": {'presence': True},
        "body": {'presence': True}
    }
```

As you can see, we defined three fields for our model, two of type string (is the default type in Emmett) and one of type text, which will map the corresponding columns in the table, and added some validation rules for them, so that we avoid to store posts missing titles or bodies.

As you will see in the next paragraphs, Emmett models have some reserved attributes, like `validation` which define some options for the fields inside your models. All the options listed in the next sections are available also as parameters of the `Field` class, and you can choose how to organize your code depending on your needs.

In order to use the model just defined in your application you must register it using the `define_models()` method of the `Database` class of Emmett, as we seen in the [first example](./):

```python
from emmett.orm import Database
db = Database(app)
db.define_models(Post)
```

This will create a `Table` object on your `Database` instance accessible both with model name and table name:

```python
db.Post
db.posts
```

> **Note:**   
> Accessing `Model` refers to the model itself, while `db.Model` refers to the table instance you created with your model. While these two classes shares the fields of your models, so accessing `Model.fieldname` and `db.Model.fieldname` or `db.tablename.fieldname` will produce the same result, they have different properties and methods, and you should remember this difference.


### Tables naming
Under default behavior, Emmett will create the table using the name of the class and making it plural, so that the class `Post` will create the table *posts*, `Comment` will create table *comments* and so on.   
If you want to customize the name of the table, you can use the `tablename` attribute inside your model:

```python
class Post(Model):
    tablename = "myposts"
```

just ensure the name is valid for the DBMS you're using.

> **Warning:**    
> Emmett doesn't have a *real* pluralization system to evaluate names, so in case the name you've chosen for your model doesn't have a *regular* plural in english, you should write down the correct plural with the `tablename` attribute. Just as an example, a model named `Mouse` will be translated in the *horrible* `"mouses"` tablename, so you should assign:   
> `tablename = "mice"`

Fields
------
`Field` objects define your entity's properties, and will map the appropriate columns inside your tables, so in general you would write the name of the property and its type:

```python
started = Field.datetime()
```

Available type methods for Field definition are:

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
| list:string | `list` of `str` |
| list:int | `list` of `int` |
| json | `json` |

If you don't specify a type for the `Field` class, and create an instance directly, it will be set as *string* as default value.

Using the right field type ensure the right columns types inside your tables, and allows you to benefit from the default validation implemented by Emmett.

Validation
----------
To implement a validation mechanism for your fields, you can use the `validation` parameter of the `Field` class, or the mapping `dict` with the name of the fields at the `validation` attribute inside your Model. Both method will produce the same result, just pick the one you prefer:

```python
title = Field(validation={'presence': True})
body = Field.text(validation={'presence': True})
```

```python
validation = {
    'title': {'presence': True},
    'body': {'presence': True}
}
```

The validation rules you define will be used to validate the forms created from the models on the user input and inserts.   
While you can find the complete list of available validators in the [appropriate chapter](../validation) of the documentation, here we list the default validation implemented by Emmett on fields:

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
| int_list | `{'is': 'list:int'}`| no |
| json | `{'is': 'json'}` | no |
| password | `{'len': {'gte': 6}, 'crypt': True}}` | no |

> **Tip:**    
> When you want to allow your fields been empty, you can use the *allow* validator:   
> `{'allow': 'blank'}` or `{'allow': 'empty'}`

### Disable default validation
Sometimes you may want to disable the default validation implemented by Emmett. Depending on your needs, you have two different ways.   
When you need to disable the default validation on a single `Field`, you can use the `auto_validation` parameter:

```python
a = Field(auto_validation=False)
```

Otherwise, if you want to disable the default validation on every field of your `Model`, the `auto_validation` attribute is handy:

```python
class MyModel(Model):
    auto_validation = False
```

Default values
--------------
Emmett models have a `default_values` attribute that helps you to set the default value for the field on record insertions:

```python
default_values = {
    'started': lambda: request.now
}
```

Which is the same of the `default` parameter of `Field` class:

```python
started = Field.datetime(default=lambda: request.now)
```

The values defined in this way will be used on the insertion of new records in the database if no other value is given during the operation.

Update values
-------------
As for the `default_values` attribute we've seen before, `update_values` helps you to set the default value for the field on record updates:

```python
update_values = {
    'started': lambda: request.now
}
```

Or you can use the `update` parameter of `Field` class:

```python
started = Field.datetime(update=lambda: request.now)
```

The values defined in this way will be used on the update of existing records in the database if no other value is given during the operation.

Fields accessibility
--------------------

*Changed in version 1.0*

The `fields_rw` attribute of `Model` class helps you defining the access rules to the fields. It might be useful, for example, to hide some attributes to users when you create forms:

```python
fields_rw = {
    'started': False,
    'open': (True, False)
}
```

Any item of the dictionary can be a `tuple`, where the first value defines if the field should be readable by the user and the second value defines if the field should be writable, or `bool` that will set both values to the one given. By default, all fields are defined with *rw* at `True`.

You may prefer to explicit passing read-writes values to the fields, using `rw` parameter:

```python
started = Field.datetime(rw=False)
```

Indexes
-------

*New in version 0.7*

Emmett provides an `indexes` attribute on models which helps you define indexes on your tables:

```python
indexes = {
    'field1': True,
    ('field1', 'field2'): True,
    'custom_index_name': {'fields': ['fields3', 'fields4']}
}
```

> **Note:** indexes are available only when using Database with [migrations](./migrations) enabled.

As you can see, Emmett supports different formats for indexes, since we defined:

- an index on the field *field1*
- a combined index on fields *field1* and *field2*
- a combined index on fields *fields3* and *fields4* with a custom name

Practically speaking, the rules Emmett apply on the indexes definition are:

- when the value is a `bool`, the key must be a field of your model or a tuple of fields of your model
- when the value is a `dict`, the key will be the name of the index

> **Note:** every index defined in Emmett models will have its name starting with `modelname_widx__name`.

When using the `dict` notation, you can also specify the `unique` option as a boolean, which is `False` on default behavior.

Emmett supports some advanced options on defining indexes, see the [advanced chapter](./advanced#advanced-indexes) of the documentation for further informations.

Values representation
---------------------
Sometimes you need to give a better representation for the value of your entity, for example rendering dates or shows only a portion of a text field. In these cases, the `repr_values` attribute of your models will help:

```python
repr_values = {
    'started': lambda row, value: prettydate(value)
}
```

Once defined this, you can render the value using:

```python
MyModel.started.represent(record, record.started)
```

And if you may prefer to explicit passing representation rules to the single fields instead of writing down in the model, you can use the `representation` parameter:

```python
started = Field.datetime(representation=lambda row, value: prettydate(value))
```

Forms helpers
-------------
The `Model` attributes listed in this section are intended to be used for forms generation.

### Form labels
Labels are useful to produce good titles for your fields in forms:

```python
form_labels = {
    'started': T("Opening date:")
}
```
Labels will decorate the input fields in your forms. In this example we used the [Emmett translator](./languages) object to automatically translate the string in the correct language.

You can also use the `label` parameter of `Field` class:

```python
started = Field.datetime(label=T("Opening date:"))
```

### Form info
As for the labels, `form_info` attribute is useful to produce hints or helping blocks for your fields in forms:

```python
form_info = {
    'started': T("Insert the desired opening date for your event in YYYY-MM-DD format.")
}
```

You can also use the `info` parameter of `Field` class:

```python
started = Field.datetime(info=T("some description here"))
```

### Widgets
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

And you can also use the `widget` parameter of `Field` class:

```python
started = Field.datetime(widget=my_custom_widget)
```

The setup helper
----------------
Sometimes you need to access your model attributes when defining other features, but, until now, we couldn't access the class or the instance itself. To avoid this problem, you can use the `setup` method of the model:

```python
def setup(self):
    # you can access the database, the table and its fields
    db = self.db
    table = self.table
    field = self.table.fieldname
```


Model methods
-------------
You can also define methods that will be available on the Model class itself. For instance, every Emmett model comes with some pre-defined methods, for example:

```python
MyModel.form()
```
will create the form for the entity defined in your model.

Other methods pre-defined in Emmett are:

| method | description |
| --- | --- |
| validate | validates the values passed as parameters (field=value) and return an `sdict` of errors (that would be empty if the validation passed) |
| create | insert a new record with the values passed (field=value) if they pass the validation |

But how can you define additional methods?   
Let's say, for example that you want a shortcut in your `Notification` model to set all the records to be *read* for a specific user, without writing down the query manually every time:

```python
class Notification(Model):
    user = Field()
    message = Field.text()
    read = Field.bool()
    
    @classmethod
    def read_all(cls, user):
        return cls.where(
            lambda n: n.user == user
        ).update(read=True)
```
now you can easily set user's notification as read:

```python
>>> Notification.read_all(my_user)
3
```

As you observed, you can just use the standard `classmethod` decorator of the python language.

> **Note:**   
> Accessing `Model.method()` refers to the model itself, while `db.Model.attribute` refers to the table instance you created with your model.
