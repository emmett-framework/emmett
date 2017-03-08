The Authorization System
========================

Since authorizations and authentications are a very important part of almost every application, weppy includes an useful module to deal with them. With a few lines of code, you will be able to create any required database tables and generate forms for access control in your application.

So, how do you use it? Let's find out with an example:

```python
from weppy import App
from weppy.orm import Database
from weppy.tools.auth import Auth, AuthUser
from weppy.sessions import SessionCookieManager

app = App(__name__)
app.config.db.uri = "sqlite://storage.sqlite"
app.config.auth.hmac_key = "mysupersecretkey"

class User(AuthUser):
    pass

db = Database(app)
auth = Auth(app, db, user_model=User)

app.pipeline = [
    SessionCookieManager('myverysecretkey'),
    db.pipe,
    auth.pipe
]

auth_routes = auth.module(__name__)
```

That's it.

Write a template page for the account function, including the returned form,
and open [http://127.0.0.1:8000/auth/login](http://127.0.0.1:8000/auth/login)
in your browser. weppy should show you a login page with the appropriate form.

> **Note:** weppy's `Auth` module requires session handling and a Database instance activated on your application in order to work properly.

As you've figured out, the `auth_routes` module will be responsible for
your app's authorization flow. With the default settings, the `Auth` module 
of weppy exposes the following:

* http://.../{baseurl}/login
* http://.../{baseurl}/logout
* http://.../{baseurl}/registration
* http://.../{baseurl}/profile
* http://.../{baseurl}/email_verification
* http://.../{baseurl}/password_retrieval
* http://.../{baseurl}/password\_reset/{reset\_key}
* http://.../{baseurl}/password_change

and it creates all the necessary database tables, from users to groups and memberships.

You can obviously change the routing URL prefix as any other application module:

```python
auth_routes = auth.module(__name__, url_prefix='account')
```

### Disable specific routes
You may want to disable some actions exposed by the authorization module.
Let's say you don't want the `password_retrieval` functionality. To do that,
just edit your application configuration:

```python
app.config.auth.disabled_routes = ["password_retrieval"]
```

### Add custom routes
You can also define custom actions to be routed by the auth module. Let's say 
you want to route a method for the facebook authentication on the */account/facebook* path:

```python
@auth_routes.route("/facebook")
def facebook_auth():
    # some code
```


Access control with "requires"
------------------------------

*Changed in 1.0*

One of the strengths of the authorization module is that it is simple to
introduce access controls to your application. Let's say that you need to allow
access to a specific zone to only users who are logged in. With weppy,
you can do that with one line of code:

```python
from weppy.tools import requires

@app.route()
@requires(auth.is_logged, url('unauthorized_page'))
def my_protected_page():
    #some code
```

As you probably figured out, the `requires` helper will determine if the condition 
in the first parameter passed as and if that is not so, weppy will redirect 
the client to the URL in the second parameter.

You can also pass a function to be invoked as with the second parameter, for example:

```python
def not_auth():
    abort(403)

@app.route()
@requires(lambda: auth.has_membership('admins'), not_auth)
def admin():
    # code
```

returns an HTTP 403 error.

> **Note:** when you need to evaluate the condition during the request, 
you should use a `lambda` function if the first argument passed to `requires`
is not a callable.

Sometimes you may need to return specific contents on missing authorization. 
In that case, you can write:

```python
from weppy.tools import service

def not_authorized():
    return dict(error="Not authorized")

@app.route()
@requires(auth.is_logged_in, not_authorized)
@service.json
def protected():
    return dict(data="Some data here")
```

so the client will also receive a JSON object on an authorization error.

> – OK, dude. What if I want to protect an entire application module with 
access control?

You can use the `RequirePipe` instead of decorating any function 
of your module:

```python
from weppy import AppModule
from weppy.pipeline import RequirePipe

mymodule = app.module(__name__, "mymodule")
mymodule.pipeline = [RequirePipe(some_condition, otherwise)]
```

If you go this route, just remember to not add access control to your 
exposed function, otherwise your user won't be able to login.

Authorization models
--------------------

*Changed in version 1.0*

The `Auth` module defines five models (and the five related database tables)
under default behavior:

- `AuthUser`
- `AuthGroup`
- `AuthMembership`
- `AuthPermission`
- `AuthEvent`

Now, you can customize the models by creating subclasses, and the thing you'll want to model most often is probably going to be a user. As we saw from the previous example, your base class will be `AuthUser` and from there you can add your fields, like an avatar.

You could define your `User` model like so:

```python
from weppy.orm import Field
from weppy.tools.auth import AuthUser

class User(AuthUser):
    avatar = Field("upload", uploadfolder="uploads")
    
    form_profile_rw = {
        "avatar": True
    }
```

and pass it to the `Auth` instance:

```python
from weppy.tools import Auth
auth = Auth(app, db, user_model=User)
```

As you can see, defining your user model by subclassing `AuthUser` is essentially 
the same as subclassing `Model`, but there are some differences. Firstly, 
the fields you define will be the additional fields you will want to add to
the user table. Secondly, you'll use `form_profile_rw` and `form_registration_rw`, 
instead of the `form_rw` attribute, to treat the field differently for accesses 
during user registration and during user edits after registration. The default
visibility is set to `False` for any extra fields you define, so the above example
allows the client to upload an avatar for their account only with the profile function,
not during the registration.

The default fields included in the `AuthUser` model are:

- email
- password
- first_name
- last_name

plus some other columns need by the system and hidden to the users.

If you don't want to have the `first_name` and `last_name` fields inside your
user model (they are set to be not-null), you can subclass the `AuthUserBasic`
model instead, available under `weppy.tools.auth.models`, which doesn't include them.

Before seeing how to customize the remaining auth models, let's see which
relations are available as default.

### Auth relations

The default `Auth` configuration gives you the ability to use these `has_many`
relations on the `AuthUser` model (and any model subclassing it):

```python
user = db.AuthUser(id=1)
# referring membership records
user.auth_memberships()
# referring group records
user.auth_groups()
# referring permission records
user.auth_permissions()
# referring event records
user.auth_events()
```

The `AuthGroup` model has these `has_many` relations:

```python
group = db.AuthGroup(id=1)
# referring user records
group.users()
# referring permission records
group.auth_permissions()
```

Consequentially, `AuthMembership`, `AuthPermission` and `AuthEvent` have the
inverse `belongs_to` relations:

```python
membership = db.AuthMembership(id=1)
# referred user record
membership.user
# referred group record
membership.auth_group

permission = db.AuthPermission(id=1)
# referred group record
permission.auth_group

event = db.AuthEvent(id=1)
# referred user record
event.user
```

### Customizing auth models

*section in development*

Users management
---------------

Thanks to the models and relations defined by the `Auth` module, you can manage
the users in your application easily. Let's say you want to add a **group** of
administrators:

```python
admins = auth.add_group('administrators')
```

then you can add users to the administrators' group easily:

```python
admin = db.User(id=42)
# 1st way:
auth.add_membership(admins, admin)
# 2nd way:
auth.add_membership('administrators', admin)
# 3rd way:
admins.users.add(admin)
# 4th way:
admin.auth_groups.add(admins)
```

Once you have added groups and memberships, you can use the `has_membership` helper
of the `Auth` model that we saw previously, in the *requires* paragraph:

```python
# on the logged user:
auth.has_membership('administrators')
# specifying a user:
auth.has_membership('administrators', user)
```

and you can obviously get all the groups a user is a member of by using relation:

```python
user.auth_groups()
```

Nonetheless, weppy's `Auth` module also have a finer management for users,
considering permissions:

```python
auth.add_permission(admins, 'ban_users')
```

As you saw in the example, this allows you to bind specific permissions to groups,
and then checks for them both on groups and users:

```python
# on the logged user:
auth.has_permission('ban_users')
# on specific user:
auth.has_permission('ban_users', user=admin)
# on specific group:
auth.has_permission('ban_users', group=admins)
```

weppy's `Auth` permissions also support more details, like a model name and a record:

```python
maintenance = db.Preference(name='maintenance').first()
auth.add_permission(admins, 'write', 'Preference', maintenance.id)
# then you will check
auth.has_permission('write', 'Preference', maintenance.id)
```

### Blocking users

*New in version 0.6*

Sometimes you need to lock user operations on your application. The auth module
has 2 different *locking* statuses for this:

- **disabled:** the user won't be able to perform the normal auth operation until a reset of their password
- **blocked:** the user won't be able to perform any auth operation (they are banned)

You can change an user status in two different ways. The first is directly with
your `Auth` instance:

```python
auth.disable_user(user)
auth.block_user(user)
auth.allow_user(user)
```

where the only accepted parameters are an user row (including the id) or just the id of the user involved.

You can also change the user status directly on a user you've selected from the database:

```python
user = User.first()
user.disable()
user.block()
user.allow()
```

The allow methods will simply reset any blocking status on the users.

Auth module configuration
-------------------------

*section in development*

Additional login methods
------------------------

*section in development*
