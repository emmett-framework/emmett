Services
========

Quite often, you will need to render the output of your application using a
protocol other than HTML; for example, JSON or XML.

Emmett can help you expose those services with the `service` decorator:

```python
from emmett import App
from emmett.tools import service

app = App(__name__)

@app.route("/json")
@service.json
async def f():
    # your code
```
The output will be automatically converted using the required service
(JSON in this example).

> – awesome. But, what if I need to expose several function with a service?
Should I decorate every function?   
> – *you can use the provided pipe, dude*

Emmett also provides a `ServicePipe` object so you can create an application module with all the functions you want to expose with a specific service and add the pipe to the module:

```python
from emmett.tools import ServicePipe
from myapp import app

api = app.module(__name__, 'api')
api.pipeline = [ServicePipe('json')]

@api.route()
async def a():
    # code

@api.route()
async def b():
    # code
```

So, which are the available services? Let's see them.

JSON and XML
------------

Providing a JSON service with Emmett is quite easy:

```python
@app.route("/json")
@service.json
async def f():
    l = [1, 2, {'foo': 'bar'}]
    return dict(status="OK", data=l)
```

The output will be a JSON object with the converted content of your python
dictionary:

```json
{
    "status": "OK",
    "data": [
        1,
        2,
        {
            "foo": "bar",
        }
    ]
}
```

To provide an XML service, just decorate your function using the next line
instead:

```python
@service.xml
```

Obviously, the syntax for using `ServicePipe` is the same as in the 
first example:

```python
# providing a JSON service pipe
ServicePipe('json')

# providing an XML service pipe
ServicePipe('xml')
```

Multiple services
-----------------

Sometimes you may want to expose several services for a single endpoint, for example a list of items both in JSON and XML format.

You can easily achieve this decorating your route multiple times, using different pipelines:

```python
from emmett.tools import ServicePipe

@app.route('/elements.json', pipeline=[ServicePipe('json')])
@app.route('/elements.xml', pipeline=[ServicePipe('xml')])
async def elements():
    return [{"foo": "bar"}, {"bar": "foo"}]
```

With this notation, you can serve different services using the same exposed method.
