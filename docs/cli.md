Command Line Interface
======================

weppy provides a built-in integration of the [click](http://click.pocoo.org)
command line interface, to implement and allow customization of command line scripts.

Basic Usage
-----------

weppy automatically installs a command `weppy` inside your virtualenv. The way
this helper works is by providing access to all the commands on your weppy
application's instance, as well as some built-in commands that are included
out of the box. weppy extensions can also register more commands there if they
desire to do so.

For the `weppy` command to work, an application needs to be discovered. To tell
weppy which application it should inspect, use the `--app` / `-a` parameter.
It should be the import path for your application or the path to a Python file.
In the latter case, weppy will attempt to setup the Python path for you automatically
and discover the module name, but there is a chance this may fail.

Given that, to run a development server for your application, you can just write
in your command line:

```bash
> weppy --app=myapp run
```

or, in the case of a single-file app:

```bash
> weppy --app=myapp.py run
```

Running a Shell
---------------

To run an interactive Python shell, you can use the `shell` command:

```bash
> weppy --app=myapp shell
```

This will start up an interactive Python shell, setup the correct application
context and setup the local variables in the shell. By default, you have access
to your `app` object, and all the variables you defined in your application module.

Custom Commands
---------------

If you want to add more commands to the shell script, you can do this easily.
In fact, if you want a shell command to setup your application, you can write:

```python
from weppy import App

app = App(__name__)

@app.command('setup')
def setup():
    # awesome code to initialize your app
```

The command will then be available on the command line:

```bash
> weppy --app=myapp setup
```
