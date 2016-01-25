Services
========

Quite often you would need to render the output of your application using a different protocol, for example JSON or XML.

weppy can help you exposing those services with the `service` decorator:

```python
from weppy import App
from weppy.tools import service

app = App(__name__)

@app.route("/json")
@service.json
def f():
    # your code
```
The output will be automatically converted using the required service (in this example JSON).

> – awesome. But, what if I need to expose several function with a service? Should I decorate every function?   
> – *you can use the provided handler, dude*

weppy also provides a `ServiceHandler` object so you can create an `AppModule` with all the functions you want to expose with a specific service and add the handler to the module:

```python
from weppy import AppModule
from weppy.tools import ServiceHandler
from myapp import app

api = AppModule(app, 'api', __name__)
api.common_handlers = [ServiceHandler('json')]

@api.route()
def a():
    # code

@api.route()
def b():
    # code
```

So, which are the available services? Let's see them.

JSON and XML
------------

Providing a JSON service with weppy is quite easy:

```python
@app.route("/json")
@service.json
def f():
    l = [1, 2, {'foo': 'bar'}]
    return dict(status="OK", data=l}
```

The output will be a JSON object with the converted content of your python dictionary:

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

To provide an XML service, just decorate your function using the next line:

```python
@service.xml
```

Obviously the syntax for the `ServiceHandler` usage is the same of the first example:

```python
# providing a json service handler
ServiceHandler('json')

# providing an xml service handler
ServiceHandler('xml')
```
