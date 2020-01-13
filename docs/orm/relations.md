Relations
=========
*New in version 0.4*

One of the big advantages of using a relational database is, indeed, the ability of establishing relations between data.    
Emmett provides some helpers to simplify the definition of those relations and to perform operations with related entities. Let's see a quick example in order to have an idea on how they work:

```python
class Doctor(Model):
    name = Field()
    has_many('patients')

class Patient(Model):
    name = Field()
    age = Field.int()
    belongs_to('doctor')
```

As you can see, we used the `belongs_to` and `has_many` helpers in order to define a one-to-many relation between doctors and patients, so that a doctor has many patients and a patient can have only one doctor.

These helpers will also add attributes and helpers on records in order to access related data more quickly. In the next paragraphs we will inspect all the available helpers and how to use them in order to perform operations between related data.

belongs\_to
-----------

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

In Emmett `belongs_to` has a real *belonging* meaning, and when we use it we're implicitly making an assertion: a patient cannot exists without a doctor. Actually this is correct also under a logical point of view: to name "patient" someone, he or she has to be in cure by some doctor, otherwise we won't call it a "patient".

This assertion has some consequences on the validation and on the deletion policies, in fact Emmett will:

- set the `notnull`  option of `doctor` field of `Patient` and add a `{'presence': True}` validation policy on it, ensuring that this attribute is present and points to an existing record in doctors table
- use a `cascade` rule on the relations, so when a doctor is deleted, also its patient follows the same destiny

> **Note:**    
> When using the `belongs_to` helper, ensure the model you're referencing to is defined **before** the one where you using the helper.

Whenever you don't need a strictly dependency for this kind of relation, you can use the `refers_to` helper.

refers\_to
----------
*New in version 0.6*

The `refers_to` helper, as of the `belongs_to`, allows you to define relations that depends on other entities, but not in a way where these relations are *necessary*. To explain this concept, let's see another example:

```python
class Note(Model):
    body = Field.text()

class Todo(Model):
    title = Field()
    done = Field.bool()
    refers_to('note')
```

In the same way happened with `belongs_to`, the todos table will have a column containing the id of the referred row from the notes table, but in this case, we allow this value to be empty.

In fact, `refers_to` in Emmett has a *reference without need* meaning, meaning that reflects in the idea (in this specific case) that a todo can exists even if doesn't have a note attached to it.

Due to this concept, in this case Emmett will:

- add a `{'presence': True, 'allow': 'empty'}` validation policy on the `note` attribute of `Todo`, allowing the value to be empty, and when it's not, ensuring that the attribute points to an existing record in notes table
- use a `nullify` rule on the relations, so when a note is deleted, all the todos which had a relation with it will still exist with removed relation

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
*Changed in version 0.6*

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

As for the `has_many` helper, `has_one` won't produce anything on the database side, as it will map the single records referring to the current record itself, using the opposite relation.

The `has_one` helper is useful for your application code, since you can directly access the passport record referred to a citizen:

```python
>>> ww = db.Citizen(name="Heisenberg")
>>> ww.passport
<Set (passports.citizen = 1)>
>>> ww.passport()
<Row {'number': 'AA1234', 'id': 1L, 'citizen': 1L}>
```

Many to many relations and "via" option
---------------------------------------
In order to create a many-to-many relationship, you have to use a *join table*. Some frameworks will hide to you this by generating those tables for you, but Emmett won't do hidden operations on you database, and, as a consequence of a *design decision*, requires you to write down the model of the join table too, and to be conscious of what happening.

A quite common many-to-many relations is the one between users and groups, where an user can have many groups and a group have many users. In Emmett we can write down these models:

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

This is quite correct, but we missing the advantage here, since we don't have any direct access to users from a specific group or to the groups of a specific users, since we should pass through the memberships and then use these to gain the result-set we want.    
This is why Emmett has a `via` option with the `has_many` helper so that we can rewrite the upper example like this:

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
>>> user.groups()
<Rows (1)>
>>> group = db.Group(name="Los Pollos Hermanos")
>>> group.users
<Set ((memberships.group = 1) AND (memberships.user = users.id))>
>>> group.users()
<Rows (1)>
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
-----------------------------
Under the default behavior, `belongs_to`, `refers_to`, `has_one` and `has_many` use the passed argument both for the attribute naming and the model you're referencing to, so:

