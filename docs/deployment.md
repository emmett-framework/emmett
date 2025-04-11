Deployment
==========

Depending on your setup and preferences, there are multiple ways to run Emmett applications. In this chapter, we'll try to document the most common ones.

Included server
---------------

*Changed in version 2.7*

Emmett comes with [Granian](https://github.com/emmett-framework/granian) as its HTTP server. In order to run your application in production you can just use the included `serve` command:

    emmett serve --host 0.0.0.0 --port 80

You can inspect all the available options of the `serve` command using the `--help` option. Here is the full list:

| option | default | description |
| --- | --- | --- |
| host | 0.0.0.0 | Bind address |
| port | 8000 | Bind port |
| workers | 1 | Number of worker processes |
| threads | 1 | Number of threads |
| blocking-trheads | 1 | Number of blocking threads |
| runtime-mode | st | Runtime implementation (possible values: st,mt) |
| interface | rsgi | Server interface (possible values: rsgi,asgi) |
| http | auto | HTTP protocol version (possible values: auto,1,2) |
| http-read-timeout | 10000 | HTTP read timeout (in milliseconds) |
| ws/no-ws | ws | Enable/disable websockets support |
| loop | auto | Loop implementation (possible values: auto,asyncio,rloop,uvloop) |
| log-level | info | Logging level (possible values: debug,info,warning,error,critical) |
| backlog | 2048 | Maximum connection queue |
| backpressure | | Maximum number of requests to process concurrently |
| ssl-certfile | | Path to SSL certificate file |
| ssl-keyfile | | Path to SSL key file |

Other ASGI servers
------------------

*Changed in version 2.7*

Since an Emmett application object is also an [ASGI](https://asgi.readthedocs.io/en/latest/) application, you can serve your project with any [ASGI compliant server](https://asgi.readthedocs.io/en/latest/implementations.html#servers).

To serve your project with such servers, just refer to the specific server documentation an point it to your application object.

Docker
------

Even if Docker is not properly a deployment option, we think giving an example of a `Dockerfile` for an Emmett application is proficient for deployment solutions using container orchestrators, such as Kubernetes or Mesos.

In order to keep the image lighter, we suggest to use the *slim* Python image as a source:

```Dockerfile
FROM python:3.9-slim

RUN mkdir -p /usr/src/deps
COPY requirements.txt /usr/src/deps

WORKDIR /usr/src/deps
RUN pip install --no-cache-dir -r /usr/src/deps/requirements.txt

COPY ./ /app
WORKDIR /app

EXPOSE 8000

CMD [ "emmett", "serve" ]
```
