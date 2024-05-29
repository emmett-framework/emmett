Debug and logging
=================

*Errare humanum est*, said Seneca, a long time ago. As humans, sometimes we fail, and, sooner or later, we will see an exception on our applications. Even if the code is 100% correct, we can still get exceptions from time to time. And why? Well, *shit happens*, not only as a consequence of the Finagle's Law – even if he was damn right, wasn't he? – but also because the process of deploying web applications forces us to deal with a long list of involved technologies, everyone of which could fail. Just think about it: the client may fail during the request, your database can be overloaded, a hard-drive on your machine can crash, a library you're using can contain errors, and this goes on and on.

So, what can we do to face all this necessary complexity?   

Emmett provides two facilities to track and debug errors on your application: a *debugger* for your development process, and a simple logging configuration for your production environment.

Debugger
--------

When you run your application with the built-in development server or set your `App.debug` attribute to `True`, Emmett will use its internal debugger when an exception occurs to show you some useful information. What does that look like?

![debugger](https://emmett.sh/static/screens/debug.png)

The debug page contains three sections:

- the **application traceback**   
- the **full traceback**   
- the **frames** view

The difference between the two tracebacks is straightforward: the first is filtered only on your application code, while the second contains the complete trace of what happened – including the framework components, libraries, and so on.

The third section of the debugger page is called *frames* and inspecting it can tell you a lot about what happened during an exception.

![debugger](https://emmett.sh/static/screens/debug_frames.png)

As you can see, for every step of the full traceback, Emmett collects – when is possible – all the variables' contents and reports them as shown in the above screen.

> – OK, dude. What happens when I have an error in a template?   
> – *the debugger catches them too.*

![debugger](https://emmett.sh/static/screens/debug_template.png)

The debugger will also try to display the line that generated the exception in templates, complete with the error type. Still, when you forget a `pass` in a template file, it can be impossible to show you the statement that was not *passed*.

Logging application errors
--------------------------

When your application runs on production, Emmett – obviously – won't display the debug page, but will collect the full traceback and store it in logs. In fact, with the default configuration, a file called *production.log* will be created in the *logs* folder inside your application folder. It will log every message labeled as *warning* level or more severe.

But how does Emmett logging works?   

It uses the standard Python logging module, and provides a shortcut that you can use with the `log` attribute of your `App`. This becomes handy when you want to add some messages inside your code, because you can just call:

```python
app.log.debug('This is a debug message')
app.log.info('This is an info message')
app.log.warning('This is a warning message')
```

Basically, the `log` attribute of your app is a Python `Logger` with some handlers configured. As we said above, Emmett automatically logs exceptions calling your `app.log.exception()`.

### Configuring application logs

You probably want to configure logging for your application to fit your needs. To do that, just use your `app.config` object:

```python
from emmett import App, sdict

app = App(__name__)

app.config.logging.myfile = sdict(
    level="info",
    max_size=100*1024*1024
)
```

With this example, you will generate a *myfile.log* which will grow to 100MB in size and log all messages with an *info* level or higher. This is the complete list of parameters you can set for a logging file:

| name | description |
| --- | --- |
| max\_size | max size for the logging files (default `5*1024*1024`) |
| file\_no | number of old files to keep with rotation (default `4`) |
| level | logging level (default `'warning'`) |
| format | format for messages (default `'[%(asctime)s] %(levelname)s in %(module)s: %(message)s'`) |
| on\_app\_debug | tells Emmett to log the messages also when application is in debug mode (default `False`) |

That's it.
