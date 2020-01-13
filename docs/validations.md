Validations
===========

*New in version 0.4*

Validations are used to ensure that only valid data is parsed and/or stored from
forms and user interactions. For example, it may be important to your
application that every user provides a valid email address, or that an
input field contains a valid number, or that a date has the right format.

There is one validation mechanism in Emmett, suitable whether you're using independent
forms or one from a model. It is built to be easy to use, providing built-in helpers
for common needs, and it also allows you to create your own validation methods
if you need more customation.

Validations cannot be bypassed by end users, and are triggered every time a form is
submitted or when you invoke the `Model` methods `validate` and `create`. But
how you define validations for your entities and forms?

The quick way is to use the `validation` parameter of the `Field` class, which
is used by the `Model` and `Form` classes in Emmett. It accepts a `dict` of
instructions:

```python
# ensure the input is a valid email address
Field(validation={'is': 'email'})
```

And when you're using models, it may be more comfortable to group all the field
validations into a single place, with the `validation` attribute of your `Model`
class:

```python
class Person(Model):
    email = Field()
    website = Field()

    validation = {
        'email': {'is': 'email'},
        'website': {'is': 'url', 'message': 'You must insert a valid url'}
    }
```

Whether you use `Field`'s validation parameter or `Model`'s validation attribute,
the result will be the same.

As you've seen with the *website* field in the example, you can always customize
the validation's error message.

Now, let's see the available built-in validation helpers.

Presence and absence of input
-----------------------------

Emmett provides two helpers when you just need to ensure that a specific field is
not blank or is blank: `'presence'` and `'empty'`.

In fact, when you need to ensure a field is not empty, you can use the
`'presence'` validator:

```python
myfield = Field(validation={'presence': True})
```

In this case, the `presence` validator ensures that the contents of the input
are valid, so a blank input or some white spaces won't pass the validation.

On the other hand, if you need to ensure your field is blank, you can use the
`'emtpy'` validator:

```python
myfield = Field(validation={'empty': True})
```

If you prefer, you may also write:

```python
myfield = Field(validation={'empty': False})
```

which will be the same as `{'presence': True}`, but remember that writing
`{'presence': False}` doesn't mean `{'empty': True}`.

When you're applying the `'presence'` validator to a *reference* field, the
behavior of the validator will be quite different: it will also check that
the given value exists in the referenced table.

Type of input
-------------

In the first examples, we ensured that the input values were emails or URLs.
This is done with the `'is'` validator, and can be used to ensure several types
for your fields:

| *is* values | validation details |
| --- | --- |
| int | ensure `int` type |
| float | ensure `float` type |
| decimal | ensure `decimal.Decimal` type |
| date | ensure `datetime.date` type |
| time | ensure `datetime.time` type |
| datetime | ensure `datetime.datetime` type |
| email | ensure is a valid email address |
| url | ensure is a valid URL |
| ip | ensure is a valid IP |
| json | ensure is valid JSON content |
| image | (for *upload* fields) ensure the input is an image file |
| list:*type* | ensure is a list with elements of given *type* (available with all `'is'` values except for *image* and *json*) |

Since many options of the `'is'` validator ensure a specific Python type on
validation, the input values will also be converted to the right type: an input
which should be `'int'` that comes as a string from the form will be converted
to an `int` object for all the other validators, or for your post-validation code.