- `belongs_to('user')` or `refers_to('user')` will add a `user` field to your model referenced to `User` model
- `has_one('passport')` will add a virtual `passport` attribute to your rows referenced to `Passport` model
- `has_many('attendants')` will add a virtual `attendants` attribute to your rows referenced to `Attendant` model

Sometimes, you may want to use a different name for the attribute responsible of the relation. Let's say, for example, that you want an `owner` attribute for the relation with the `User` model. You can reach this just writing:

```python
belongs_to({'owner': 'User'})
has_one({'owner': 'User'})
```

The same thing becomes necessary when you're working with model names that are not *regular plurals* in english. In fact, as we seen for the table naming, Emmett doesn't have a *real pluralization engine*, so for example, if you have a `Mouse` model, and a many relation with it, you need to manually specify the attribute and the model names:

```python
has_many({'mice': 'Mouse'})
```

### Specify fields and models in relations
*New in version 0.6*

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

As you can see, we have that a `Todo` always has an owner, which is a `User`, and it also might have an assigned user, which is a `User` too.

We specified the model in the `belongs_to` and the `refers_to` helpers, and the model and the field with the format `Model.field`  in the `has_many` helpers. With this notations we can access the relation sets as usual.

### Self references
*New in version 0.6*

Specifying relation models becomes handy also in situations where you have relations with the same model, for example:

```python
class Person(Model):
    name = Field()
    refers_to({'father': 'self'})
    has_many({'children': 'self.father'})
```

As you can see, we defined a model `Person` which can have a relation with another record of the same table: father is a `Person` too. In order to achieve this result, we simply used the keyword `self`. You can also use the model name for the relation, changing `'self'` with `'Person'`, and Emmett will understand that too, but we think this way is more self-explanatory.

### Scoped relations
*New in version 0.7*

Sometimes you may need to specify scopes on `has_one` and `has_many` relations. A common example is when you use *soft-deleting* in your application:

```python
class User(Model):
    name = Field()
    has_many({'todos': {'scope': 'not_deleted'}})

class Todo(Model):
    belongs_to('user')
    description = Field()
    is_deleted = Field.bool()

    @scope('not_deleted')
    def _not_deleted(self):
        return self.is_deleted == False
```

As you can see, we have that the `Todo` model has an `is_deleted` field and a scope `not_deleted` that filters out the records we have set as deleted. Using the `scope` option in the `has_many` relation of the `User` model, Emmett will returns only those records when selecting rows from a specific user, and, also, will set the fields with the correct values from the scope query when we add or create new records related to a specific user.

Whenever you have to specify the reference field using the `scope` option, Emmett requires you to combine it with the `target` one:

```python
class User(Model):
    has_many({'todos': {'target': 'Todo.owner', 'scope': 'not_deleted'}})

class Todo(Model):
    belongs_to({'owner': 'User'})
```

> **Note:** when using `scope` on `via` relations, remember you're applying the scope condition on the final model involved in the relation.

### Where condition on relations
*New in version 0.7*

Similarly to the `scope` option, you can use the `where` option to specify queries that should be applied by Emmett when building the relation: this is handy when you need the condition just one and you don't need to write a scope for that.

For example, we can change the upper example and rewrite it as:

```python
class User(Model):
    name = Field()
    has_many({'todos': {'where': lambda m: m.is_deleted == False}})

class Todo(Model):
    belongs_to('user')
    description = Field()
    is_deleted = Field.bool()
```

As you can see the `where` value must be a `lambda` function accepting just one parameter: the model you're referring to. The condition can be any valid expression in the Emmett query language.

> **Hint:** you can also specify `where` conditions on existing `scope` relations, to combine the queries.


Operations with relations
-------------------------

*Changed in version 0.6*

As we've seen from the above paragraphs, `belongs_to` and `refers_to` will create an attribute that let you access the referred record when you perform a select. In fact, given the same model of the example:

```python
class Patient(Model):
    belongs_to('doctor')
```

we can access the doctor of a certain patient directly from this last one:

```python
>>> patient = Patient.first()
>>> patient.doctor
1
>>> patient.doctor.name
'Bishop'
```

but you can see that accessing `patient.doctor` will return you the `id` of the referred record, not the record itself. This is because Emmett won't load the relations immediately, and the attribute `doctor` of the selected patient is, indeed, not a `Row` object:

```python
>>> type(patient.doctor)
<class 'pydal.helpers.classes.Reference'>
```

the `Reference` object is in fact responsible of selecting the referred record only when you need to access its attributes.

> **Note:** remember that when you access an attribute of a `Reference` object, a *SELECT* to the database is performed, once per referred record.

