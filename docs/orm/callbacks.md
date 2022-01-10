Callbacks
=========

Callbacks are methods that get called when specific database operations are performed on your data.

When you need to perform actions on one of these specific conditions, Emmett helps you with several different callbacks decorators that you can use inside your models, corresponding to different moments before and after certain database operations. The methods you decorate using these helpers will be invoked automatically when the database operation is performed.

All the callbacks method should return `None` or `False` (not returning anything in python is the same of returning `None`) otherwise returning `True` will abort the current operation.

Let's see these decorators in detail.

before\_insert
--------------

The `before_insert` callback is called just before the insertion of a new record will be performed. The methods decorated with this helper should accept just one parameter that will be the dictionary mapping the fields and the values to be inserted in the table.    
Here is a quick example:

```python
from emmett.orm import Model, before_insert

class Thing(Model):
    name = Field()

    @before_insert
    def print_values(self, fields):
        print(fields)
```

Now, if you insert a new record, you will see the printed values:

```python
>>> db.Thing.insert(name="cube")
{'name': 'cube'}
```

after\_insert
-------------

The `after_insert` callback is called just after the insertion of a new record happened. The methods decorated with this helper should accept the dictionary mapping the fields and the values that had been used for the insertion as the first parameter, and the id of the newly created record as the second one.    
Here is a quick example:

```python
from emmett.orm import Model, after_insert

class Thing(Model):
    name = Field()

    @after_insert
    def print_values(self, fields, rid):
        print(fields, rid)
```

Now, if you insert a new record, you will see the printed values:

```python
>>> db.Thing.insert(name="cube")
{'name': 'cube'}, 1
```

The `after_insert` callbacks becomes handy when you need to initialize related data. Let's say for example that you want to store some profiling data about your users on another table and you want to create the related record just after the user one has been inserted:

```python
class User(Model):
    email = Field()
    password = Field()
    has_one('profile')

    @after_insert
    def create_profile(self, fields, uid):
        self.db.Profile.insert(user=uid)

class Profile(Model):
    belongs_to('user')
    language = Field(default="en")
```

before\_update
--------------

As the `before_insert` callback gets called just before a record insertion, the `before_update` one is called just before a set of records is updated. The methods decorated with this helper should accept the database set on which the update operation will be performed, and the dictionary mapping the fields and the values to use for the update as the second one.
Here is a quick example:

```python
from emmett.orm import Model, before_update

class Thing(Model):
    name = Field()

    @before_update
    def print_values(self, dbset, fields):
        print(dbset, fields)
```

Now, if you update a set of records, you will see the printed values:

```python
>>> db(db.Thing.id == 1).update(name="sphere")
<Set (things.id = 1)>, {'name': 'Sphere'}
```

Notice that, since the first parameter is a database set, you can have more than one record involved in the operation.

after\_update
-------------

The `after_update` callback is called just after the update of the set of records has happened. As for the `before_update` decorator, the methods decorated with this helper should accept the database set on which the update operation was performed as the first parameter, and the dictionary mapping the fields and the values used for the update as the second one.
Here is a quick example:

```python
from emmett.orm import Model, after_update

class Thing(Model):
    name = Field()

    @after_update
    def print_values(self, dbset, fields):
        print(dbset, fields)
```

Now, if you update a set of records, you will see the printed values:

```python
>>> db(db.Thing.id == 1).update(name="sphere")
<Set (things.id = 1)>, {'name': 'Sphere'}
```

before\_delete
--------------

The `before_delete` callback is called just before the deletion of a set of records will be performed. The methods decorated with this helper should accept just one parameter that will be the database set on which the delete operation should be performed.    
Here is a quick example:

```python
from emmett.orm import Model, before_delete

class Thing(Model):
    name = Field()

    @before_delete
    def print_values(self, dbset):
        print(dbset)
```

Now, if you delete a set of records, you will see the printed values:

```python
>>> db(db.Thing.id == 1).delete()
<Set (things.id = 1)>
```

after\_delete
-------------

The `after_delete` callback is called just after the deletion of a set of records has happened. As for the `before_delete` decorator, the methods decorated with this helper should accept just one parameter that will be the database set on which the delete operation was performed.    
Here is a quick example:

```python
from emmett.orm import Model, after_delete

class Thing(Model):
    name = Field()

    @after_delete
    def print_values(self, dbset):
        print(dbset)
```

Now, if you delete a set of records, you will see the printed values:

```python
>>> db(db.Thing.id == 1).delete()
<Set (things.id = 1)>
```

Notice that in the `after_delete` callbacks you will have the database set parameter, but the records corresponding to the query have been just deleted and won't be accessible anymore.

before\_save
------------

*New in version 2.4*

The `before_save` callback is invoked just before the execution of the `save` operation from the relevant record. The methods decorated with this helper should accept just one parameter that will be the record getting saved.    
Here is a quick example:

```python
class Product(Model):
    name = Field.string()
    price = Field.float(default=0.0)


class CartElement(Model):
    belongs_to("product")

    quantity = Field.int(default=1)
    price_denorm = Field.float(default=0.0)

    @before_save
    def _rebuild_price(self, row):
        row.price_denorm = row.quantity * row.product.price
```

> **Note**: `save` triggers both `before_save` and the relevant insert or update callbacks. During the operation `before_save` will be invoked before the `before_insert` or `before_update` callbacks.

