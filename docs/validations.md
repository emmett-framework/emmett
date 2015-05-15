Validations
===========

Validations are used to ensure that only valid data is parsed and/or stored from forms and user interactions. For example, it may be important to your application to ensure that every user provides a valid email address, or that an input field contains a valid number, or a date with the right format.

The validation mechanism in weppy is the same both if you're using independent forms or model's ones, and is built to be easy to use, provides built-in helpers for common needs, but also allows you to create your own validation methods as well.

Validations cannot be bypassed by end users, and happens every time a form is submitted, or when you invoke the `Model` methods `validate` and `create`. But how you define validations for your entities and forms?

The quite immediate way is to use the `validation` parameter of the `Field` class which is used both by `Model` and `Form` classes in weppy:

```python
# ensure the input is a valid email address
Field(validation={'is': 'email'})
```

And when you're using models, you may find yourself more comfortable in grouping all fields validations into a single place, with the `validation` attribute of your `Model` class:

```python
class Person(Model):
    email = Field()
    website = Field()

    validation = {
        'email': {'is': 'email'},
        'website': {'is': 'url'}
    }
```

The result of using `Field`'s validation parameter or `Model`'s validation attribute will be the same: is basically a matter of personal coding style.

So, what are the built-in validation helpers? Let's see them specifically.

Presence and absence of input
-----------------------------

weppy provides two helpers when you just need to ensure that a specific field is not blank or is blank: `'presence'` and `'empty'`.

In fact, when you need to ensure a field is not empty, you can use the `'presence'` validator:

```python
myfield = Field(validation={'presence': True})
```

In this case, the `presence` validator ensure that the contents of the input are a valid, so a blank input or some white spaces won't pass the validation.

On the contrary, if you need to ensure your field is blank, you can use the `'emtpy'` validator:

```python
myfield = Field(validation={'empty': True})
```

If you prefer, you may also write:

```python
myfield = Field(validation={'empty': False})
```

which will be the same of `{'presence': True}`, but remember that writing `{'presence': False}` doesn't mean `{'empty': True}`.

When you're applying the `'presence'` validator to a *reference* field, the behavior of the validator will be quite different, since it will also check that the given value is existent in the referenced table.

Type of input
-------------

In the first examples, we ensured that the input values were emails or urls. This is done with the `'is'` validator, and can be used to ensure several types for your fields:

| *is* values | validation details |
| --- | --- |
| int | ensure `int` type |
| float | ensure `float` type |
| decimal | ensure `decimal.Decimal` type |
| date | ensure `datetime.date` type |
| time | ensure `datetime.time` type |
| datetime | ensure `datetime.datetime` type |
| email | ensure is a valid email address |
| url | ensure is a valid url |
| ip | ensure is a valid ip |
| json | ensure is valid json content |
| image | (for *upload* fields) ensure the input is an image file |

Since many options of the `'is'` validators ensure a specific python type, on validation the input values will also be converted to the right type: an input which should be `'int'` and that it comes as a string from the form, will be converted as an `int` object for all the other validators, or for your post-validation code.

Note that, since `'is'` validator ensure the input is valid for the given type, it's like an implicit `{'presence': True}`, so you don't need to add `'presence'` when you use it.

> – Dude what if I want the field can be blank, and when it's not, of a specific type?   
> – *you can use the `'allow'` validator described next*

Also remember that `Field` comes with a default `'is'` validator (unless you disabled it with the `auto_validation` parameter) depending on its type (so an *int* field will have an `{'is': 'int'}` validator, since weppy guess you want the input to be valid) as we described in the [specific chapter](./dal#fields).

Specific values allowance
-------------------------

In the previous paragraph we saw that `'is'` validator implicitly consist also in a `{'presence': True}` validation. Now, what if we need to allow an *int* field to be blank, so that when is filled it will be converted to an integer and when it's not, it will pass the validation anyway?

We can use the `'allow'` validator:

```python
maybe_number = Field('int', validation={'allow': 'blank'})
# or
maybe_number = Field('int', validation={'allow': 'empty'})
```

In this specific case we are telling the validator to accept blank/empty inputs, but you can also pass specific values to it:

```python
maybe_number = Field('int', validation={'allow': None})
maybe_number = Field('int', validation={'allow': 'nope'})
```

Practically speaking, `'allow'` validator *allows* you to add an exception rule to your validation, and can be applied to anyone of the validators described in this page.

Length of input
---------------

You will need to set some boundaries on the length of your fields. A very common scenario will be a password field, that you want to be greater than a certain a length and/or not too long:

```python
password = Field('password', validation={'len': {'gt': 5, 'lt': 25}})
```

As you can see, the `'len'` validator is just the easier way to do that. It accepts different arguments, depending on what you need:

| parameter | value expected | example |
| --- | --- |
| gt | `int` | `{'len': {'gt': 5}}` |
| lt | `int` | `{'len': {'lt': 25}}` |
| gte | `int` | `{'len': {'gte': 6}}` |
| lte | `int` | `{'len': {'lte': 24}}` |
| range | `tuple` of `int` | `{'len': {'range': (6, 25)}}` |

Note that the `range` parameter behaves like the python builtin `range()`, including the lower value and excluding the upper one, so the above line is the same of `{'len': {'gte': 6, 'lt': 25}}`.

Value inclusion
---------------

Numeric boundaries
------------------

Validate only a specific value
------------------------------

Match input
-----------

Transformations
---------------

Exclusion
---------

Custom validation
-----------------
