Relations
========
*New in version 0.4*

One of the big advantages of using a relational database is, indeed, the ability of establishing relations between data.    
weppy provides some helpers to simplify the definition of those relations and to perform operations with related entities. Let's see a quick example in order to have an idea on how they works:

```python
class Doctor(Model):
    name = Field()
    has_many('patients')

class Patient(Model):
    name = Field()
    age = Field('int')
    belongs_to('doctor')
```

As you can see, we used the `belongs_to` and `has_many` helpers in order to define a one-to-many relation between doctors and patients, so that a doctor has many patients and a patient can have only one doctor.

These helpers will also add attributes and helpers on records in order to access related data more quickly. In the next paragraphs we will inspect all the available helpers and how to use them in order to perform operations between related data.

belongs\_to
-------------

The `belongs_to` helper allows you to define relations that depends on other entities. If we recall the example we seen above:

```python
class Patient(Model):
    belongs_to('doctor')
```

we can clearly understand what will happen on the database: the patients table will have a column containing the id of the referred row from the doctors table.

The referred doctor will be available on a patient object selected from your database just as an attribute:

```python
patient = db.Patient(name="Pinkman")
doctor_name = patient.doctor.name
```

In weppy `belongs_to` has a real *belonging* meaning, and when we use it we're implicitly making an assertion: a patient cannot exists without a doctor. Actually this is correct also under a logical point of view: to name "patient" someone, he or she has to be in cure by some doctor, otherwise we won't call it a "patient".

This assertion has some consequences on the validation and on the deletion policies, in fact weppy will:

- set the `notnull`  option of `doctor` field of `Patient` and add a `{'presence': True}` validation policy on it, ensuring that this attribute is present and points to an existing record in doctors table
- use a `cascade` rule on the relations, so when a doctor is deleted, also its patient follow the same destiny

> **Note:**    
> When using the `belongs_to` helper, ensure the model you're referencing to is defined **before** the one where you using the helper.

Whenever you don't need a strictly dependency for this kind of relation, you can use the `refers_to` helper.

refers\_to
---------
*New in version 0.6*

The `refers_to` helper, as of the `belongs_to`, allows you to define relations that depends on other entities, but not in a way where these relations are *necessary*. To explain this concept, let's see another example:

```python
class Note(Model):
    body = Field('text')

class Todo(Model):
    title = Field()
    done = Field('bool')
    refers_to('note')
```

In the same way happened with `belongs_to`, the todos table will have a column containing the id of the referred row from the notes table, but in this case, we allow this value to be empty.

In fact, `refers_to` in weppy has a *reference without need* meaning, meaning that reflects in the idea (in this specific case) that a todo can exists even if doesn't have a note attached to it.

Due to this concept, in this case weppy will:

- add a `{'presence': True, 'allow': 'empty'}` validation policy on the `note` attribute of `Todo`, allowing the value to be empty, and when it's not, ensuring that the attribute points to an existing record in notes table
- use a `nullify` rule on the relations, so when a note is deleted, all the todos which had a relation with it will still exists with removed relation

> **Note:**    
> When using the `refers_to` helper, ensure the model you're referencing to is defined **before** the one where you using the helper.

has\_many
---------

The `has_many` helper is intended to be used as the reverse operator of a `belongs_to` or a `refers_to` in one-to-many relations. You have already seen it from the first example:

```python
class Doctor(Model):
    has_many('patients')

class Patient(Model):
    belongs_to('doctor')
```

where we used the `has_many` helper on the `Doctor` model in order to specify the many relations with `Patient`.

Differently from `belongs_to` and `refers_to`, the `has_many` helper won't produce anything on the database side, as it will map a set of the records referring to current record itself. Practically speaking, the `has_many` helper will use the opposite relation in order to know which records are referring to the object.

The `has_many` helper becomes handy for your application code rather than the data you store, in fact when you have a record representing a doctor, you can have the set of patients referred to it as an attribute:

```python
>>> doctor_bishop = db.Doctor(name="Bishop")
>>> doctor_bishop.patients
<Set (patients.doctor = 1)>
```

We will inspect all the operations you can do with the sets generated via `has_many` in the next paragraphs.

has\_one
---------

The `has_one` helper is intended to be used as the reverse operator of a `belongs_to` or a `refers_to` in one-to-one relations. Let's see how it works with an example:

```python
class Citizen(Model):
    name = Field()
    has_one('passport')

class Passport(Model):
    number = Field()
    belongs_to('citizen')

    validation = {
        'citizen': {'unique': True}
    }
```

In this case we have a one-to-one relationship between citizens and passports: in fact, a passport belongs to a citizen and a citizen can only have a passport (or no passport at all).    
Note that we also added the `unique` validation of `citizen` in `Passport` to avoid creation of multiple records referred to the same citizen.

As for the `has_many` helper, `has_one` won't produce anything on the database side, as it will map the single records referring to current record itself, using the opposite relation.

The `has_one` helper is useful for your application code, since you can directly access the passport record referred to a citizen:

```python
>>> ww = db.Citizen(name="Heisenberg")
>>> ww.passport
<Row {'number': 'AA1234', 'id': 1L, 'citizen': 1L}>
```

Many to many relations and "via" option
------
In order to create a many-to-many relationship, you have to use a *join table*. Some frameworks will hide to you this by generating those tables for you, but weppy won't do hidden operations on you database, and, as a consequence of a *design decision*, requires you to write down the model of the join table too, and to be conscious of what happening.

A quite common many-to-many relations is the one between users and groups, where an user can have many groups and a group have many users. In weppy we can write down these models:

