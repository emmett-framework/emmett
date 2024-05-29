![Emmett](https://emmett.sh/static/img/logo-bwb-xb-xl.png)

Emmett is a full-stack Python web framework designed with simplicity in mind.

The aim of Emmett is to be clearly understandable, easy to be learned and to be 
used, so you can focus completely on your product's features:

```python
from emmett import App, request, response
from emmett.orm import Database, Model, Field
from emmett.tools import service, requires

class Task(Model):
    name = Field.string()
    is_completed = Field.bool(default=False)

app = App(__name__)
app.config.db.uri = "postgres://user:password@localhost/foo"
db = Database(app)
db.define_models(Task)
app.pipeline = [db.pipe]

def is_authenticated():
    return request.headers.get("api-key") == "foobar"
    
def not_authorized():
    response.status = 401
    return {'error': 'not authorized'}

@app.route(methods='get')
@requires(is_authenticated, otherwise=not_authorized)
@service.json
async def todo():
    page = request.query_params.page or 1
    tasks = Task.where(
        lambda t: t.is_completed == False
    ).select(paginate=(page, 20))
    return {'tasks': tasks}
```

[![pip version](https://img.shields.io/pypi/v/emmett.svg?style=flat)](https://pypi.python.org/pypi/emmett)
![Tests Status](https://github.com/emmett-framework/emmett/workflows/Tests/badge.svg)

## Documentation

The documentation is available at [https://emmett.sh/docs](https://emmett.sh/docs).
The sources are available under the [docs folder](https://github.com/emmett-framework/emmett/tree/master/docs).

## Examples

The *bloggy* example described in the [Tutorial](https://emmett.sh/docs/latest/tutorial) is available under the [examples folder](https://github.com/emmett-framework/emmett/tree/master/examples). 

## Status of the project

Emmett is production ready and is compatible with Python 3.8 and above versions.

Emmett follows a *semantic versioning* for its releases, with a `{major}.{minor}.{patch}` scheme for versions numbers, where:

- *major* versions might introduce breaking changes
- *minor* versions usually introduce new features and might introduce deprecations
- *patch* versions only introduce bug fixes

Deprecations are kept in place for at least 3 minor versions, and the drop is always communicated in the [upgrade guide](https://emmett.sh/docs/latest/upgrading).

## How can I help?

We would be very glad if you contributed to the project in one or all of these ways:

* Talking about Emmett with friends and on the web
* Adding issues and features requests here on GitHub
* Participating in discussions about new features and issues here on GitHub
* Improving the documentation
* Forking the project and writing beautiful code

## License

Emmett is released under the BSD License.

However, due to original license limitations, some components are included 
in Emmett under their original licenses. Please check the LICENSE file for 
more details.
