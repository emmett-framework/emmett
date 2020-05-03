Database objects and operations
===============================

Once you defined your [models](./models) and the structure of your database entities, you need to make operations with them. In the next paragraphs we will inspect all the ways to create, modify and fetch your data from the database.

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

Emmett has also a more *low level* method to create records, that will skip the validation and insert the record directly into the database:

```python
>>> db.Dog.insert(name="Peggy")
2
```

As you can see, the `insert` method of the table defined by the model will return directly the `id` of the inserted record, since no validation was performed.

> **Note:**    
> Remember that if you're not in the request flow with the `Database` pipe, you have to commit your changes to effectively have them written into the database.

### Accessing the created record

As we just seen from the above methods, when you create a new record, Emmett returns just the integer corresponding to the `id` of the database row. If you look deeply, you will find that actually the return value is not just an integer:

```python
>>> rv = Dog.create("Penny")
>>> type(rv.id)
<class 'pydal.helpers.classes.Reference'>
```

In fact, you can access the attributes of the record you just created:

```python
>>> rv.id.name
'Penny'
>>> rv.id.as_dict()
{'id': 3, 'name': 'Penny'}
```

We will see more about the `as_dict` method in the next paragraphs.

Making queries
--------------

As soon as you have rows in your tables, you need to query them to fetch the data you want. Emmett provides a very efficient way to write queries using python language, since you will use your model fields and their methods.

But, before we proceed learning the syntax to make queries, we have to understand the main principle behind Emmett querying: the sets. Every time you work with the database to filter data, you're actually using a `Set` of rows corresponding to your query. The `Set` class is fundamental in Emmett and allows you to make all the operations on the records corresponding to your query, as we will see in the next paragraphs .

So, how you make queries on your database? Let's say, for example, that you have a table containing events, defined by the model:

```python
class Event(Model):
    name = Field()
    location = Field()
    participants = Field.int()
    happens_at = Field.datetime()
```

and you want to query all the events for a certain location. You can use your `Database` instance and its `where` method for that:

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

Emmett provides the `&`, `|` and `~` operators for the *and*, *or* and *not* conditions, in order to combine multiple conditions on the same query.

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

In all the examples we've seen above, we applied multiple where conditions on the same table. Emmett offers also a more compact way to write these queries using directly the `Model.where` method and a `lambda` notation:

```python
Event.where(lambda e: 
    ~(
        (e.location == "New York") | (e.location == "Chicago")
    ) & (e.happens_at >= request.now)
)
```

The resulting `Set` will obviously be the same.

### Query using tables

As we seen in the [models](./models) section, adding a model to your `Database` instance will add a `Table` object accessible both with the model name and the table name.

Since the tables share the fields with models, you can use them for querying too. In fact you can write the same query in all these ways:

```python
Event.where(lambda e: e.location == "New York")
db(Event.location == "New York")
db(db.Event.location == "New York")
db(db.events.location == "New York")
```

and all of them will produce the same result. Just use the one you prefer or that results more convenient for your code.

### Query all records in the table

When you want to work with all the records of a table, you have two options, one using the `Model` class and one with the `db()` syntax we have seen above:

```python
# from the model
Event.all()
# using Database instance
db(db.Event)
```

Both the methods will return the `Set` corresponding to all the records of the table.

### Additional query operators

Emmett also provides additional query operators that might be useful when you need particular conditions or for specific field types. Let's see them in detail.

#### belongs for the IN condition

When you need to perform sql *IN* conditions, you can use the `belongs` method:

```python
locations = ["New York", "Chicago"]
db(~Event.location.belongs(locations))
```

In this example we're asking all the events not happening in New York or Chicago.

#### String and text operators

An operator you may be familiar with is the `like` one, that produces a *LIKE* operation on the database. It works pretty similar to writing a raw sql query with a *LIKE* condition:

```python
db(Event.name.like("party%"))
```

where the *%* character is a wild-card meaning *any sequence of characters*, so the query will find any event starting with "party".

