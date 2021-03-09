Sessions
========

An essential feature for a web application is the ability to store specific informations about the client from a request to the next one. Accordingly to this need, Emmett provides another object beside the `request` and the `response` ones called `session`.

```python
from emmett import session

@app.route("/counter")
async def count():
    session.counter = (session.counter or 0) + 1
    return "This is your %d visit" % session.counter
```

The above code is quite simple: the app increments the counter every time the user visit the page and return this number to the user.   
Basically, you can use `session` object to store and retrieve data, but before you can do that, you should add a *SessionManager* to your application pipeline. These managers allows you to store sessions' data on different storage systems, depending on your needs. Let's see them in detail.

Storing sessions in cookies
---------------------------

*Changed in version 2.1*

You can store session contents directly in the cookies of the client using the Emmett's `SessionManager.cookies` pipe:

```python
from emmett import App, session
from emmett.sessions import SessionManager

app = App(__name__)
app.pipeline = [SessionManager.cookies('myverysecretkey')]

@app.route("/counter")
# previous code
```

As you can see, `SessionManager.cookies` needs a secret key to crypt the sessions' data and keep them secure – you should choose a good key – but also accepts more parameters:

| parameter | default value | description |
| --- | --- | --- |
| expire | 3600 | the duration in seconds after which the session will expire |
| secure | `False` | tells the manager to allow *https* sessions only |
| samesite | Lax | set `SameSite` option for the cookie |
| domain | | allows to set a specific domain for the cookie |
| cookie\_name | | allows to set a specific name for the cookie |
| cookie\_data | | allows to pass additional cookie data to the manager |

Storing sessions on filesystem
------------------------------

*Changed in version 2.1*

You can store session contents on the server's filesystem using the Emmett's `SessionManager.files` pipe:

```python
from emmett import App, session
from emmett.sessions import SessionManager

app = App(__name__)
app.pipeline = [SessionManager.files()]

@app.route("/counter")
# previous code
```

As you can see, `SessionManager.files` doesn't require specific parameters, but it accepts these optional ones:

| parameter | default value | description |
| --- | --- | --- |
| expire | 3600 | the duration in seconds after which the session will expire |
| secure | `False` | tells the manager to allow sessions only on *https* protocol |
| samesite | Lax | set `SameSite` option for the cookie |
| domain | | allows to set a specific domain for the cookie |
| cookie\_name | | allows to set a specific name for the cookie |
| cookie\_data | | allows to pass additional cookie data to the manager |
| filename_template | `'emt_%s.sess'` | allows you to set a specific format for the files created to store the data |

Storing sessions using redis
----------------------------

*Changed in version 2.1*

You can store session contents using *redis* – you obviously need the redis package for python – with the Emmett's `SessionManager.redis` pipe:

```python
from redis import Redis
from emmett import App, session
from emmett.sessions import SessionManager

app = App(__name__)
red = Redis(host='127.0.0.1', port=6379)
app.pipeline = [SessionManager.redis(red)]

@app.route("/counter")
# previous code
```

As you can see `SessionManager.redis` needs a redis connection as first parameter, but as for the cookie manager, it also accepts more parameters:

| parameter | default | description |
| --- | --- | --- |
| prefix | `'emtsess:'` | the prefix for the redis keys (default set to |
| expire | 3600 | the duration in seconds after which the session will expire |
| secure | `False` | tells the manager to allow sessions only on *https* protocol |
| samesite | Lax | set `SameSite` option for the cookie |
| domain | | allows to set a specific domain for the cookie |
| cookie\_name | | allows to set a specific name for the cookie |
| cookie\_data | | allows to pass additional cookie data to the manager |

The `expire` parameter tells redis when to auto-delete the unused session: every time the session is updated, the expiration time is reset to the one specified.
