Sessions
========

An essential feature for a web application is the ability to store specific informations about the client from a request to the next one. Accordingly to this need, weppy provides another object beside the `request` and the `response` ones called `session`.

```python
from weppy import session

@app.route("/counter")
def count():
    session.counter = (session.counter or 0) + 1
    return "This is your %d visit" % session.counter
```

The above code is quite simple: the app increments the counter every time the user visit the page and return this number to the user.   
Basically, you can use `session` object to store and retrieve data, but before you can do that, you should add a *SessionManager* to your application handlers. These managers allows you to store sessions' data on different storage systems, depending on your needs. Let's see them.

Storing sessions in cookies
---------------------------
You can store session contents directly in the cookies of the client using the weppy's `SessionCookieManager` handler:

```python
from weppy import App, session
from weppy.sessions import SessionCookieManager

app = App(__name__)
app.common_handlers = [SessionCookieManager('myverysecretkey')]

@app.route("/counter")
# previous code
```

As you can see, `SessionCookieManager` needs a secret key to crypt the sessions' data and keep them secure – you should choose a good key – but also accepts more parameters:

| parameter | description |
| --- | --- |
| secure | tells the manager to allow sessions only on *https* protocol |
| domain | allows you to set a specific domain for the cookie |

Storing sessions on filesystem
------------------------------
*New in version 0.2*

You can store session contents on the server's filesystem using the weppy's `SessionFSManager` handler:

```python
from weppy import App, session
from weppy.sessions import SessionFSManager

app = App(__name__)
app.common_handlers = [SessionFSManager()]

@app.route("/counter")
# previous code
```

As you can see, `SessionFSManager` doesn't require specific parameters, but it accepts these optional ones:

| parameter | description |
| --- | --- |
| expire | set the expiration for the session (default `3600` seconds) |
| secure | tells the manager to allow sessions only on *https* protocol |
| domain | allows you to set a specific domain for the cookie |
| filename_template | allows you to set a specific format for the files created to store the data (default `'weppy_%s.sess'`) |

Storing sessions using redis
----------------------------
You can store session contents using *redis* – you obviously need the redis package for python – with the weppy's `SessionRedisManager` handler:

```python
from redis import Redis
from weppy import App, session
from weppy.sessions import SessionRedisManager

app = App(__name__)
red = Redis(host='127.0.0.1', port=6379)
app.common_handlers = [SessionRedisManager(red)]

@app.route("/counter")
# previous code
```

As you can see `SessionRedisManager` needs a redis connection as first parameter, but as for the cookie manager, it also accepts more parameters:

| parameter | description |
| --- | --- |
| prefix | the prefix for the redis keys (default set to `'wppsess:'` |
| expire | set the expiration for the keys (default `3600` seconds) |
| secure | tells the manager to allow sessions only on *https* protocol |
| domain | allows you to set a specific domain for the cookie |

The `expire` parameter tells redis when to auto-delete the unused session: every time the session is updated, the expiration time is reset to the one specified.
