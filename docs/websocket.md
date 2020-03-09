Handling websockets
===================

*New in version 2.0*

In the same way we saw for [requests](./request), Emmett also provides facilities to help you dealing with websockets in your application.

The websocket object
--------------------

When a websocket connection comes from a client, Emmett binds useful informations about it within the `websocket` object, which can be accessed just with an import:

```python
from emmett import websocket
```

It contains useful information about the current processing socket, in particular:

| attribute | description |
| --- | --- |
| scheme | could be *ws* or *wss* |
| path | full path of the request |
| host | hostname of the request |
| headers | the headers of the request |
| cookies | the cookies passed with the request |

Now, let's see how to deal with request variables.

### Request variables

Emmett's `websocket` object also shares the same attributes of `request` when available:

| attribute | description |
| --- | --- |
| query_params | contains the URL query parameters |

and also in websockets, this attribute is an `sdict` object so when the URL doesn't contain the query parameter you're trying to look at, this will be `None`, so it's completely safe to call it. It won't raise any exception.


Sending and receiving messages
------------------------------

The main difference between request routes and websocket ones is the communication flow. In fact, while in standard routes you just write a return value, with sockets you can receive and send multiple messages within the same connection.

This is why the `websocket` object in Emmett also has three awaitable methods for this purpose:

- accept
- receive
- send

While the `accept` method is implicitly called by the former ones, and is exposed in case you want to specify a specific flow for websockets acceptance, the `receive` and `send` method will be used by Emmett to deal with communications.

Giving an example, a super simple echo websocket in Emmett will look like this:

```python
from emmett import websocket

@app.websocket()
async def echo():
    while True:
        message = await websocket.receive()
        await websocket.send(message)
```

Mind that, since a websocket route essentially is a loop, when your code returns Emmett will close the connection.
