Computed and virtual attributes
===============================

Quite often during the development of your application you will need to compute values or perform operations that dependend on the values contained in the rows you're selecting, inserting or updating in your database.

Emmett provides different apis that can help you in these cases: let's see them in details.

Computed fields
---------------
*Changed in version 0.7*

Sometimes you need some field values to be *computed* using other fields' values. Let's say, for example, that you have a table of items where you store the quantity and price for each of them. You often need the total value of the items you have in your store, and you don't want to compute this value every time in your application code.

A solution can be to compute the value when you change the price or the quantity of the item and store that value to the database too. In this case you can use the `compute` decorator:

```python
from emmett.orm import Model, Field, compute

class Item(Model):
    price = Field.float()
    quantity = Field.int()
    total = Field.float()
    
    @compute('total')
    def compute_total(self, row):
        return row.price*row.quantity
```

As you can see, the `compute` decorator needs and accepts just one parameter: the name of the field where to store the result of the computation.

The function that performs the computation has to accept the row as its first parameter, and it will be called both on inserts and updates.

Virtual attributes
------------------
*Changed in version 1.0*

Virtual attributes are values returned by functions that will be injected to the involved rows every time you select them.

To clarify this concept, we will consider the same example we gave for the *computed* attributes and we will replace them with the `rowattr` decorator instead:

```python
from emmett.orm import Model, Field, rowattr

class Item(Model):
    price = Field.float()
    quantity = Field.int()
    
    @rowattr('total')
    def total(self, row):
        return row.price*row.quantity
``` 

As you can see, we don't have a real column in the table that will store the `total` value of the item, but we defined instead a method that evaluate it and add it to the selected rows.

> **Note:**    
> Since virtual attributes are, by definition, *virtuals*, you can't use them in order to make queries.

You can access the values as the common fields:

```python
>>> item = db(Item.price >= 2).select().first()
>>> item.total
30.0
```

Virtual methods
---------------
*Changed in version 1.0*

Similarly to virtual attributes, these methods are helpers injected to the rows when you select them. Differently from virtual attributes, however, they will be methods indeed, and you should invoke them to access the value you're looking for.

Let's consider again the same example we saw above, and let's use the `rowmethod` decorator:

```python
from emmett.orm import Model, Field, rowmethod

class Item(Model):
    price = Field.float()
    quantity = Field.int()
    
    @rowmethod('total')
    def total(self, row):
        return row.price*row.quantity
```

As we said, virtual methods are evaluated *on demand*, which means you have to invoke them when you want to access the values you need:

```python
>>> item = db(db.Item.price > 2).select().first()
>>> item.total()
30.0
```

### More on virtual methods

Field methods are a great instrument also to run database operations from the current selected object. In fact, since you're inside the model instance, you can access the model itself, the table and the database from within the method you're writing.

For example, let's say you have a table of messages referring to some topics and you want to easily get the next message from the current one. You can write down a method for that:

```python
from emmett.orm import Model, belongs_to, rowmethod

class Message(Model):
    belongs_to('topic', 'author')
    body = Field.text()
    written_at = Field.datetime()

    @rowmethod('next_one')
    def get_next_message(self, row):
        return self.db(
            (self.topic == row.topic) &
            (self.written_at > row.written_at)
        ).select(
            orderby=self.written_at, 
            limitby=(0, 1)
        ).first()
```

Then, once we have a message, we can access the next quickly:

```python
>>> message = db(db.Message.topic == 1).select().first()
>>> message
<Row {'id': 2L, 'topic': 1L, 'author': 1L, 'written_at': datetime.datetime(2015, 12, 22, 9, 18, 23, 118701), 'body': 'This is a test message'} >
>>> message.next_one()
<Row {'id': 3L, 'topic': 1L, 'author': 1L, 'written_at': datetime.datetime(2015, 12, 22, 9, 20, 21, 229511), 'body': 'This is another test message'} >
```

Virtual methods, as we saw for virtual fields, needs the row as first parameter, that will be injected by Emmett, but you can obviously add more parameters and pass values for them during invocation.
