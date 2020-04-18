![logo](http://weppy.org/static/logo-big.png)

[![pip version](https://img.shields.io/pypi/v/weppy.svg?style=flat)](https://pypi.python.org/pypi/weppy) 
![Tests Status](https://github.com/emmett-framework/emmett/workflows/Tests-weppy/badge.svg)

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

## Benchmarks

weppy is one of several Python web frameworks included in [TechEmpower benchmarks](https://www.techempower.com/benchmarks). Here are some snippets from the results (Python 3):

**ORM**

| framework | req/s | performance gain |
| --- | --- | --- |
| weppy 1.0.1 | 40690 | 2.1x |
| pyramid 1.6.1 | 28342 | 1.5x |
| django 1.9.4 | 25525 | 1.3x |
| flask 0.10.1 | 19495 | 1x |

**JSON serialization**

| framework | req/s | performance gain |
| --- | --- | --- |
| weppy 1.0.1 | 257196 | 3.1x |
| pyramid 1.6.1 | 172666 | 2.1x |
| flask 0.10.1 | 106679 | 1.3x |
| django 1.9.4 | 83390 | 1x |

## Status of the project

Since version 1.0 weppy can be considered stable. Is compatible with Python 2.7, 3.4, 3.5 and 3.6.

weppy is currently used in production by:

- [Sellf](https://github.com/Sellf)

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