On the other hand, the `has_many` and `has_one` helpers will attach `Set` objects to the selected row, so given the same model of the example:

```python
class Doctor(Model):
    has_many('patients')
```

accessing the `patients` attribute of a selected doctor, will give you the same kind of object we inspected in the [operations chapter](./operations):

```python
>>> doctor = Doctor.first()
>>> doctor.patients
<Set (patients.doctor = 1)>
```

As a consequence, on these objects you have the same methods we already discussed for `Set`:

| method | description |
| --- | --- |
| where | return a subset given additional queries |
| select | get the records |
| count | count the records |
| update | update all the records |
| validate\_and\_update | perform a validation and update the records |
| delete | delete all the records |

and [scopes](./scopes) will work on these sets as well, so if you defined, for example, a scope named *males* in your `Patient` model, you can use it with the same syntax:

```python
doctor.patients.males().select(paginate=1)
```

The `has_one` and `has_many` generated sets will also have a shortcut for `select` and some additional methods that can help you when performing operations on relations. Let's see them.

### has\_one sets methods

Since accessing the relations is generally the most performed operation, you also have a **shortcut** for the `select` method if you just call the attribute of an `has_one` set:

```python
>>> ww = Citizen.get(name="Heisenberg")
>>> ww.passport()
<Row {'number': 'AA1234', 'id': 1L, 'citizen': 1L}>
```

as you can see, calling the `passport` attribute directly will perform a `select().first()` call on the set. The shortcut will consequentially call the `first` method of the `Rows` object since an `has_one` relationship expects to have only one record related to the original row.

> **Note:** calling the shortcut or the `select` method without parameters will perform caching of the other row object on the set. If you need to avoid this for consequent calls, use the `reload` parameter set to `True`.

The `has_one` sets also have a `create` method:

```python
citizen = Citizen.first()
citizen.passport.create(number="AA123")
```

that will perform a validation and an insert operation with the reference bound to the current record. The operation is the same of writing:

```python
citizen = Citizen.first()
Passport.create(number="AA123", citizen=citizen)
```

### has\_many sets methods

Similarly to the `has_one` sets, the `has_many` ones have a **shortcut** for the `select` method if you just call the attribute:

```python
>>> doctor.patients()
<Rows (1)>
```

This shortcut will return the rows referenced to the record, and accepts the same parameters accepted by the `select` method.

> **Note:** calling the shortcut or the `select` method without parameters will perform caching of the referred rows on the set. If you need to avoid this for consequent calls, use the `reload` parameter set to `True`.

The `has_many` sets also have three more methods that can help you performing operations with relations, in particular the `create`, `add` and `remove` methods. These methods have a slightly different behavior when the `has_many` helper is configured with the `via` options. Let' see them in details.

#### Creating new related records

The `create` method of the `has_many` sets behaves quite like the ones built with the `has_one` helper:

```python
>>> doctor = Doctor.first()
>>> doctor.patients.create(name="Walter White", age=50)
<Row {'errors': {}, 'id': 6}>
```

It will perform a validation and then insert a new record referred to the `doctor` row.

Note that this method is available only if your `has_many` relation is not a `via` one; in fact, for sets produced with `has_many` relations and `via` option the `create` method will raise a `RuntimeError`.    
This is a consequence of the fact that Emmett doesn't know if you have additional columns in your join table. In fact, if you consider this example:

```python
class User(Model):
    name = Field()
    has_many(
        'memberships', 
        {'organizations': {'via': 'memberships'}})

class Organization(Model):
    name = Field()
    has_many(
        'memberships',
        {'users': {'via': 'memberships'}})

class Membership(Model):
    belongs_to('user', 'organization')
    role = Field()
```

the `Membership` model responsible of the `via` relations has a `role` field that should be set when you want to create a user for an organization or an organization for an user. In order to do that, you should create both of the records independently and then associate the records, as we will see in the next paragraph.

#### Add records to many relations

Every time you have existing records, you can use the `add` method of the `has_many` sets to establish new relations.

If we consider back the *doctor-patients* example, where we have an `has_many` relation without the `via` option, the `add` method will change the doctor of a certain patient:

```python
>>> patient = Patient.first()
>>> patient.doctor.name
"Walter Bishop"
>>> doctor = Doctor.get(name="Jekyll")
>>> doctor.patients.add(patient)
<Row {'updated': 1, 'errors': {}}>
```

that will produce the same result of writing:

```python
db(Patient.id == patient.id).validate_and_update(
    doctor=doctor)
```

