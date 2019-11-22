Callbacks
=========

Callbacks are methods that get called when specific database operations are performed on your data.

When you need to perform actions on one of these specific conditions, Emmett helps you with six different callbacks decorators that you can use inside your models, corresponding to the moments before and after a database insert, update and delete operations. The methods you decorate using these helpers will be invoked automatically when the database operation is performed.

All the callbacks method should return `None` or `False` (not returning anything in python is the same of returning `None`) otherwise returning `True` will abort the current operation.

Let's see these decorators in detail.

before\_insert
--------------

The `before_insert` decorator is called just before the insertion of a new record will be performed. The methods decorated with this helper should accept just one parameter that will be the dictionary mapping the fields and the values to be inserted in the table.    
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

The `after_insert` decorator is called just after the insertion of a new record happened. The methods decorated with this helper should accept the dictionary mapping the fields and the values that had been used for the insertion as the first parameter, and the id of the newly created record as the second one.    
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

As the `before_insert` callbacks is called just before a record insertion, the `before_update` one is called just before a set of records is updated. The methods decorated with this helper should accept the database set on which the update operation will be performed, and the dictionary mapping the fields and the values to use for the update as the second one.
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

The `after_update` decorator is called just after the update of the set of records has happened. As for the `before_update` decorator, the methods decorated with this helper should accept the database set on which the update operation was performed as the first parameter, and the dictionary mapping the fields and the values used for the update as the second one.
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

The `before_delete` decorator is called just before the deletion of a set of records will be performed. The methods decorated with this helper should accept just one parameter that will be the database set on which the delete operation should be performed.    
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

The `after_delete` decorator is called just after the deletion of a set of records has happened. As for the `before_delete` decorator, the methods decorated with this helper should accept just one parameter that will be the database set on which the delete operation was performed.    
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

Skip update callbacks
---------------------

Sometimes you would need to skip the invocation of the update callbacks, for example when you want to mutually *touch* related entities during the update of one of the sides of the relation. In these cases, you can use the `update_naive` method on the database sets that won't trigger the callbacks invocation.    
Let's see this with an example:

```python
class User(Model):
    email = Field()
    changed_at = Field.datetime()
    has_one('profile')

    @after_update
    def touch_profile(self, dbset, fields):
        row = dbset.select().first()
        self.db(
            db.Profile.user == row.id
        ).update_naive(
            changed_at=row.changed_at
        )

class Profile(Model):
    belongs_to('user')
    language = Field()
    changed_at = Field.datetime()
    
    @after_update
    def touch_user(self, dbset, fields):
        row = dbset.select().first()
        self.db(
            db.User.id == row.user
        ).update_naive(
            changed_at=row.changed_at
        )
```
