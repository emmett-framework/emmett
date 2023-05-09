Advanced usage
==============

This final part of the databases documentation will explain some advanced features and behaviors you might need to understand when you're designing more complex applications or you need advanced and particular flows for your data.

Model inheritance and subclassing
---------------------------------

The `Model` class can be subclassed and extended by design in many different ways. You can also define models without creating a table for them in the database and use them as meta classes for common fields, validations and other needs.

In fact, even if some properties regarding your model are bound dictionaries of the class itself, Emmett will *hack* these attributes in order to make them inherit and extend the ones from the upper models.

For instance, if you have a lot of models where you want to store the creation and update timestamps, you can write down a simple model for that:

```python
class TimeStampModel(Model):
    created_at = Field.datetime()
    updated_at = Field.datetime()

    default_values = {
        'created_at': lambda: request.now,
        'updated_at': lambda: request.now
    }

    update_values = {
        'updated_at': lambda: request.now
    }
```

and then extend it with the other models:

```python
class Post(TimeStampModel):
    title = Field()
    body = Field.text()
    status = Field()

    default_values = {
        'status': 'published'
    }

class Comment(TimeStampModel):
    text = Field.text()
```

Then if you pass just these models to your `Database` instance:

```python
db.define_models(Post, Comment)
```

you will find the `created_at` and `updated_at` fields on these tables and the default and update values set for them.

As you can see, the `Post` model has its own `default_values` dictionary that defines the default value for the `status` field, but the resulting dictionary will contains also the values of the `TimeStampModel` dictionary. This behavior is injected by Emmett and is intended to avoid you the pain of rewriting the whole dictionaries when extending models.

You can obviosly override a value from the super model, in fact if you write something like this in the `Post` model:

```python
default_values = {
    'updated_at': lambda: request.now+timedelta(minutes=5),
    'status': 'published'
}
```

it will change the default value defined from `TimeStampModel` for the `updated_at` value.

This is true for all the reserved properties related to the fields we seen in the [models](./models) part of the documentation, and all the other attributes of the `Model` class will follow the normal inheritance behavior in the python language.

Models in Emmett also inherits all the properties decorated with the helper functions we seen in the previus chapters, and all the relations too.

In fact, if you defined scopes in `TimeStampModel`:

```python
@scope('created_between')
def filter_creation_period(self, start, end):
    return (self.created_at >= start) & (self.created_at < end)

@scope('updated_between')
def filter_update_period(self, start, end):
    return (self.updated_at >= start) & (self.updated_at < end)
```

you will be able to use them on the `Post` and `Comment` classes.

You can also use multiple models as base classes for inheritance, and Emmett will merge the relevant properties with the order of the base classes. For example if we define another base model:

```python
class Hidden(Model):
    is_hidden = Field.bool()

    default_values = {
        'is_hidden': True
    }

    @scope('not_hidden')
    def filter_not_hidden(self):
        return self.is_hidden == False

    @scope('only_hidden')
    def filter_only_hidden(self):
        return self.is_hidden == True
```

and update the inheritance for the `Post` class:

```python
class Post(TimeStampModel, Hidden):
    # ...
```

you will have the fields, default values and scopes from this model too.

> **Warning:** every time you using inheritance with model ensure every class is a subclass of the `Model` one.

> **Note:** when you need to override a decorated method of the super model, ensure to decorate it also in the subclassed one and to use the same method name of the super one.

Customize has\_one and has\_many sets
-------------------------------------

Sometimes you will need to customize the way Emmett generates relations sets for `has_one` and `has_many` relations.

For example, you may want to change the behavior of a relation depending on some conditions:

```python
from emmett import session

class User(Model):
    @has_many()
    def posts(self):
        if session.user.is_admin:
            return Post.where(lambda m: m.is_trashed == True)
        return Post.where(lambda m: m.is_trashed == False)
```

As you can see we used the `has_many` helper as a decorator over custom `posts` method we defined inside our `User` model. This way, the `posts` attribute of a user will have different sets depending on the condition we defined. 