```python
class User(Model):
    name = Field()
    has_many('memberships')

class Group(Model):
    name = Field()
    has_many('memberships')

class Membership(Model):
    belongs_to('user', 'group')
``` 

This will reflect our tables: we have a users table, a groups table, and a memberships table which maps the belonging of a user into a group from the other two tables.

This is quite correct, but we missing the advantage here, since we don't have any direct access to users from a specific group or to the groups of a specific users, since we should pass trough the memberships and then use these to gain the result-set we want.    
This is why weppy has a `via` option with the `has_many` helper so that we can rewrite the upper example like this:

```python
class User(Model):
    name = Field()
    has_many(
        'memberships',
        {'groups': {'via': 'memberships'}}
    )

class Group(Model):
    name = Field()
    has_many(
        'memberships',
        {'users': {'via': 'memberships'}}
    )

class Membership(Model):
    belongs_to('user', 'group')
```

Using the `via` option, we finally achieve the desired result, as we can access users from a group and groups from a user:

```python
>>> user = db.User(name="Walter White")
>>> user.groups
<Set ((memberships.user = 1) AND (memberships.group = groups.id))>
>>> group = db.Group(name="Los Pollos Hermanos")
>>> group.users
<Set ((memberships.group = 1) AND (memberships.user = users.id))>
```

### Using via option for shortcuts

The `via` option can be useful also without join tables. To understand the scenario, consider this example:

```python
class University(Model):
    has_many(
        'courses', 
        {'attendants': {'via': 'courses'}}
    )

class Course(Model):
    belongs_to('university')
    has_many('attendants')

class Attendant(Model):
    belongs_to('course')
```

As you can see, you can use `via` to share `has_many` relations to `belongs_to` or `refers_to` relations: in this case we're giving to the university the ability to fetch attendants from all their courses:

```python
>>> university = db.University[1]
>>> university.attendants
<Set ((courses.university = 1) AND (attendants.course = courses.id))>
```

Naming and advanced relations
--------
Under the default behavior, `belongs_to`, `refers_to`, `has_one` and `has_many` use the passed argument both for the attribute naming and the model you're referencing to, so:

- `belongs_to('user')` or `refers_to('user')` will add a `user` field to your model referenced to `User` model
- `has_one('passport')` will add a virtual `passport` attribute to your rows referenced to `Passport` model
- `has_many('attendants')` will add a virtual `attendants` attribute to your rows referenced to `Attendant` model

Sometimes, you may want to use a different name for the attribute responsible of the relation. Let's say, for example, that you want an `owner` attribute for the relation with the `User` model. You can reach this just writing:

```python
belongs_to({'owner': 'User'})
has_one({'owner': 'User'})
```

The same thing becomes necessary when you're working with model names that are not *regular plurals* in english. In fact, as we seen for the table naming, weppy doesn't have a *real pluralization engine*, so for example, if you have a `Mouse` model, and a many relation with it, you need to manually specify the attribute and the model names:

```python
has_many({'mice': 'Mouse'})
```

### Specify fields and models in relations

When you have relations that should be mapped to custom named fields, you should specify them in both sides of the relations. This happens often when you have multiple relations to the same model, as in this example:

```python
class User(Model):
    name = Field()
    has_many(
        {'owned_todos': 'Todo.owner'},
        {'assigned_todos': 'Todo.assigned_user'}
    )

class Todo(Model):
    description = Field()
    belongs_to({'owner': 'User'})
    refers_to({'assigned_user': 'User'})
```

As you can see, we have that a `Todo` always have an owner, which is a `User`, and it also might have an assigned user, which is a `User` to.

We specified the model in the `belongs_to` and the `refers_to` helpers, and the model and the field with the format `Model.field`  in the `has_many` helpers. With this notations we can access the relation sets as usual.

### Self references

Specifying relation models becomes handy also in situations where you have relations with the same model, for example:

```python
class Person(Model):
    name = Field()
    refers_to({'father': 'self'})
    has_many({'children': 'self.father'})
```

As you can see, we defined a model `Person` which can have a relation with another record of the same table: father is a `Person` too. In order to achieve this result, we simply used the keyword `self`. You can also use the model name for the relation, changing `'self'` with `'Person'`, and weppy will understand that too, but we think this way is more self-explanatory.

Operations with relations
--------------------

[...]

### has\_many sets methods

Every time you use the `has_many` helper, weppy add an attribute of type `Set` (pydal's class) with the specified name on the `Row` object you've selected. Let's see it with the above example of users and things:

```python
>>> u = db.User(id=1)
>>> u.memberships
<Set (memberships.user = 1)>
>>> u.things
<Set ((memberships.user = 1) AND (memberships.thing = things.id))>
```

Since the object is a specific set of your database responding to a query, you have all the standard methods to run operations on in:

| method | description |
| --- | --- |
| count | count the records in the set |
| select | get the records of the set |
| update | update all the records in the set |
| validate\_and\_update | perform a validation and update the records |
| delete | delete all the records in the set |
| where | return a subset given additional queries |
| add | add a row to the set |

As you observed, until now we used a shortcut for the `select` method just calling the set:

```python
>>> u.things.select()
<Rows (1)>
>>> u.things()
<Rows (1)>
```

While all the methods described are quite intuitive, and works in the same way of running operations on tables, the add option can be quite useful when you need to add a relation to an existing object:

```python
>>> cube = db.Thing(name="cube")
>>> user = db.User(id=1)
>>> user.things.add(cube)
```

which is just another way of doing:

```python
>>> db.Membership.insert(user=user, thing=thing)
```