But Emmett provides also some shortcuts for the `like` operator with wild-card:

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

Note that the `like` operator will usually be case-sensitive on most of the DBMS, so if you want to make case-insensitive queries, you should specify the option on `like` and the other helpers:

```python
db(Event.name.like("party%", case_sensitive=False))
```

You can also use the `upper` and `lower` helpers:

```python
db(Event.name.upper().startswith("PARTY"))
```

Emmett provides also a `regexp` method on fields that works in the same way of the `like` one but allows regular expressions syntax for the look-up expression. Just remember that only some DBMS support it (PostgreSQL, MySQL, Oracle and SQLite).

#### Date and time operators

Emmett provides some additional operators for date, time and datetime fields, in particular:

* *date* and *datetime* fields have the `day`, `month` and `year` methods
* *time* and *datetime* fields have the `hour`, `minutes` and `seconds` methods

So, for example, you can query the events of a specific year quite easily:

```python
db(Event.happens_at.year() == 1985)
```

Selecting records
-----------------

Once you have made a query to your database and have a `Set`, you can fetch the records with the `select` method:

```python
>>> db(Event.location == "New York").select()
<Rows (2)>
```

The returning object of a `select` operation will always be a `Rows` object, which is an iterable of `Row` objects. A `Row` objects behaves quite like a dictionary, but allows you to access its elements as attributes, and implements some useful methods.

```python
>>> rows = db(Event.location == "New York").select()
>>> for row in rows:
...     print(row.name)
Awesome party
Secret party
>>> rows[0]
<Row {'happens_at': datetime.datetime(2016, 1, 7, 23, 0, 0), 'name': 'Awesome party', 'participants': 300, 'location': 'New York', 'id': 1}>
```

The `Rows` and `Row` objects have also some helper methods you might find useful. For example, the `Rows` object has a `first` and a `last` methods:

```python
>>> rows = db(Event.location == "New York").select()
>>> rows.first()
<Row {'happens_at': datetime.datetime(2016, 1, 7, 23, 0, 0), 'name': 'Awesome party', 'participants': 300, 'location': 'New York', 'id': 1}>
>>> rows.last()
<Row {'happens_at': datetime.datetime(2016, 1, 8, 23, 0, 0), 'name': 'Secret party', 'participants': 200, 'location': 'New York', 'id': 2}>
```

They work pretty the same like calling `rows[0]` and `rows[-1]` but while using integer position will raise an exception if the `Rows` object is empty, `first()` and `last()` will return `None`.

The `first` method can be useful also when you're looking for a single record:

```python
event = db(Event.name == "Secret Party").select().first()
if event:
    print(
        "Event %s starts at %s" % (
            event.name, str(event.happens_at)
         )
    )
else:
    print("Event not found")
```

The `Row` object has an `as_dict` method that you might find useful for serialization, since it will produce a dictionary from the original object without any callable object. For example, if you're working with json apis, you can render the dictionary directly as the json response.

```python
>>> rows = db(Event.location == "New York").select()
>>> rows.first().as_dict()
{'happens_at': datetime.datetime(2016, 1, 7, 23, 0, 0), 'name': 'Awesome party', 'participants': 300, 'location': 'New York', 'id': 1}
```

Similarly, the `Rows` object has both an `as_dict` and an `as_list` methods. While the `as_list` returns a list of rows serialized with `as_dict`, so you can avoid to call the `as_dict` of the rows recursively, the `as_dict` returns a dictionary that will have the ids of the rows as keys and the rows serialized with the `as_dict` method as values:

```python
>>> rows.as_list()
[{'happens_at': datetime.datetime(2016, 1, ...}, {...}]
>>> rows.as_dict()
{1: {'happens_at': datetime.datetime(2016, 1, ...}, 2: {...}}
```



Now, let's proceed with the options of the `select` method. It accepts unnamed arguments: these are interpreted as the names of the fields that you want to fetch. For example, you can be explicit on fetching just the *id* and *name* and fields:

