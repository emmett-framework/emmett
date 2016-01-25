The Authorization System
========================

weppy includes an useful authorization system, based on the once available on *web2py*, which automatically creates required database tables, and generate forms to add access control in your application writing just a few lines.

So how do you use it? Let's find out with an example:

```python
from weppy import App, DAL
from weppy.tools import Auth
from weppy.sessions import SessionCookieManager

app = App(__name__)
app.config.db.uri = "sqlite://storage.sqlite"

db = DAL(app)
auth = Auth(app, db)

app.common_handlers = [
    SessionCookieManager('myverysecretkey'),
    db.handler,
    auth.handler
]

@app.route('/account(/<str:f>)?(/<str:k>)?')
def account(f, k):
    form = auth(f, k)
    return dict(form=form)
```

That's it.
Write a template page for the account function including the returned form and open [http://127.0.0.1:8000/account](http://127.0.0.1:8000/account) in your browser. weppy should redirect you to the login page and showing you the relative form.

> **Note:** weppy's auth module requires session handling and a DAL instance activated on your application to work properly.

As you've figured out, the exposed `account` function will be responsible of the authorization flow in your app.
The `Auth` module of weppy exposes (with the default settings):

* http://.../{baseurl}/login
* http://.../{baseurl}/logout
* http://.../{baseurl}/register
* http://.../{baseurl}/verify_email
* http://.../{baseurl}/retrieve_username
* http://.../{baseurl}/retrieve_password
* http://.../{baseurl}/reset_password
* http://.../{baseurl}/request\_reset\_password
* http://.../{baseurl}/change_password
* http://.../{baseurl}/profile

and it also creates all the database tables needed, from users to groups and memberships ones.

You can obviously change the routing url for the authorization function:

```python
@app.route('/myurl(/<str:f>)?(/<str:k>)?')
def accunt(f, k):
    # code
```

and even change the name of the exposed function, but if you do that, you mast tell to the `Auth` module to use it to generate urls:

```python
auth = Auth(app, db, base_url='mycontrol')

@app.route('/myurl(/<str:f>)?(/<str:k>)?')
def mycontrol(f, k):
    form = auth(f, k)
    return dict(form=form)
```
otherwise the authorization module won't work properly.

###Disable specific actions
You may want to disable some actions exposed by the authorization module, let's say for example you don't want the `retrieve_username` functionality. To do that, just edit your application configuration:

```python
app.config.auth.actions_disabled = ["retrieve_username"]
```

###Add custom actions
You can also define custom actions to be routed by your application. Let's say you want to route "/account/facebook" on your "/account" exposed function:

```python
def myfbfunction():
    # code

auth.register_action("facebook", myfbfunction)
```

and that's it.

Access control with "requires"
------------------------------

One of the advantages of the authorization module is the simple way you can introduce access controls over your application. Let's say, for example, that you need to allow access to a specific zone only to logged users. In weppy you can do that in just a line of code:

```python
from weppy.tools import requires

@app.route()
@requires(auth.is_logged_in, url('unauthorized_page'))
def myprotected_page():
    #some code
```

As you probably figured out, the `requires` helper will check the condition passed as the first parameter and if the request doesn't met the requirement, it will redirect the client on the url passed as second parameter.

You can also pass a function to be invoked as second parameter, for example:

```python
def not_auth():
    abort(403)

@app.route()
@requires(lambda: auth.has_membership('administrator'), not_auth)
def admin():
    # code
```

to return an HTTP 403 error.

> **Note:** when you need to evaluate the condition during the request, if the first argument passed to `requires` is not a callable you should use a `lambda` function.

Sometimes you may need to return specific contents on missing authorization, for example you can write:

```python
from weppy.tools import service

def not_auth():
    return dict(error="Not authorized")

@app.route()
@requires(auth.is_logged_in, not_auth)
@service.json
def protected():
    return dict(data="Some data here")
```

so the client will receive a JSON object also on authorization error.

> – Ok dude. What if I want to protect an entire application module with access control?

You can use the `RequireHandler` instead of decorating any function of your module:

```python
from weppy import AppModule
from weppy.handlers import RequireHandler

mymodule = AppModule(app, "mymodule", __name__)
mymodule.common_handlers = [RequireHandler(some_condition, otherwise)]
```

just remember to not add access control over your authorization exposed function, otherwise your user won't be able to login.

Authorization models
--------------------

*New in version 0.4*

The `Auth` module define five models (and obviously the five related database tables) under default behavior:

- `AuthUser`
- `AuthGroup`
- `AuthMembership`
- `AuthPermission`
- `AuthEvent`

Now, you can customize the models subclassing them, and the first you want to is the one referred to the user, on which you can add your fields, for example an avatar. You will define your `User` model:

```python
from weppy.dal import Field
from weppy.tools.auth import AuthUser


class User(AuthUser):
    avatar = Field("upload", uploadfolder="uploads")
    
    form_profile_rw = {
        "avatar": True
    }
```

and pass it to the Auth instance:

```python
from weppy.tools import Auth
auth = Auth(app, db, usermodel=User)
```

As you can see, defining your user model subclassing `AuthUser` is quite the same as for a `Model`, except that the fields you define will be the additional fields you want to add to the user table, and instead of the `form_rw` attribute you have `form_profile_rw` and `form_registration_rw` to treat separately the field access during user registration and when the user edits its own profile.
As the default visibility is set to `False` for any extra field you have defined, in the above example the client will be able to upload an avatar for its account only with the profile function and not during the registration.

The default fields included in the `AuthUser` model are:

- email
- password
- first_name
- last_name

plus some other columns need by the system and hidden to the users.

If you don't want to have the `first_name` and `last_name` fields inside your user model (they are set to be not-null), you can subclass the `AuthUserBasic` model instead, available under `weppy.tools.auth.models` which doesn't include them.

Before seeing how to customize the remaining auth models, let's see which relations are available as default.

### Auth relations

The default `Auth` configuration gives you the ability to use these `has_many` relations on the `AuthUser` model (and any model subclassing it):

```python
user = db.AuthUser(id=1)
# referring membership records
user.authmemberships()
# referring group records
user.authgroups()
# referring permission records
user.authpermissions()
# referring event records
user.authevents()
```

The `AuthGroup` model has these `has_many` relations:

```python
group = db.AuthGroup(id=1)
# referring user records
group.users()
# referring permission records
group.authpermissions()
```

Consequentially, `AuthMembership`, `AuthPermission` and `AuthEvent` have the inverse `belongs_to` relations:

```python
membership = db.AuthMembership(id=1)
# referred user record
membership.user
# referred group record
membership.authgroup

permission = db.AuthPermission(id=1)
# referred group record
permission.authgroup

event = db.AuthEvent(id=1)
# referred user record
event.user
```

### Customizing auth models

*section in development*

Users management
---------------

Thanks to the models and relations defined by the `Auth` module, you can easily manage the users in your application. Let's say, for example, you want to add a **group** of administrators:

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
admin.authgroups.add(admins)
```

Once you have added groups and memberships, you can use the `has_membership` helper of the `Auth` model (that we've already seen before in the *requires* paragraph):

```python
# on the logged user:
auth.has_membership('administrators')
# specifying a user:
auth.has_membership('administrator', user)
```

and you can obviously get all the groups user has membership with using relation:

```python
user.authgroups()
```

But weppy's `Auth` module also have a finer management for users, considering permissions:

```python
auth.add_permission(admins, 'ban_users')
```

As you got from the example, this allows you to bind specific permissions to groups, and then checks for them both on groups and users:

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
auth.add_permission(admins, 'write', 'Setting', maintenance.id)
# then you will check
auth.has_permission('write', 'Setting', maintenance.id)
```

### Blocking users

*New in version 0.6*

Sometimes you need to lock user operations on your application. The auth module have 2 different *locking* statuses for this:

- **disabled:** the user won't be able to perform the normal auth operation until the reset of the password
- **blocked:** the user won't be able to perform any auth operation (aka banned)

You can change an user status in two different ways, the first is directly with you `Auth` instance:

```python
auth.disable_user(user)
auth.block_user(user)
auth.allow_user(user)
```

where the only accepted parameter is an user row (including the id) or just the id of the user involved.

But you can also change the user status directly on a user you've selected from the database:

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
