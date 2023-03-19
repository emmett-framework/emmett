Upgrading to newer releases
===========================

Just like any software, Emmett is changing over time, and most of these changes we introduce don't require you to change anything into your application code to profit from a new release.

Sometimes, indeed, there are changes in Emmett source code that do require some changes or there are possibilities for you to improve your own code quality, taking advantage of new features in Emmett.

This section of the documentation reports all the main changes in Emmett from one release to the next and how you can (or you *should*) update your application's code to have the less painful upgrade experience.

Just as a remind, you can update Emmett using *pip*:

```bash
$ pip install -U emmett
```

Version 2.5
-----------

Emmett 2.5 release is highly focused on the included HTTP server.

This release drops previous 2.x deprecations and support for Python 3.7.

### New features

#### Granian HTTP server and RSGI protocol

Emmett 2.5 drops its dependency on uvicorn as HTTP server and replaces it with [Granian](https://github.com/emmett-framework/granian), a modern, Rust based HTTP server.

Granian provides [RSGI](https://github.com/emmett-framework/granian/blob/master/docs/spec/RSGI.md), an alternative protocol to ASGI implementation, which is now the default protocol used in Emmett 2.5. This should give you roughly 50% more performance out of the box on your application, with no need to change its code.

Emmett 2.5 applications still preserve an ASGI interface, so in case you want to stick with this protocol you can use the `--interface` option [in the included server](./deployment#included-server) or still use Uvicorn with the `emmett[uvicorn]` extra notation in your dependencies.

#### Other new features

Emmett 2.5 also introduces support for [application modules groups](./app_and_modules#modules-groups) and Python 3.11

Version 2.4
-----------

Emmett 2.4 release is highly focused on the included ORM.

This release doesn't introduce any deprecation or breaking change, but some new features you might be interested into.

### New features
 
- The ability to use relative paths in [templates](./templates) `extend` and `include` blocks
- GIS/spatial [fields](./orm/models#fields) and [operators]((./orm/operations#engine-specific-operators)) support in ORM
- [Primary keys customisation](./orm/advanced#custom-primary-keys) support in ORM
- A `watch` parameter to ORM [compute decorator](./orm/virtuals#computed-fields)
- A [save method](./orm/operations#record-save-method) to rows and [relevant callbacks](./orm/callbacks#before_save) in ORM
- A [destroy method](./orm/operations#record-destroy-method) to rows and [relevant callbacks](./orm/callbacks#before_destroy) in ORM
- [Commit callbacks](./orm/callbacks#before_commit-and_after_commit) in ORM
- [Changes tracking](./orm/operations#record-changes) to rows in ORM
- The `set` command to [migrations](./orm/migrations) CLI
- The ability to [skip callbacks](./orm/callbacks#skip-callbacks) in ORM

Emmett 2.4 also introduces support for Python 3.10.

Version 2.3
-----------

Emmett 2.3 introduces some deprecations and some new features you might be interested into.

### Deprecations

#### Cookie sessions encryption

Since its birth, Emmett tried to maximise its compatibility across platforms, and consequentially provided the cryptographic functions needed for its security modules in pure Python versions.

Nevertheless, those implemetations clearly provide poor performances, and we opted for rewriting them using Rust producing the [emmett-crypto](https://github.com/emmett-framework/crypto) package. This refactoring also gave us the chance to upgrade and modernise the algorithm used to encrypt the session data when using the [cookies implementation](./sessions#storing-sessions-in-cookies). 

Since the new algorithm is not compatible with the previous one, and the new implementation is an optional extra dependency in Emmett 2.3, we decided to deprecate the existing one letting you to decide when to switch to the new one, as such switch will invalidate all the active sessions.

This is why the `SessionManager.cookies` constructor in Emmett 2.3 has a new `encryption_mode` argument with default value set to *legacy*. In order to upgrade to new code, you should change your dependencies file to install Emmett with the crypto extras, like:

    pip install -U emmett[crypto]

and change the value for the `encryption_mode` parameter to *modern*:

```python
SessionManager.cookies('myverysecretkey', encryption_mode='modern')
```

> **Note:** since `emmett-crypto` module is written in Rust language, in case no pre-build wheel is available for your platform, you will need the Rust toolchain on your system to compile it from source.

### New features

With version 2.3 we introduced the following new features:

- [PostgreSQL json/jsonb](./orm/operations#engine-specific-operators) fields and operators support in ORM
- [Radio widget](./forms#additional-widgets) in forms
- [On deletion policies](./orm/relations#deletion-policies-on-relations) in `belongs_to` and `refers_to` relations
- A `--dry-run` option to [migrations](./orm/migrations) `up` and `down` commands

Also, in Emmett 2.3 we added an optional extra `crypto` dependency which re-implements cryptographic functions using Rust programming language.

Version 2.2
-----------

Emmett 2.2 introduces some changes you should be aware of, and some new features you might be interested into.

### Breaking changes

#### Fixed pbkdf2 library values representation

Emmett versions prior to `2.2.2` contain a bug in the library responsible of *PBKDF2* hashes generation. The produced hashes contain wrong characters due to a wrong decoding format. This means that any stored value produced by the library should be fixed, otherwise further hash comparisons will fail.

Previous generated values look like this:

    pbkdf2(2000,20,sha512)$adcc9967adbd17f6$b'c68deb7f0690c2cafb99b1f323313b17117337ac'

while the correct format is:

    pbkdf2(2000,20,sha512)$adcc9967adbd17f6$c68deb7f0690c2cafb99b1f323313b17117337ac

In case your application use the [Auth system](https://emmett.sh/docs/2.2.x/auth) with default configuration, the passwords' hashes stored in the database contain the wrong characters, and you should fix them manually. Here is a code snippet you can use:

```python
with db.connection():
    for row in User.where(lambda u: u.password.like("%b'%")).select():
        password_components = row.password.split("$")
        row.update_record(
            password="$".join(password_components[:-1] + [password_components[-1][2:-1]])
        )
    db.commit()
```

### Minor changes

The following changes are considered *minor* changes, since they affect only default values, and can be consequentially set to the previous ones:

- The default `SameSite` value for sessions cookies is now *Lax* instead of *None*
- The default logging level in `serve` command is now *info* in place of *warning*

Mind that Emmett 2.2 also drops support for previous 2.x deprecations.

### New features

With version 2.2 we introduced the following new features:

- [Commands groups](./cli#custom-commands) support in the CLI
- [Static paths customisation](./app_and_modules#application-modules) in application modules
- [Workers support](./deployment#included-server) in the included server

Version 2.1
-----------

Emmett 2.1 introduces some minor breaking changes you should be aware of, and some new features you might been interested into.

### Breaking changes

#### Removed sanitizer from libs

The *sanitizer* module was a very old module included in Emmett since long time ago. This module was written using the `formatter` module from standard library, deprecated since Python 3.4, and scheduled for removal in next Python versions.

The only place using this library in Emmett was in `html.safe` method with the `sanitize` option activated. Considering the lack of usage from the community, the lack of maintenance of the library and in order to avoid preventions in supporting future Python versions, since Emmett 2.1 this library is not available anymore. In case you need a replacement for the sanitizer, you must implement by yourself.

Moreover, calling `html.safe` with `sanitize` option set will warn about the behaviour difference.

### Deprecations

#### Html safe helper

Due to removal of `sanitizer` library, `html.safe` is now exactly the same of `html.asis`. You should switch the usage in your code.

#### Application run method

The `run` method in `App` class is now deprecated. Please rely on `develop` and `serve` command from CLI.

#### Extensions string signals

Prior to Emmett 2.1 [extensions signals](./extensions#using-signals) were implemented as strings. Since 2.1 a new `Signals` enum is available in extensions module you should use in place of strings.

### New features

With version 2.1 we introduced some new features:

- [HTTP/2](./request#http2) support
- `SameSite` parameter support on [session cookies](./sessions)

Emmett 2.1 also introduces (beta) support for Python 3.9, and type hints on all major interfaces.

Version 2.0
-----------

Version 2.0 introduces quite a lot of changes, with the majority of them being breaking. This is due to the drivers of this new major version:

- The drop of Python 2 support, since it reached End Of Life
- The switch to ASGI and async code from previous WSGI approach

Since these drivers changes completely the approach used to write applications, the framework name and packages were also changed, in order to avoid developers to inadvertently update between versions and brake all of their code. So, goodbye weppy, welcome Emmett.

If you are really considering porting your application to Emmett from weppy, here is the list of steps.

### New package name

Since the package name is changed to `emmett`, you will need to rewrite all the imports in your application from the old ones:

```python
from weppy import App, request
```

to the new package:

```python
from emmett import App, request
```

In general all the previous importables described in documentation are unchanged in Emmett, but we dropped quite a lot of the internals part of the WSGI flow, so in case you imported some peculiar resources and your code raises `ImportError`, please check the source code for the relevant changes.

Mind also that the `weppy` command is now the `emmett` command.

### Dropped support for Python 2

Since we dropped the support for Python 2, if your application is written using this version of the Python language, you need to update your code, following [one](https://docs.python.org/3/howto/pyporting.html) of the available guides out there.

Also mind that the minimum supported Python version in Emmett is 3.7.

### Async flow

In Emmett everything regarding the request flow follows ASGI implementation, and, thus, all the relative code should be asynchronous.

Operative speaking, you can keep your routes as standard methods, but whenever you access `Request.body_params`, you need to change your code from synchronous:

```python
@app.route()
def some_route():
    value = request.body_params.foo
```

to asynchronous one:

```python
@app.route()
async def some_route():
    value = (await request.body_params).foo
```

In general, if you need to repeatedly access `Request.body_params`, might be a good idea to store it in a variable:

```python
@app.route()
async def some_route():
    params = await request.body_params
    foo = params.foo
```

Mind that, since forms process the request's body, they're awaitable objects too:

```python
@app.route()
async def some_route():
    form = await SomeModel.form()
```

#### Async pipeline

Since the pipeline is strictly tied to request flow, all the methods inside `Pipe` class are now coroutine functions, so while in weppy you wrote:

```python
class MyPipe(Pipe):
    def open(self):
        pass
    def close(self):
        pass
    def pipe(self, next_pipe, **kwargs):
        return next_pipe(**kwargs)
    def on_pipe_success(self):
        pass
    def on_pipe_failure(self):
        pass
```

in Emmett you need to write:

```python
class MyPipe(Pipe):
    async def open(self):
        pass
    async def close(self):
        pass
    async def pipe(self, next_pipe, **kwargs):
        return await next_pipe(**kwargs)
    async def on_pipe_success(self):
        pass
    async def on_pipe_failure(self):
        pass
```

Due to the new asynchronous flow, we also introduced a big step-forward in the pipeline flow: while in weppy the `open` and `close` pipes' methods were called one after another, in Emmett they get scheduled in the loop at the same time. This means that **the order on which these methods get called is no more predictable**.

In general, if you need the execution order of your code to be preserved, use the `pipe` method instead of the `open` or `close` ones.

#### Upload handling

Emmett 2.0 introduces the `files` sdict attribute in the `Request` object.

As a direct consequence, your code should be updated to handle uploads from the new attribute, instead of looking for uploads in the `body_params` one.

An example might be the following:

```python
@app.route()
async def upload():
    files = await request.files
    file = files.upload_param
    await file.save(f"somepath/{file.filename}")
```

### Internationalization files

Since 2.0 Emmett uses [Severus](https://github.com/emmett-framework/severus) as its internationalization engine.

Versions prior to 2.0 implied usage of python files for translations, while in 2.0 supported formats are JSON and YAML.

This means you should convert your Python translations to JSON files, which in the majority of cases it just requires changing the files extensions from `.py` to `.json`.

Mind that the format syntax also changed: since Emmett 2.0 the only supported syntax for symbols in strings is the `format` one. Consequentialy you have to change your translation strings containing old symbols:

```json
{
    "you received %(like)s": "hai ricevuto %(like)s"
}
```

to the braces format:

```json
{
    "you received {like}": "hai ricevuto {like}"
}
```

### Other changes

Here we list other breaking changes introduced with 2.0

#### Removal of request combined params

Since the introduction of ASGI and asynchronous code we had to deal with the fact `Request.query_params` and `Request.body_params` started to have a different nature. In fact, while the first it's still an object, the second one became an awaitable.

In order to avoid code complexity, and also push the developer to explicitly declare in the application code which request's component gets accessed by the code, we opted to drop the generic combined `Request.params` attribute. This also gives more consistency to Emmett api's, since `Request.params` behaviour was not exactly predictable when the same parameter name was present both in `query_params` and `body_params`.

This means that you need to change the code where you using `Request.params` and use the other attributes. If you still want to make a combined version of the two, you can do it manually:

```python
@app.route()
async def some_route():
    params = {**request.query_params, **(await request.body_params)}
```

#### Default value for Content-Type header

In Emmett the default value for the response `Content-Type` header is now `text/plain` instead of the previous `text/html`.

All the automatic handling of this header done by the framework itself is still there, so even you're using a `service` pipe or a template for your route, nothing will change.

The main difference is that you no more need to declare plain text `Content-Type` if you just return a string in your route. You need to change the `Content-Type` header just if you return strings containing html in your routes.

### Deprecation of run CLI command

Aside from breaking changes, Emmett 2.0 also deprecated the `run` command, in favour of two different commands for local serving and production serving your application. This means you should use:

- `emmett -a some_app develop` in order to run a local server
- `emmett -a some_app serve` in order to run a production server

While the `run` command still works in Emmett 2.0, it will be completely removed in future versions.

### New features

Emmett 2.0 also introduces some new features:

- [Websockets](./websocket) support
- An optional `output` parameter to `route` decorator
- An `after_loop` signal

Emmett 2.0 also introduces official support for Python 3.8.