On `has_many` relations that have the `via` option configured, things are slightly different. In fact, if we consider the *user-membership-organization* example, the `add` method will create a new record on the join table:

```python
>>> org = Organization.first()
>>> user = User.first()
>>> org.users.add(user, role="admin")
<Row {'errors': {}, 'id': 1}>
```

and as you can see, the `add` method accepts the other record as the first parameter, and any additional named parameter for additional fields of the join table, and will perform a validation and an insert on this table.

#### Removing records from many relations

The `remove` method of the `has_many` sets is intended to be the opposite of the `add` one.

In cases of an `has_many` relation without the `via` option, the `remove` method has a different behavior depending on the opposite relation. In fact, if the opposite relation is a `belongs_to` relation, the `remove` method will delete the other record:

```python
>>> doctor = Doctor.get(name="Jekyll")
>>> patient = Patient.get(name="John")
>>> doctor.patients.remove(patient)
1
```

and the returning value is the number of deleted records.

On the contrary, if your opposite relation is a `refers_to` relation, the `remove` record will nullify the reference, keeping the other record in the database (the reference of the other record will be `None` in Emmett and NULL in the database).

When you have `has_many` relations defined with `via` options, the `remove` method will instead remove the record responsible of the relation in the join table. For instance, writing this:

```python
org = Organization.first()
user = User.first()
org.users.remove(user)
```

will delete the join record in the *memberships* table and keep the organization and the users intact and independents.

### Joins and N+1 queries

*Changed in version 1.0*

Quite often in your application you will need to select multiple records and then access to their relations. Let's say for example, that you have a blog application with users and posts:

```python
class User(Model):
    name = Field()
    has_many('posts')

class Post(Model):
    belongs_to('user')
    title = Field()
```

and you want to print out all the post titles for all the users. You might be tempted to write something like this:

```python
users = User.all().select()
for user in users:
    print("%s posts:" % user.name)
    for post in user.posts():
        print("  %s" % post.name)
```

but this will make Emmett to perform a select operation to your database every time you call `user.posts()`, causing the problem called "N+1 queries".

#### The join method

To avoid the problem we just exposed, Emmett provides a `join` method over the sets. In fact, if you rewrite the example above like this: 

```python
users = User.all().join('posts').select()
for user in users:
    print("%s posts:" % user.name)
    for post in user.posts():
        print("  %s" % post.name)
```

Emmett will perform a *JOIN* operation on the database and the posts will be directly available on the users without any additional selects.

As you probably understood, the `join` method accepts one or more relations to join in the select operation, and you can just write down these relations with their names as strings.

The `join` method will load any kind of relation, independently if they are `belongs_to`, `refers_to`, `has_one` and `has_many` (also the ones with `via` options), so you can select, for example, the post matching a certain name and load also their authors:

```python
db(
    Post.name.contains("tutorial")
).join('user').select()
```

or load the organizations of the users from the example in the previous sections that are a many-via relations:

```python
User.all().join('organizations').select()
```

> **Note:** when you perform joins of relations, the `type` of the related object inside the selected rows is just the same of the normal select operation.

Note that, the `join` method will returns only those rows matching the joins, so, going back to the posts example, when you do:

```python
User.all().join('posts').select()
```

Emmett won't return users that don't have posts. When you need this behavior, you should use the `including` option of the `select` method instead.

#### Select with including option

The `including` option of the `select` method will reflect in a *LEFT OUTER JOIN* operation on your database, and is useful when you want to select entities and their relations even if these are empty. Writing:

```python
User.all().select(including='posts')
```

will return all the users in your database with their posts, if any, with the same types of the `join` method. The `including` option accepts a string parameter or a list of strings, which have to be, like on the `join` method, the names of the relations you want to load.

> **Note:** when you includes relations, the `type` of the related object inside the selected rows is just the same of the normal select operation.

#### Manual joins

If you need that, you can use also a lower level method to perform joins with Emmett:

```python
db(Post.user == User.id).select(db.User.ALL, db.Post.ALL)
```

This code will return the join rows of users and their posts, as we saw with the `join` method. The main difference from the above is that the rows returned with this method won't have related posts as nested rows of users, but instead every row contained in the returned `Rows` object will have a `users` attribute and a `posts` attribute containing the two selected rows from their tables. As a direct consequence, if you have users with more than one post, they will be repeated in rows for every post matching the query.

If this structure better suits your needs for your application development, you might use this method to perform joins instead of the `join` method.
