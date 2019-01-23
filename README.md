**Warning:** *this branch is to be considered in alpha stage. Use at your own risk*

![logo](http://weppy.org/static/logo-big.png)

[![pip version](https://img.shields.io/pypi/v/weppy.svg?style=flat)](https://pypi.python.org/pypi/weppy) 
[![build status](https://img.shields.io/travis/gi0baro/weppy.svg?style=flat)](https://travis-ci.org/gi0baro/weppy)

weppy is a full-stack python web framework designed with simplicity in mind.

The aim of weppy is to be clearly understandable, easy to be learned and to be 
used, so you can focus completely on your product's features:

```python
from weppy import App, request, response
from weppy.orm import Database, Model, Field
from weppy.tools import service, requires

class Task(Model):
    name = Field.string()
    is_completed = Field.bool(default=False)

app = App(__name__)
app.config.db.uri = "postgres://user:password@localhost/foo"
db = Database(app)
db.define_models(Task)
app.pipeline = [db.pipe]

def is_authenticated():
    return request.headers["Api-Key"] == "foobar"
    
def not_authorized():
    response.status = 401
    return {'error': 'not authorized'}

@app.route(methods='get')
@service.json
@requires(is_authenticated, otherwise=not_authorized)
def todo():
    page = request.query_params.page or 1
    tasks = Task.where(
        lambda t: t.is_completed == False
    ).select(paginate=(page, 20))
    return {'tasks': tasks}
```

## Installation

You can install weppy using pip:

```
$ pip install weppy
```

## Documentation

The documentation is available at [http://weppy.org/docs](http://weppy.org/docs).
The sources are available under the *docs* folder.

## Examples

The "bloggy" example described in the [Tutorial](http://weppy.org/docs/latest/tutorial) is available under the *examples* folder. 
While we're still populating this folder with more examples, you can also take a look at [H-Funding](https://github.com/gi0baro/h-funding), which uses many of weppy's features.

## Starter kit

Aside from the examples, we encourage you to look at the [starter kit](https://github.com/mijdavis2/starter_weppy) and the convenient [scaffold generator](https://github.com/mijdavis2/generator-weppy-mvc) written by [MJ Davis](https://github.com/mijdavis2). These projects can really help you writing your next weppy application.

## Status of the project

This is an alpha stage branch for the async weppy support. It can be used only with Python 3.7 and above versions.

## How can I help?

We would be very glad if you contributed to the project in one or all of these ways:

* Talking about weppy with friends and on the web
* Participating in [weppy users group](https://groups.google.com/forum/#!forum/weppy-talk)
* Adding issues and features requests here on GitHub
* Participating in discussions about new features and issues here on GitHub
* Improving the documentation
* Forking the project and writing beautiful code

## License

weppy is released under the BSD License.

However, due to original license limitations, some components are included 
in weppy under their original licenses. Please check the LICENSE file for 
more details.
