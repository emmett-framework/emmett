Validations
===========

*New in version 0.4*

Validations are used to ensure that only valid data is parsed and/or stored from forms and user interactions. For example, it may be important to your application to ensure that every user provides a valid email address, or that an input field contains a valid number, or a date with the right format.

The validation mechanism in weppy is the same both if you're using independent forms or model's ones, and is built to be easy to use, provides built-in helpers for common needs, but also allows you to create your own validation methods as well.

Validations cannot be bypassed by end users, and happens every time a form is submitted, or when you invoke the `Model` methods `validate` and `create`. But how you define validations for your entities and forms?

The quite immediate way is to use the `validation` parameter of the `Field` class which is used both by `Model` and `Form` classes in weppy, and that accepts a `dict` of instructions:

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
        'website': {'is': 'url', 'message': 'You must insert a valid url'}
    }
```

The result of using `Field`'s validation parameter or `Model`'s validation attribute will be the same: is basically a matter of personal coding style.

As you've seen with the *website* field in the example, you can always customize the error message resulting from the validation.

Now, let's see the available built-in validation helpers.

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
| list:*type* | ensure is a list with elements of given *type* (available with all `'is'` values except for *image* and *json*) |

Since many options of the `'is'` validator ensure a specific python type, on validation the input values will also be converted to the right type: an input which should be `'int'` and that it comes as a string from the form, will be converted as an `int` object for all the other validators, or for your post-validation code.

Here are some examples of `'is'` validation helper:

```
price = Field('float', validation={'is': {'float': {'dot': ','}}})
emails = Field('list:string', validation={'is': {'list:email': {'splitter': ';'}}})
urls = Field('list:string', validation={'is': 'list:url'})
```

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
| --- | --- | --- |
| gt | `int` | `{'len': {'gt': 5}}` |
| lt | `int` | `{'len': {'lt': 25}}` |
| gte | `int` | `{'len': {'gte': 6}}` |
| lte | `int` | `{'len': {'lte': 24}}` |
| range | `tuple` of `int` | `{'len': {'range': (6, 25)}}` |

Note that the `range` parameter behaves like the python builtin `range()`, including the lower value and excluding the upper one, so the above line is the same of `{'len': {'gte': 6, 'lt': 25}}`.

Value inclusion
---------------

To ensure the value is inside a specific set, you can use the `'in'` validator:

```python
myfield = Field(validation={'in': ['a', 'b']})
```

and if you have an *int* field, you can also use the convenient `'range'` option:

```python
number = Field('int', validation={'in': {'range': (1, 10)}})
```

The `'in'` validator also accepts some specific options, in particular:

| parameter | description |
| --- | --- |
| labels | a `list` of values to display on form's dropdown |
| multiple | allow user to select multiple values |

When you want to use these options with a set, you may use the `'set'` notation:

```python
number = Field(
    'int',
    validation={'in': {'set': [0, 1], 'labels': ['zero', 'one']}}
)
```

Numeric boundaries
------------------

When you need to ensure some numeric values on *int* fields, you may find useful a different approach from `{'in': {'range': (1, 10)}}`, using the same notation of `'len'`:

```python
num_a = Field('int', validation={'gt': 0})
num_b = Field('int', validation={'lt': 12})
num_c = Field('int', validation={'gte': 1, 'lte': 10})
```

Validate only a specific value
------------------------------

Sometimes you need to validate only a specific value for a field. weppy provides the `'equals'` validator to help you:

```python
accept_terms = Field(validation={'equals': 'yes'})
```

Basically the `'equals'` validator perform a `==` check between the input value and the one given.

Match input
-----------

When you want to validate a match of a regex *expression*, you can use the `'match'` validation helper. For example, let say you want to validate a ZIP code:

```python
zip = Field(validation={'match': '^\d{5}(-\d{4})?$'})
```

or a phone number:

```python
phone = Field(validation={'match': '^1?((-)\d{3}-?|\(\d{3}\))\d{3}-?\d{4}$'})
```

`'match'` also accepts some parameters:   

- the `search` parameter (default to `False`), which will use the regex method `search` instead of the `match` one
- the `strict` parameter (default to `False`), which will only matches the beginning of the string.

In this example, due to the `strict` parameter, the value for the first field will pass validation and the second won't:

```python
normal = Field(validation={'match': 'ab'})
strict = Field(validation={'match': {'expression': 'ab', 'strict': True}})
Model.validate({'normal': 'abc', 'strict': 'abc'})
```

Exclusion
---------

When you need to do an *exclusion* operation under validation process, you can use the `'not'` validation helper. Let's say that you want the value to be different from a certain value:

```python
myfield = Field(validation={'not': {'equals': 'somevalue'}})
```

or you want to exclude a set of values:

```python
color = Field(validation={'not': {'in': ['white', 'black']}})
```

Basically the `'not'` validator takes another validation as argument and check the opposite result.

Any
---

Sometimes you need to validate an input value that respond to *any* of the given validations. Under this circumstances, you can use the `'any'` validation helper:

```python
myfield = Field(validation={'any': {'is': 'email', 'in': ['foo', 'bar']}})
```

Obviously the `'any'` validator takes other validations as argument and validate the value if any of the children validations pass.

Transformations
---------------

weppy provides several validation helpers that let you transform the input value of the field on validation. For example, you may want your *string* field to always being lowercase, or you need your *password* field to be crypted.

Here is the complete list of *transformation* helpers available in weppy builtins.

### lower

The `'lower'` helper turns your string to lowercase:

```python
low = Field(validation={'lower': True})
```

### upper

The `'upper'` helper is the opposite of the `'lower'` one, and will turn your string to uppercase:

```python
up = Field(validation={'upper': True})
```

### clean

The `'clean'` helper removes any special character from your string:

```python
clean = Field(validation={'clean': True})
```

### urlify

The `'urlify'` helper allows you to create url valid strings (so that, for example, you can use them for routing purposes): 

```python
urldata = Field(validation={'urlify': True})
```

This helper also accepts the `underscore` parameter (default set as `False`) that you can use if you want underscores to be kept in the string:

```python
urldata = Field(validation={'urlify': {'underscore': True}})
```

### crypt

The `'crypt'` helper becomes handy when you want to crypt the contents of the field. The easiest way to use it is just to enable it:

```python
password = Field(validation={'crypt': True})
```

which will crypt the contents using *sha512* algorithm.

If you just want to use a different algorithm, choosing between *md5*, *sha1*, *sha224*, *sha256*, *sha384*, *sha512*, you can just write:

```python
password = Field(validation={'crypt': 'md5'})
```

But `'crypt'` also accepts two more parameters:   

- the `key` parameter, which allows you to specify your own key to use with the algorithm
- the `salt` parameter, which allows you to specify a salt to hash the password with.

```python
password = Field(
    validation={'crypt': {'algorithm': 'md5', 'key': 'MyVerySecretKey'}}
)
```

Custom validation
-----------------

Of course the builtin validation helpers cannot be enough in many particular cases. When you need to implement your own validation logic on a specific field, you can create your own `Validator` subclass, and pass an instance of it to the `validation` parameter:

```python
from weppy.validators import Validator

class MyValidator(Validator):
    message = "Invalid value"

    def __call__(self, value):
        if value == "notallowed":
            return value, self.message
        return value, None

myfield = Field(validation=MyValidator())
```

and if you need to use multiple `Validator` classes, you can pass to `validation` a list of instances:

```python
myfield = Field(validation=[MyValidator1(), MyValidator2()])
```

When you write down your own `Validator` you just have to remember that the validation logic has to be inside the `__call__` method, and that should return the value and the error message if validation has failed or the value and `None` if everything was ok.

`Validator` class also have a `formatter` function, that allows you to format the value to display in the form for particular cases:

```python
class FloatValidator(Validator):
    def formatter(self, value):
        #: shows only 2 values after the separator
        if value is None:
            return None
        val = str(value)
        if '.' not in val:
            val += '.00'
        else:
            val += '0' * (2 - len(val.split('.')[1]))
        return val
```
