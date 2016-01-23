Advanced usage
==============

This final part of the databases documentation will explain some advanced features and behaviors you might need to understand when you're designing more complex applications or you need advanced and particular flows for your data.

Model inheritance and subclassing
---------------------------------

The `Model` class can be subclassed and extended by design in many different ways. You can also define models without creating a table for them in the database and use them as meta classes for common fields, validations and other needs.

In fact, even if some properties regarding your model are bound dictionaries of the class itself, weppy will *hack* these attributes in order to make them inherit and extend the ones from the upper models.

For instance, if you have a lot of models where you want to store the creation and update timestamps, you can write down a simple model for that:

```python
class TimeStampModel(Model):
    created_at = Field('datetime')
    updated_at = Field('datetime')

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
    body = Field('text')
    status = Field()

    default_values = {
        'status': 'published'
    }

class Comment(TimeStampModel):
    text = Field('text')
```

Then if you pass just these models to your `DAL` instance:

```python
db.define_models(Post, Comment)
```

you will find the `created_at` and `updated_at` fields on these tables and the default and update values set for them.

As you can see, the `Post` model has its own `default_values` dictionary that defines the default value for the `status` field, but the resulting dictionary will contains also the values of the `TimeStampModel` dictionary. This behavior is injected by weppy and is intended to avoid you the pain of rewriting the whole dictionaries when extending models.

You can obviosly override a value from the super model, in fact if you write something like this in the `Post` model:

```python
default_values = {
    'updated_at': lambda: request.now+timedelta(minutes=5),
    'status': 'published'
}
```

it will change the default value defined from `TimeStampModel` for the `updated_at` value.

This is true for all the reserved properties related to the fields we seen in the [models](./models) part of the documentation, and all the other attributes of the `Model` class will follow the normal inheritance behavior in the python language.

Models in weppy also inherits all the properties decorated with the helper functions we seen in the previus chapters, and all the relations too.

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

You can also use multiple models as base classes for inheritance, and weppy will merge the relevant properties with the order of the base classes. For example if we define another base model:

```python
class Hidden(Model):
    is_hidden = Field('bool')

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
