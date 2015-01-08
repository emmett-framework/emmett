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
auth = Auth(app, db, base_url='/account')

app.common_handlers = [
    SessionCookieManager('myverysecretkey'),
    db.handler,
    auth.handler
]

@app.expose('/account(/<str:f>)?(/<str:k>)?')
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
* http://.../{baseurl}/change_password
* http://.../{baseurl}/profile

and it also creates all the database tables needed, from users to groups and memberships ones.

You can obviously change the base url for the authorization function:

```python
auth = Auth(app, db, base_url='/mycontrol')

@app.expose('/mycontrol(/<str:f>)?(/<str:k>)?')
def account(f, k):
    form = auth(f, k)
    return dict(form=form)
```
you just need to remember using the `"/name(/<str:f>)?(/<str:k>)?"` format for exposing your account function, otherwise the authorization module won't work properly.

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

@app.expose()
@requires(auth.is_logged_in, url('unauthorized_page'))
def myprotected_page():
    #some code
```

As you probably figured out, the `requires` helper will check the condition passed as the first parameter and if the request doesn't met the requirement, it will redirect the client on the url passed as second parameter.

You can also pass a function to be invoked as second parameter, for example:

```python
def not_auth():
    abort(403)

@app.expose()
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

@app.expose()
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

Database tables
---------------
*section under writing*

Authorization system with DAL Models
------------------------------------
You can obviously use the Auth module with the [database Models layer](./dal#the-models-layer). You just have to define your user model:

```python
from weppy import Field
from weppy.dal import AuthModel


class User(AuthModel):
    fields = [
        Field("avatar", "upload", uploadfolder='uploads'),
    ]

    profile_visibility = {
        "avatar": (True, True)
    }
```

and pass it to the Auth instance:

```python
from weppy.tools import Auth
auth = Auth(app, db, usermodel=User)
```

As you can see, defining an `AuthModel` is quite the same as for a `Model`, except that the fields you define will be the additional fields you want to add to the user table, and instead of the `visibility` attribute you have `profile_visibility` and `register_visibility` to treat separately the field access during user registration and when the user edits its own profile.
As the default visibility is set to `False` for any extra field you have defined, in the above example the client will be able to upload an avatar for its account only with the profile function and not during the registration.

Auth module configuration
-------------------------

*section under writing*

Additional login methods
------------------------

*section under writing*