after\_save
-----------

*New in version 2.4*

The `after_save` callback is invoked just after the execution of the `save` operation from the relevant record. The methods decorated with this helper should accept just one parameter that will be the saved record.    
Here is a quick example:

```python
class User(Model):
    email = Field()

    @after_save
    def _send_welcome_email(self, row):
        # if is a new user, send a welcome email
        if row.has_changed_value("id"):
            send_welcome_email(row.email)
```

> **Note**: `save` triggers both `after_save` and the relevant insert or update callbacks. During the operation `after_save` will be invoked after the `after_insert` or `after_update` callbacks.

before\_destroy
---------------

*New in version 2.4*

The `before_destroy` callback is invoked just before the execution of the `destroy` operation from the relevant record. The methods decorated with this helper should accept just one parameter that will be the record getting destroyed.    
Here is a quick example:

```python
class Product(Model):
    name = Field.string()
    price = Field.float(default=0.0)


class CartElement(Model):
    belongs_to("product")

    quantity = Field.int(default=1)
    price_denorm = Field.float(default=0.0)

    @before_destroy
    def _clear_element(self, row):
        row.quantity = 0
        row.price_denorm = 0
```

> **Note**: `destroy` triggers both `before_destroy` and `before_delete` callbacks. During the operation `before_destroy` will be invoked before the `before_delete` callback.

after\_destroy
--------------

*New in version 2.4*

The `after_destroy` callback is invoked just after the execution of the `destroy` operation from the relevant record. The methods decorated with this helper should accept just one parameter that will be the destroyed record.    
Here is a quick example:

```python
class Cart(Model):
    has_many({"elements": "CartElement"})
    updated_at = Field.datetime(default=now, update=now)


class CartElement(Model):
    belongs_to("cart")

    @after_destroy
    def _update_cart(self, row):
        row.cart.save()
```

> **Note**: `destroy` triggers both `after_destroy` and `after_delete` callbacks. During the operation `after_destroy` will be invoked after the `after_delete` callback.

before\_commit and after\_commit
--------------------------------

*New in version 2.4*

Emmett also provides callbacks to watch `commit` events on [transactions](./connecting#transactions). Due to their nature, these callbacks behave differently from the other ones, and thus we need to make some observations:

- code encapsuled in these callbacks **should not make any database operation**, as it might breaks the current transaction stack
- these callbacks will be invoked in bulk once the trasaction is getting committed, thus the callback for the operation and the commit one won't probably be called one after another, and the commit one will receive all the operations happened during the transaction itself, not just the last one

> **Note:** commit callbacks get triggered only on the top transaction, not in the nested ones (savepoints).

The methods decorated with these helpers should accept two parameters: the operation type and the operation context:

```python
@after_commit
def my_method(self, op_type, ctx):
    ...
```

The operation type is one of the values provided by the `TransactionOps` enum, and will be one of the following:

- insert
- update
- delete
- save
- destroy

Now, since `before_commit` and `after_commit`, as we saw, catch all the operations happening on the relevant model, these methods offers additional filtering in order to watch only the relevant events. In order to listen only particular operations, you can use the `TransactionOps` enum in combination with the `operation` method:

```python
from emmett.orm import TransactionOps

@after_commit.operation(TransactionOps.insert)
def my_method(self, ctx):
    ...
```

as you can see, filtered operation callbacks won't need the operation type parameter.

The operation context is represented by an object with the following attributes:

| attribute | description |
| --- | --- |
| values | fields and values involved |
| return\_value | return value of the operation |
| dbset | query set involved (for update and delete operations) |
| row | row involved (for save and destroy operations) |
| changes | row changes occurred (for save and destroy operations) |

Now, let's see all of this with some examples. 

We might want to send a welcome email to a newly registered user, and we want to be sure the operation commited:

```python
class User(Model):
    email = Field()

    @after_commit.operation(TransactionOps.insert)
    def _send_welcome_email(self, ctx):
        my_queue_system.send_welcome_email(ctx.return_value)
```

or we might track activities over the records:

```python
class Todo(Model):
    belongs_to("owner")
    
    description = Field.text()
    completed_at = Field.datetime()

    @after_commit.operation(TransactionOps.save)
    def _store_save_activity(self, ctx):
        activity_type = "creation" if "id" in ctx.changes else "edit"
        my_queue_system.store_activity(activity_type, ctx.row, ctx.changes)

    @after_commit.operation(TransactionOps.destroy)
    def _store_save_activity(self, ctx):
        my_queue_system.store_activity("deletion", ctx.row, ctx.changes)
```

Skip callbacks
--------------

*Changed in version 2.4*

Sometimes you would need to skip the invocation of callbacks, for example when you want to mutually *touch* related entities during the update of one of the sides of the relation. In these cases, you can use the `skip_callbacks` parameter in the method you're calling.    
Let's see this with an example:

```python
class User(Model):
    has_one('profile')

    email = Field()
    changed_at = Field.datetime()

    @after_save
    def touch_profile(self, row):
        profile = row.profile()
        profile.changed_at = row.changed_at
        profile.save(skip_callbacks=True)

class Profile(Model):
    belongs_to('user')
    language = Field()
    changed_at = Field.datetime()
    
    @after_save
    def touch_user(self, row):
        row.user.changed_at = row.changed_at
        row.user.save(skip_callbacks=True)
```
