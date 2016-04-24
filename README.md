![logo](http://weppy.org/static/logo-big.png)

[![pip version](https://img.shields.io/pypi/v/weppy.svg?style=flat)](https://pypi.python.org/pypi/weppy) 
[![build status](https://img.shields.io/travis/gi0baro/weppy.svg?style=flat)](https://travis-ci.org/gi0baro/weppy)

weppy is a full-stack Python framework that includes everything needed to easily
create fast, scalable, and secure web applications. It takes some components from
*web2py* and has a syntax inspired by *Flask*.

The aim of weppy is to be clearly understandable, easy to be learned and to be used,
so you can focus completely on your product's features:

```python
from weppy import request, response
from weppy.tools import service, requires
from myapp import app, auth

@app.route()
@service.json
@requires(auth.is_logged_in, otherwise=not_authorized)
def todos():
    page = request.params.page or 1
    return {'todos': auth.user.todos.select(paginate=page)}

def not_authorized():
    response.status = 401
    return {'error': 'not authorized'}
```

## Installation

You can install weppy using pip:

    pip install weppy

## Documentation

The documentation is available at [http://weppy.org/docs](http://weppy.org/docs).
The sources are available under the *docs* folder.

## Examples

The "bloggy" example described in the [Tutorial](http://weppy.org/docs/latest/tutorial)
is available under the *examples* folder. While we're still populating this folder
with more examples, you can also take a look at [H-Funding](https://github.com/gi0baro/h-funding),
which uses many of weppy's features.

## Benchmarks

weppy was one of several Python 3 frameworks included in some benchmarks
[published by Kirill Klenov](http://klen.github.io/py-frameworks-bench).

This is an extract from the results for a simple JSON serialization:

| framework | req/s | ms/req | performance |
| --- | --- | --- | --- |
| weppy | 10853 | 18.46 | 2.5x |
| flask | 6831 | 29.38 | 1.6x |
| django | 4330 | 46.61 | 1x |

## Status of the project

weppy is currently released in beta stage.
*What does that mean?*

* That the code may contain *noteworthy* bugs
* That you can use it on production, but cannot blame the developers if 
something goes wrong

weppy provides support for Python 2.7, 3.3, 3.4 and 3.5.

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