```python
>>> rows = db(Event.location == "New York").select(Event.id, Event.name)
>>> rows[0]
<Row {'id': 1, 'name': 'Awesome party'}>
```

If you don't specify arguments, Emmett will select all the fields for all the tables involved in the query. In fact, the explicit argument for the first example is:

```python
db(Event.location == "New York").select(db.Event.ALL)
```

The `ALL` attribute of `Table` is, indeed, a special attribute that will select all the columns of the table.

> **Warning:** the `ALL` attribute is available on `Table` objects only, not on `Model` obejcts

### Shortcuts

*Changed in version 0.6*

Emmett provides some shortcuts that might be useful when you want to select single records. For example, you can select a single record using the `Model.get` method with the query:

```python
event = Event.get(name="Secret party")
```

or calling the table:

```python
event = db.Event(name="Secret party")
```

both the methods will produce the same result of writing:

```python
event = db(Event.name == "Secret party").select().first()
```

And if you want to select a record using the id, you can pass it as an unnamed parameter in both methods, or accessing it as a table item:

```python
event = Event.get(1)
event = db.Event(1)
event = db.Event[1]
```

The `Model` class has also a `first` and a `last` methods, that will select the first and the last record of the table, with ascending ordering of the `id` field:

```python
first_inserted = Event.first()
last_inserted = Event.last()
```

### Ordering

When you want to specify a ordering for selecting record, you can use the `orderby` option of the `select` method, that will produce an *ORDER BY* instruction in the sql query.

```python
db(Event.location == "New York").select(
    orderby=Event.happens_at
)
```

will return all the events in New York in ascending order by their dates (so the oldest one will be the first).

To have the rows in descending order (in this case the oldest one will be the last), just use the `~` operator:

```python
db(Event.location == "New York").select(
    orderby=~Event.happens_at
)
```

You can also concatenate multiple fields for ordering using the `|` operator:

```python
db(Event.location == "New York").select(
    orderby=Event.happens_at|Event.participants
)
```

### Pagination

When you select records, you often want to limit the result to a specific number of records, and use pagination to get the consequent results. Emmett provides the `paginate` option in the `select` method, so for example

```python
Event.all().select(paginate=1)
```

will return the first page of results, with 10 events per page. You can specify the size of the page using a tuple, so that

```python
Event.all().select(paginate=(2, 25))
```

will return the second page, with 25 events per page.

> **Note:** remember that `paginate` will always consider the first page number as 1, not 0

Emmett provides also a more sql-like option for limiting the results, the `limitby` one, that has the same syntax of the sql *LIMIT BY* instruction:

```python
Event.all().select(limitby=(25, 50))
```

with the starting offset and the ending one. This line of code will produce the same result of using `paginate=(2, 25)`.

### Aggregation

When you need to aggregate the rows with the same values for specific columns, you can use the `groupby` option of the `select` method. For example, you can select all the locations for events in 2015:

```python
db(Event.happens_at.year() == 2015).select(
    Event.location,
    orderby=Event.location,
    groupby=Event.location)
```

You can also specify a grouping condition, for example aggregate only records that have 300 or more participants:

```python
db(Event.happens_at.year() == 2015).select(
    Event.location,
    orderby=Event.location,
    groupby=Event.location,
    having=(Event.participants >= 300))
```

The argument of `having` should be a query with the same syntax you used for `db.where()`.

The `select` method also provides a `distinct` option, that has the same effect as grouping using all specified fields:

```python
db(Event.happens_at.year() == 1955).select(
    Event.location,
    distinct=True)
```

### Counting and expressions

Among with the `select` method, sets come with a `count` method:

```python
>>> Event.all().count()
3
```

But also fields have a `count` method. This is useful when you do aggregation as we seen in the above paragraph; for example you may want to count the number of events happened in 2015 grouped by their locations:

```python
count = Event.id.count()
db(Event.happens_at.year() == 2015).select(
    Event.location,
    count,
    orderby=Event.location,
    groupby=Event.location)
```

The resulting rows will be something like this:

```python
<Row {'events': {'location': 'New York'}, '_extra': {'COUNT(events.id)': 2}}>
```

And you can, for example, print the values using:

```python
>>> for row in rows:
...     print(row.events.location, row[count])
Chicago 1
New York 2
```

As you can see, you can access the *count* value using the variable as item of the row. Also notice that Emmett moved the *location* field into the *events* dictionary. This is done because you added elements that don't belongs to the events table itself, and Emmett wants to make this very explicit, grouping all the elements belonging to the table into a separated key of the rows.

Beside the `count` method, fields also have other methods useful to compute values from the records: the `sum`, `avg`, `min`, and `max` methods. They work all the same, like the `count` one. Let's say for example that you want to have the sum of all the participants to events in 1955 grouped by their locations:

```python
summed = Event.participants.sum()
db(Event.happens_at.year() == 1955).select(
    Event.location,
    summed,
    orderby=Event.location,
    groupby=Event.location)
```

You will have the same result structure we've seen for `count`.

Updating records
----------------

When you need to update existing data inside your database, you can use two different methods, the first one is the `update` method of the `Set` object:

```python
>>> db(Event.happens_at.year() == 1955).update(location="Hill Valley")
2
```

The `update` method accepts the column names and the values to change as named arguments, and it will update all the records corresponding to the set you have queried. The return value of the update method is, indeed, the number of records updated.

Since the `update` record is atomic, it also accepts expression built with model fields as arguments. As an example, you can increment a value:

```python
db(Event.location == "Hill Valley").update(
    participants=Event.participants+2)
```

As we've just seen, the `update` method is built on top of the `Set` object, so when you want to update a specific record, you should query for its `id` (or a combination of other values that makes the record unique):

```python
db(Event.id == 1).update(participants=3)
```

But this is not the only option, in fact the `Row` object has an `update_record` method, which is the second method in Emmett to update an existing record. In order to use this method, you should have a selected row with the `id` included in the selected fields.

This will produce the same result of the last example:

```python
>>> row = Event.get(1)
>>> row.update_record(participants=3)
<Row {'id': 1, 'location': 'Hill Valley' ...}>
```

where the main difference is that you made a *SELECT* sql operation and then an *UPDATE* one, while in the other example you did just the second one. Also, the `update_record` return the `Row` object updated to reflect the changed database record, instead of an integer.

> **Note:** `Row.update_record` should not be confused with `Row.update`, that will change the `Row` object but not the database record.

Mind that, writing lines like this:

```python
row = Event.get(1)
row.update_record(participants=row.participants+1)
```

won't produce an atomic update on the record, but will just write to the database the last selected value plus one. If you're intended to increment a value, you should use the `update` method of the `Set` with the expression as parameter, as we've seen before.

### Validation on updates

Now, since `update` and `update_record` **won't trigger validations** before effectively update the records in the database, Emmett also provides a `validate_and_update` method on the `Set` object, which works pretty the same of the `update` one:

```python
>>> db(Event.id == 1).validate_and_update(location="New York")
<Row {'updated': 1, 'errors': {}}>
```

except that it will trigger the validation on the values and the effective update of the records only on its success.    
As you can see the return value of the `validate_and_update` method will be a `Row` object containing the number of updated records under the `updated` attribute and the validation errors (if any) under the `errors` one.

Deleting records
----------------

Like for the update of records, Emmett provides two different methods to delete records:

- the `delete` method on the `Set` object
- the `delete_record` method of the `Row` object

Here are two examples:

```python
>>> db(Event.location == "New York").delete()
2
>>> row = Event.get(3)
>>> row.delete_record()
1
```

As you can see both of these methods return the number of record removed.

> **Note:** just like the `update_record`, the `delete_record` method requires you to select the `id` field in the rows.