> **Note:** the datetime validator returns a [pendulum Datetime](https://pendulum.eustace.io/) object, which is a subclass of the standard Python datetime class.

Here are some examples of `'is'` validation helper:

```
price = Field.float(validation={'is': {'float': {'dot': ','}}})
emails = Field.string_list(validation={'is': {'list:email': {'splitter': ';'}}})
urls = Field.string_list(validation={'is': 'list:url'})
```

Note that, since the `'is'` validator ensures the input is valid for the given
type, it's like an implicit `{'presence': True}`, so you don't need to add
`'presence'` when you use it.

> – Dude, what if I want to allow the field to be blank, and when it's not, allow a specific type?   
> – *you can use the `'allow'` validator, described next*

Also remember that `Field` comes with a default `'is'` validator (unless you
disabled it with the `auto_validation` parameter) depending on its type. An
*int* field will have an `{'is': 'int'}` validator, since Emmett guess you want
the input to be valid. We described that in the [Field chapter](./orm#fields).

Specific values allowance
-------------------------

In the previous section, we saw that the `'is'` validator is also
a `{'presence': True}` validation, implicitly. Now, what if we need to allow an
*int* field to be blank, so that when is filled it will be converted to an
integer and also allow it to pass the validation if it is blank?

We can use the `'allow'` validator:

```python
maybe_number = Field.int(validation={'allow': 'blank'})
# or
maybe_number = Field.int(validation={'allow': 'empty'})
```

In this specific case, we are telling the validator to accept blank/empty
inputs, but you can also pass specific values to it:

```python
maybe_number = Field.int(validation={'allow': None})
maybe_number = Field.int(validation={'allow': 'nope'})
```

Practically speaking, the `'allow'` validator *allows* you to add an exception
rule to your validation, and can be applied to any of the validators
described in this page.

Length of input
---------------

You will need to set some length requirements for your fields. Most commonly,
you will do this for a password field, which you may want to be greater than
a certain a length and/or not too long:

```python
password = Field.password(validation={'len': {'gt': 5, 'lt': 25}})
```

As you can see, the `'len'` validator is just the easier way to do that. It
accepts different arguments, depending on what you need:

| parameter | value expected | example |
| --- | --- | --- |
| gt | `int` | `{'len': {'gt': 5}}` |
| lt | `int` | `{'len': {'lt': 25}}` |
| gte | `int` | `{'len': {'gte': 6}}` |
| lte | `int` | `{'len': {'lte': 24}}` |
| range | `tuple` of `int` | `{'len': {'range': (6, 25)}}` |

Note that the `range` parameter behaves like the Python builtin `range()`,
including the lower value and excluding the upper one, so the above line is the
same of `{'len': {'gte': 6, 'lt': 25}}`.

Value inclusion
---------------

To ensure the value is inside a specific set, you can use the `'in'` validator:

```python
myfield = Field(validation={'in': ['a', 'b']})
```

If you have an *int* field, you can also use the convenient `'range'` option:

```python
number = Field.int(validation={'in': {'range': (1, 10)}})
```

The `'in'` validator also accepts some specific options, in particular:

| parameter | description |
| --- | --- |
| labels | a `list` of values to display on form's dropdown menu |
| multiple | allow user to select multiple values |

When you want to use these options with a set, you may use the `'set'` notation:

```python
number = Field(
    'int',
    validation={'in': {'set': [0, 1], 'labels': ['zero', 'one']}}
)
```

### Inclusion in database sets

*Added in version 0.8*

The `'in'` validator accepts also a database set as boundary, thanks to the 'dbset' notation. 

For example, if you have a reference in your model and you want its values to be in a specific subset of the database rather than just checking their existence in the referred table, you can write:

```python
belongs_to('article')

validation = {
    'article': {
        'in': {
            'dbset': lambda db: db.where(db.Article.id > 5)
        }
    }
}
```

As you can see, the value for `'dbset'` should be a function, accept the database as a parameter and return a database set.

With the `'dbset'` notation, the `'in'` validator accepts also some additional options, that will be used in rendering forms for your entity, in particular:

| parameter | description |
| --- | --- |
| orderby | define a sorting rule for dropdowns |
| label\_field | use a field of the reference model to render dropdowns |

For example, if you have a `rating` field in your `Article` model, you can order the results by this column, and maybe you also want to use the titles of each article to render the choices:

```python
validation = {
    'doctor': {
        'in': {
            'dbset': lambda db: db(db.Doctor.id > 5), 
            'orderby': lambda doctor: ~doctor.rating,
            'label_field': 'title'
        }
    }
}
```

Remember that the `orderby` clause should be a function and, accept the referred model as a parameter and return a sorting rule, while the `label_field` one should be a string identifying the name of the field that you want to use to format results.


Numeric boundaries
------------------

When you need to ensure some numeric values on *int* fields, you may prefer
a different approach, using the same notation as `'len'`:

```python
num_a = Field.int(validation={'gt': 0})
num_b = Field.int(validation={'lt': 12})
num_c = Field.int(validation={'gte': 1, 'lte': 10})
```

Validate only a specific value
------------------------------

Sometimes you need to validate only a specific value for a field. Emmett provides
the `'equals'` validator to help you:

```python
accept_terms = Field(validation={'equals': 'yes'})
```

Basically, the `'equals'` validator performs a `==` check between the input
value and the one given.

Match input
-----------

When you want to validate against a regex *expression*, you can use the
`'match'` validation helper. For example, let say you want to validate a ZIP
code:

```python
zip = Field(validation={'match': r'^\d{5}(-\d{4})?$'})
```

or a phone number:

```python
phone = Field(validation={'match': r'^\+?1?((-)\d{3}-?|\(\d{3}\))\d{3}-?\d{4}$'})
```

`'match'` also accepts some parameters:   

- the `search` parameter (default to `False`), which will use the regex method `search` instead of `match`
- the `strict` parameter (default to `False`), which will only match the beginning of the string.

In this example, due to the `strict` parameter, the value for the first field
will pass validation and the second won't:

```python
normal = Field(validation={'match': 'ab'})
strict = Field(validation={'match': {'expression': 'ab', 'strict': True}})
Model.validate({'normal': 'abc', 'strict': 'abc'})
```

Exclusion
---------

When you need to do an *exclusion* operation during the validation process, you
can use the `'not'` validation helper. Let's say that you want the value to be
different from a certain value:

```python
myfield = Field(validation={'not': {'equals': 'somevalue'}})
```

or you want to exclude a set of values:

```python
color = Field(validation={'not': {'in': ['white', 'black']}})
```

Basically, the `'not'` validator takes another validation as argument and check
the opposite result.

Any
---

Sometimes you need to validate an input value that responds to *any* of the
given validations. Under this circumstances, you can use the `'any'` validation
helper:

```python
myfield = Field(validation={'any': {'is': 'email', 'in': ['foo', 'bar']}})
```

Obviously, the `'any'` validator takes other validations as arguments and
validates if any of the child validations pass.

Transformations
---------------

Emmett provides several validation helpers that let you transform the input value
of the field on validation. For example, you may want your *string* field to
always being lowercase, or you need your *password* field to be encrypted.

Here is the complete list of *transformation* helpers built into Emmett:

### lower

The `'lower'` helper turns your string to lowercase:

```python
low = Field(validation={'lower': True})
```

### upper

The `'upper'` helper turns your string to uppercase:

```python
up = Field(validation={'upper': True})
```

### clean

The `'clean'` helper removes any special characters from your string:

```python
clean = Field(validation={'clean': True})
```

### urlify

The `'urlify'` helper allows you to create URL valid strings (so that, for
example, you can use them for routing purposes): 

```python
urldata = Field(validation={'urlify': True})
```

This helper also accepts the `underscore` parameter (default set as `False`)
that you can use if you want underscores to be kept in the string:

```python
urldata = Field(validation={'urlify': {'underscore': True}})
```

### crypt

The `'crypt'` helper becomes handy when you want to encrypt the contents of the
field. The easiest way to use it is just to enable it:

```python
password = Field(validation={'crypt': True})
```

which will encrypt the contents using the *sha512* algorithm.

If you want to use a different algorithm, you can choose between *md5*, *sha1*,
*sha224*, *sha256*, *sha384*, *sha512* and just write:

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

Of course, the builtin validation helpers cannot be enough in many particular
cases. When you need to implement your own validation logic on a specific field,
you can create your own `Validator` subclass, and pass an instance of it to the
`validation` parameter:

```python
from emmett.validators import Validator

class MyValidator(Validator):
    message = "Invalid value"

    def __call__(self, value):
        if value == "notallowed":
            return value, self.message
        return value, None

myfield = Field(validation=MyValidator())
```

and if you need to use multiple `Validator` classes, you can pass a list of
instances to `validation`:

```python
myfield = Field(validation=[MyValidator1(), MyValidator2()])
```

When you write down your own `Validator`, you just have to remember that the
validation logic has to be inside the `__call__` method. That should return the
value and the error message if validation has failed, or the value and `None` if
everything was OK.

The `Validator` class also has a `formatter` function, which allows you to
format the value to display in the form for particular cases:

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


### Combining custom validators with standard ones

*New in version 1.0*

You can also use custom validators we just saw in combination with the standard ones provided by Emmett. Just use the `custom` helper:

```python
class OddValidator(Validator):
    message = "value has to be odd"

    def __call__(self, value):
        if value % 2:
            return value, self.message
        return value, None

mynumber = Field.int(validation={
    'gte': 0, 'lt': 20, 'custom': OddValidator()})
```

> **Note:** you can also pass a list of custom validators to the `custom` helper.
