Database objects and operations
===============================

Once you've defined your [models](./models) and the structure of your database entities, you need to make operations with them. In the next paragraphs we will inspect all the ways to create, modify and fetch your data from the database.

Creating records
----------------

The first operation you may need, is to add new data to your database.

Given a very essential model:

```python
class Dog(Model):
    name = Field()

db.define_models(Dog)
```

the simplest way to create a new record is to use its `create` method:

```python
>>> Dog.create(name="Pongo")
<Row {'errors': {}, 'id': 1}>
```

As you can see, the `create` method return a `Row` object, which contains the `id` of the created record and a dictionary named `errors`. This is because the `create` method will validate the input before trying to insert the new record.    
In fact, if we add a validation rule to the `Dog` model:

```python
class Dog(Model):
    name = Field()
    validation = {'name': {'presence': True}}
```

and we try to insert a dog without specifying a name:

```python
>>> Dog.create()
<Row {'errors': {'name': 'Cannot be empty'}, 'id': None}>
```

we have the `name` field in the errors and the `id` set as `None`, meaning that no record has been created at all.

weppy has also a more *low level* method to create records, that will skip the validation and insert the record directly into the database:

```python
>>> db.Dog.insert(name="Peggy")
2
```

As you can see, the `insert` method of the table defined by the model will return directly the `id` of the inserted record, since no validation was performed.

> **Note:**    
> Remember that if you're not in the request flow with the `DAL` handler, you have to commit your changes to effectively have them written into the database.

### Accessing the created record

As you've seen from the above methods, when you create a new record, weppy returns just the integer corresponding to the `id` of the database row. If you look deeply, you will find that actually the return value is not just an integer:

```python
>>> rv = Dog.create("Penny")
>>> type(rv.id)
<class 'pydal.helpers.classes.Reference'>
```

In fact, you can access the attributes of the record you've just created:

```python
>>> rv.id.name
'Penny'
>>> rv.id.as_dict()
{'id': 3, 'name': 'Penny'}
```

We will see more about the `as_dict` method in the next paragraphs.

Making queries
--------------

As soon as you have rows in your tables, you need to query them to fetch the data you want. weppy provides a very efficient way to write queries using python language, since you will use your model fields and their methods.

But, before we proceed learning the syntax to make queries, we have to understand the main principle behind weppy querying: the sets. Every time you work with the database to filter data, you're actually using a `Set` of rows corresponding to your query. The `Set` class is fundamental in weppy and allows you to make all the operations we will see in the next paragraphs on the records corresponding to your query.

So, how you make queries on your database? Let's say, for example, that you have a table containing events, defined by the model:

```python
class Event(Model):
    name = Field()
    location = Field()
    participants = Field('int')
    happens_at = Field('datetime')
```

and you want to query all the events for a certain location. You can use your `DAL` instance and its `where` method for that:

```python
>>> db.where(Event.location == "New York")
<Set (events.location = 'New York')>
```

or the more compact

```python
>>> db(Event.location == "New York")
<Set (events.location = 'New York')>
```

that produce the same result.    
As you can see, you can build queries using your model fields and the available operators:

| operator | description |
| --- | --- |
| `==` | value is equal to |
| `!=` | value differs from |
| `<` | value is lower than |
| `>` | value is greater than |
| `<=` | value is lower than or equal to |
| `>=` | value is greater than or equal to |

Returning back to our `Event` model, we can, for example, get all the events that are not in New York:

```python
db(Event.location != "New York")
```

or all the events with 200 or more participants:

```python
db(Event.participants >= 200)
```

> – Ok dude, what if I want to combine multiple *where* conditions?    
> – *just use the operators for the **and**, **or** and **not** conditions*

weppy provides the `&`, `|` and `~` operators for the *and*, *or* and *not* conditions, in order to combine multiple conditions on the same query.

For example, you may want all the events in New York that have less than 200 participants:

```python
>>> db((Event.location == "New York") & (Event.participants < 200))
<Set ((events.location = 'New York') AND (events.participants < 200))>
```

or the events happening on a specific day:

```python
db(
    (Event.happens_at >= datetime(1955, 10, 5)) & 
    (Event.happens_at < datetime(1955, 10, 6))
)
```

or the future events that won't be in New York or in Chicago:

```python
db(
    ~(
        (Event.location == "New York") |
        (Event.location == "Chicago")
    ) & (Event.happens_at >= request.now)
)
```

### Model where method

In all the examples we've seen above, we applied multiple where conditions on the same table. weppy offers also a more compact way to write these queries using directly the `Model.where` method and a `lambda` notation:

```python
Event.where(lambda e: 
    ~(
        (e.location == "New York") | (e.location == "Chicago")
    ) & (e.happens_at >= request.now)
)
```

The resulting `Set` will obviously be the same.

### Query using tables

As we seen in the [models](./models) section, adding a model to your `DAL` instance will add a `Table` object accessible both with the model name and the table name.

Since the tables shares the fields with models, you can use them for querying too. In fact you can write the same query in all these ways:

```python
Event.where(lambda e: e.location == "New York")
db(Event.location == "New York")
db(db.Event.location == "New York")
db(db.events.location == "New York")
```

and all of them will produce the same result. Just use the one you prefer or result more convenient for your code.

### Additional query operators

weppy also provides additional query operators that might be useful when you need particular conditions or for specific field types. Let's see them in detail.

#### belongs for the IN condition

When you need to perform sql *IN* conditions, you can use the `belongs` method:

```python
locations = ["New York", "Chicago"]
db(~Event.location.belongs(locations))
```

In this example we're asking all the events not happening in New York or Chicago.

#### String and text operators

An operator you may be familiar with is the `like` one, that produce a *LIKE* operation on the database. It works pretty similar to writing a raw sql query with a *LIKE* condition:

```python
db(Event.name.like("party%"))
```

where the *%* character is a wild-card meaning *any sequence of characters*, so the query will find any event starting with "party".

But weppy provides also some shortcuts for the `like` operator with wild-card:

```python
db(Event.name.startswith("party"))
db(Event.name.endswith("party"))
db(Event.name.contains("party"))
```

that will be the same of writing

```python
db(Event.name.like("party%"))
db(Event.name.like("%party"))
db(Event.name.like("%party%"))
```

Note that, usually the `like` operator will be case-sensitive on most of the DBMS, so if you want to make case-insensitive queries, you should specify the option on `like` and the other helpers:

```python
db(Event.name.like("party%", case_sensitive=False))
```

You can also use the `upper` and `lower` helpers:

```python
db(Event.name.upper().startswith("PARTY"))
```

weppy provides also a `regexp` method on fields that works in the same way of the `like` one but allows regular expressions syntax for the look-up expression. Just remember that only some DBMS support it (PostgreSQL, MySQL, Oracle and SQLite).

#### Date and time operators

weppy provides some additional operators for date, time and datetime fields, in particular:

* *date* and *datetime* fields have the `day`, `month` and `year` methods
* *time* and *datetime* fields have the `hour`, `minutes` and `seconds` methods

So, for example, you can query the events of a specific year quite easily:

```python
db(Event.happens_at.year() == 1985)
```

Selecting records
-----------------

*section in development*


Updating records
----------------

*section in development*
