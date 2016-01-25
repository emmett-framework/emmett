Debug and logging
=================

*Errare humanum est* stated Seneca a long time ago. As humans, sometimes we fail, and sooner or later we will see an exception on our applications.   
Even if the code is 100% correct, we can still get exceptions from time to time. And why? Well, *shit happens*, not only as a consequence of the Murphy's law – even if he was damn right, wasn't he? – but also because when we deploy web applications we have to deal with a long list of involved stuffs, and everyone of these can fail as well.   
Just think about it: the client may fail during the request, your database can be overloaded, an hard-drive on your machine can crash, a library you're using can contain errors, and so on.

So, what can we do to face all this?   
weppy provides two facilities to track and debug errors on your application: a *debugger* for your development process, and a simple logging configuration for the production.

Debugger
--------
When you run your application with the builtin server, using the `run()` method, or the *weppy* command, or when you set to `True` your `App.debug` attribute, weppy will use its internal debugger when an exception occurs to show you some useful informations. Asking yourself what you will see?

![debugger](http://weppy.org/static/debug.png)

The debug page contains three sections:

- the **application traceback**   
- the **full traceback**   
- the **frames** view

The difference between the two tracebacks is quite obvious: the first is filtered only on your application code, while the second contains the complete trace of what happened – including the framework components, libraries and so on.

The third section of the debugger page is called *frames* and can be quite useful to inspect what happened during an exception:

![debugger](http://weppy.org/static/debug_frames.png)

As you can see, for every step of the full traceback, weppy collects – when is possible – all the variables contents and reports them like in the above screen.

> – Ok dude. What happens when I have an error in a template?   
> – *the debugger catch them too.*

![debugger](http://weppy.org/static/debug_template.png)

The debugger will also try to display the correct line that generated the exception also in templates, compatibly with the error type – when you forget a `pass` in a template file, can be impossible to show you the statement which is not *passed*.

Logging application errors
--------------------------
When your application runs on production, weppy – obviously – won't display the debug page, but will collect the full traceback and store it into logs.   
In fact, with the default configuration a file called *production.log* will be created into *logs* folder inside your application folder, and it will log every message with a *warning* level or higher.

But how does weppy logging works?   
It uses the standard python logging module, and provides a shortcut to use it with the `log` attribute of your `App`. This becomes handy when you want to add some messages inside your code, 'cause you can just call:

```python
app.log.debug('This is a debug message')
app.log.info('This is an info message')
app.log.warning('This is a warning message')
```

Basically the `log` attribute of your app is a python `Logger` with some handlers configured. As we stated above, weppy automatically logs exceptions calling your `app.log.exception()`.

### Configuring application logs
Probably you want to configure logging for your application under your needs. To do that, just use your `app.config` object:

```python
from weppy import App, sdict

app = App(__name__)

app.config.logging.myfile = sdict(
    level="info",
    max_size=100*1024*1024
)
```

With this example, you will end with a *myfile.log* which will grow till 100MB and log all messages with an *info* level or higher. This is the complete list of parameters you can set for a logging file:

| name | description |
| --- | --- |
| max_size | max size for the logging files (default `5*1024*1024`) |
| file_no | number of old files to keep with rotation (default `4`) |
| level | logging level (default `'warning'`) |
| format | format for messages (default `'[%(asctime)s] %(levelname)s in %(module)s: %(message)s'`) |
| on\_app\_debug | tells weppy to log the messages also when application is in debug mode (default `False`) |

That's it.