Another common scenario would be a *polimorphic* relation, where you want to create multiple association to a single model. Let's say, for example, that you want to use a single table to store your photos, but you want to refer this table to several ones, for example to a table of cars and also one of trucks:

```python
class Photo(Model):
    url = Field()
    entity_type = Field()
    entity_id = Field.int()
    
class Car(Model):
    name = Field()
    price = Field.float()
    
    @has_many(field='entity_id')
    def photos(self):
        return Photo.where(lambda m: m.entity_type == 'Car')

class Truck(Model):
    name = Field()
    hp = Field.int()
    price = Field.float()
    
    @has_many(field='entity_id')
    def photos(self):
        return Photo.where(lambda m: m.entity_type == 'Truck')
```

As you can see, in this case we also specified the field Emmett should use as the foreign key for the relation – if not specified this field is the name of the downcase name of the model.

You can use *polimorphic* relations also for many-to-many relations, for example for a tagging system like this:

```python
class Tag(Model):
    name = Field()

class Tagging(Model):
    belongs_to('tag')
    tagged_type = Field()
    tagged_id = Field()

class Post(Model):
    @has_many(field='tagged_id')
    def taggings(self):
        return Tagging.where(lambda m: m.tagged_type == 'Post')
    
    has_many({'tags': {'via': 'taggings'}})
    
class Video(Model):
    @has_many(field='tagged_id')
    def taggings(self):
        return Tagging.where(lambda m: m.tagged_type == 'Video')
    
    has_many({'tags': {'via': 'taggings'}})
```

Note that inheritance we explained in the section above is great to avoid repeating code:

```python
class Taggable(Model):
    @has_many(field='tagged_id')
    def taggings(self):
        return Tagging.where(
            lambda m: m.tagged_type == self.tablename)
     
    has_many({'tags': {'via': 'taggings'}})
     
    @rowmethod('taglist')
    def get_taglist(self, row):
        return row.tags().column('name')

class Post(Taggable):
    title = Field()
     
class Video(Taggable):
    title = Field()
```

Advanced indexes
----------------

*New in version 0.7*

### Using expressions

> **Note:** support for expressions in indexes depends on the DBMS in use.

Emmett supports expressions on indexes definition, which can be useful when you want to *coalesce* values from your rows:

```python
class Post(Model):
    author = Field()
    is_private = Field.bool()
    title = Field()
    
    indexes = {
        'author_and_priv': {
            'fields': ['author'], 
            'expressions': lambda m: m.is_private.coalesce(False)
        }
    }
```

As you can see the `expressions` option accepts one or a list of lambda functions, that should accept just one parameter: the model. The returning value should by any Emmett valid sql expression on a field of the model itself.

### Conditional indexes

> **Note:** support for conditional indexes depends on the DBMS in use.

Emmett supports a `where` option on indexes definition, which can be used to define conditional indexes:

```python
class Post(Model):
    author = Field()
    is_private = Field.bool()
    
    indexes = {
        'author_and_priv': {
            'fields': ['author'], 
            'where': lambda m: (m.is_private == False)
        }
    }
```

The `where` option accepts a lambda function that should accept the model as first parameter and should return any valid query using the Emmett query language.

Custom primary keys
-------------------

*New in version 2.4*

### Customise primary key type

Under default behaviour, all models in Emmett have an integer `id` primary key. In case you need to change the type of this field, just define your own `id` field.

For example, we might want to have a model with UUID strings as primary key:

```python
from uuid import uuid4

class Ticket(Model):
    id = Field.string(default=lambda: uuid4().hex)
```

### Using custom primary keys

Sometimes you need to have models without an `id` field, as a specific field can be used as primary key. Other times, you need to have compound primary keys, where you have multiple fields producing your records identifier.

Under these circumstances, using the `primary_keys` attribute of the `Model` class will be enough:

```python
class Ticket(Model):
    primary_keys = ["code"]

    code = Field.string(default=lambda: uuid4().hex)


class MultiPK(Model):
    primary_keys = ["key1", "key2"]

    key1 = Field.int()
    key2 = Field.int()
```

> **Note:** Emmett [relations](./relations) system is fully-compatible with custom and multiple primary keys.
