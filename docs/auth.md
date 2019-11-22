The Authorization System
========================

Since authorizations and authentications are a very important part of almost every application, Emmett includes an useful module to deal with them. With a few lines of code, you will be able to create any required database tables and generate forms for access control in your application.

So, how do you use it? Let's find out with an example:

```python
from emmett import App
from emmett.orm import Database
from emmett.tools.auth import Auth, AuthUser
from emmett.sessions import SessionManager

app = App(__name__)
app.config.db.uri = "sqlite://storage.sqlite"
app.config.auth.hmac_key = "mysupersecretkey"
app.config.auth.single_template = True

class User(AuthUser):
    pass

db = Database(app)
auth = Auth(app, db, user_model=User)

app.pipeline = [
    SessionManager.cookies('myverysecretkey'),
    db.pipe,
    auth.pipe
]

auth_routes = auth.module(__name__)
```

That's it.

Write a template page for the auth module (that should be placed in *templates/auth/auth.html*) to render the `form` variable returned by the module, and open [http://127.0.0.1:8000/auth/login](http://127.0.0.1:8000/auth/login) in your browser. Emmett should show you a login page with the appropriate form.

> **Note:** Emmett's `Auth` module requires session handling and a `Database` instance activated on your application in order to work properly.

As you've figured out, the `auth_routes` module will be responsible for
your app's authorization flow. With the default settings, the `Auth` module 
of Emmett exposes the following:

* http://.../{url\_prefix}/login
* http://.../{url\_prefix}/logout
* http://.../{url\_prefix}/registration
* http://.../{url\_prefix}/profile
* http://.../{url\_prefix}/email_verification/{verification\_key}
* http://.../{url\_prefix}/password_retrieval
* http://.../{url\_prefix}/password\_reset/{reset\_key}
* http://.../{url\_prefix}/password_change

and it creates all the necessary database tables, from users to groups and memberships.

You can obviously change the routing URL prefix (default set to *auth*) as any other application module:

```python
auth_routes = auth.module(__name__, url_prefix='account')
```

Auth module configuration
-------------------------

*Changed in version 1.0*

The auth module have quite a few options that can be configured. We already saw the `hmac_key` parameter, which is used to crypt passwords in the database, or the `single_template` option we used in the *bloggy* example and above.

Here is the complete list of parameters that you can change:

| parameter | default value | description |
| --- | --- | --- |
| hmac\_key | `None` | the key (required) that will be used to crypt users' passwords |
| hmac\_alg | pbkdf2(2000,20,sha512) | the algorithm that will be used to crypt users' password |
| inject\_pipe | `False` | configure the module to automatically inject its pipe on the application |
| log\_events | `True` | store in the module events table events regarding auth |
| flash\_messages | `True` | use the Emmett flashing system to display messages |
| csrf | `True` | use CSRF protection logic on forms |
| single\_template | `False` | decide if every route exposed by the module should use a single template |
| password\_min\_length | 6 | minimum length for users password |
| remember\_option | `True` | add a *remember me* checkbox in login form to have long-living sessions |
| session\_expiration | 3600 | inactivity time (seconds) after which the session will expire |
| session\_long\_expiration | 3600 * 24 * 30 | inactivity time (seconds) after which a long living session will expire |
| registration\_verification | `True` | decide if the user's email should be validated on registration |
| registration\_approval | `False` | decide if registered users should be approved manually |

As an example, if you leave the `single_template` option set to `True`, you have to write one template for every routed function of the module that we saw above.

> **Warning:** if you change the `hmac_key` and/or `hmac_alg` afterwards, the users registered to your application won't be able to login unless they reset their passwords.

> **Note:** the `registration_verification` option requires a [mailer](./mailer) is configured on the application in order to work properly.

The auth module is also pre-configured with quite a few standard messages that will be used by the system for a wide case of scenarios, from labels to error messages. You can inspect all the messages you can customize printing the dictionary in the standard configuration of the module under the `messages` key:

```python
>>> auth.ext.config.messages
```

and you can obviously configure them with the application configuration:

```python
from emmett import T

app.config.auth.messages.profile_button = T("Update profile")
```

### Disable specific routes

You may want to disable some actions exposed by the authorization module.
Let's say you don't want the `password_retrieval` functionality. To do that, just edit your application configuration:

```python
app.config.auth.disabled_routes = ["password_retrieval"]
```

### Change routes paths

*New in version 1.1*

You may want to change the default url paths for the auth module routes. You just have to change the value of the `routes_paths` dictionary in the configuration:

```python
app.config.auth.routes_paths = {
    'login': '/signin',
    'logout': '/signout',
    'registration': '/signup'}
```

### Callbacks

The auth module has an *after* callback for every route exposed by the module. This is useful, for example, if you want to change the default redirects after a certain action has occurred. In fact, under the default behaviour, the user will be redirected to its own profile after the login, while you may want to redirect him/her to a *dashboard* route you defined:

```python
from emmett import url, redirect

@auth_routes.after_login
def after_login(form):
    redirect(url('dashboard'))
```

Here is the complete list of available callbacks, with the parameters passed to them:

| callback | parameters |
| --- | --- |
| after\_login | form |
| after\_logout | |
| after\_registration | form, user, logged\_in |
| after\_profile | form |
| after\_email\_verification | user |
| after\_password\_retrieval | user |
| after\_password\_reset | user |
| after\_password\_change | |

where `form` is the form the user has filled in. The `user` parameter is present on the routes that don't have a user logged into the system, while the `logged_in` parameter tells you if the user was logged into the system after the registration.

### Add custom routes
You can also define custom actions to be routed by the auth module. Let's say you want to route a method for the facebook authentication on the */account/facebook* path:

```python
@auth_routes.route("/facebook")
def facebook_auth():
    # some code
```

### Mails

The auth module is pre-configured to send two different mails:

- to verify the email for the registration process
- to reset the password in case the user forgot it

You can customize these mails using the appropriate decorators:

- `@auth.registration_mail`
- `@auth.reset_password_mail`

For example, you may want to customize the registration email like this:

```python
@auth.registration_mail
def registration_mail(user, data):
    subject = "Welcome to Massive Dynamic!"
    body = (
        "Hi, welcome to Massive Dynamic. "
        "Please let Nina know you're from this universe and "
        "click on the link %(link)s to verify your email.")
    mailer.send_mail(
        recipients=user.email, subject=subject, body=body % data)
```

The functions you decorate with both decorators should accept the `user` and `data` parameters. The `data` parameter is a dictionary and will contains just the `link` item.

> **Note:** in order to use mail features you need a [mailer](./mailer) configured with your application.

Access control with "requires"
------------------------------

*Changed in 1.0*

One of the strengths of the authorization module is that it is simple to
introduce access controls to your application. Let's say that you need to allow
access to a specific zone to only users who are logged in. With Emmett,
you can do that with one line of code:

```python
from emmett.tools import requires

@app.route()
@requires(auth.is_logged, url('unauthorized_page'))
async def my_protected_page():
    #some code
```

As you probably figured out, the `requires` helper will determine if the condition 
in the first parameter passed as and if that is not so, Emmett will redirect 
the client to the URL in the second parameter.

You can also pass a function to be invoked as with the second parameter, for example:

```python
def not_auth():
    abort(403)

@app.route()
@requires(lambda: auth.has_membership('admins'), not_auth)
async def admin():
    # code
```

returns an HTTP 403 error.

> **Note:** when you need to evaluate the condition during the request, 
you should use a `lambda` function if the first argument passed to `requires`
is not a callable.

Sometimes you may need to return specific contents on missing authorization. 
In that case, you can write:

```python
from emmett.tools import service

def not_authorized():
    return dict(error="Not authorized")

@app.route()
@requires(auth.is_logged, not_authorized)
@service.json
async def protected():
    return dict(data="Some data here")
```

so the client will also receive a JSON object on an authorization error.

> – OK, dude. What if I want to protect an entire application module with 
access control?

You can use the `RequirePipe` instead of decorating any function 
of your module:

```python
from emmett.pipeline import RequirePipe

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
from emmett.orm import Field
from emmett.tools.auth import AuthUser

class User(AuthUser):
    avatar = Field.upload(uploadfolder="uploads")
    
    form_profile_rw = {
        "avatar": True
    }
```

and pass it to the `Auth` instance:

```python
from emmett.tools import Auth
auth = Auth(app, db, user_model=User)
```

As you can see, defining your user model by subclassing `AuthUser` is essentially the same as subclassing `Model`, but there are some differences.

Firstly, the fields you define will be the additional fields you will want to add to the user table. Secondly, you'll use `form_profile_rw` and `form_registration_rw`, instead of the `fields_rw` attribute, to treat the field differently for accesses during user registration and during user edits after registration. The default visibility is set to `False` for any extra fields you define, so the above example allows the client to upload an avatar for their account only with the profile function, not during the registration.

The default fields included in the `AuthUser` model are:

- email
- password
- first_name
- last_name

plus some other columns need by the system and hidden to the users.

If you don't want to have the `first_name` and `last_name` fields inside your
user model (they are set to be not-null), you can subclass the `AuthUserBasic`
model instead, available under `emmett.tools.auth.models`, which doesn't include them.

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
admins = auth.create_group('administrators')
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

Nonetheless, Emmett's `Auth` module also have a finer management for users,
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

Emmett's `Auth` permissions also support more details, like a model name and a record:

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

Additional login methods
------------------------

*section in development*
