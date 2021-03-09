Command Line Interface
======================

Emmett provides a built-in integration of the [click](http://click.pocoo.org) command line interface, to implement and allow customization of command line scripts.

Basic Usage
-----------

Emmett automatically installs a command `emmett` inside your virtualenv. The way this helper works is by providing access to all the commands on your Emmett application's instance, as well as some built-in commands that are included out of the box. Emmett extensions can also register more commands there if they desire to do so.

For the `emmett` command to work, an application needs to be discovered. Emmett tries to automatic discover your application in the current working directory. In case Emmett fails to automatically detect your application, you can tell Emmett which application it should inspect, use the `--app` / `-a` parameter. It should be the import path for your application or the path to a Python file.

Given that, to run a development server for your application, you can just write in your command line:

```bash
> emmett develop
```

or, in the case of a single-file app:

```bash
> emmett -a myapp.py develop
```

Running a Shell
---------------

To run an interactive Python shell, you can use the `shell` command:

```bash
> emmett shell
```

This will start up an interactive Python shell, setup the correct application context and setup the local variables in the shell. By default, you have access to your `app` object, and all the variables you defined in your application module.

Custom Commands
---------------

If you want to add more commands to the shell script, you can do this easily.   
In fact, if you want a shell command to setup your application, you can write:

```python
from emmett import App

app = App(__name__)

@app.command('setup')
def setup():
    # awesome code to initialize your app
```

The command will then be available on the command line:

```bash
> emmett setup
```

### Command groups

*New in version 2.2*

You might also want to define several commands within the same *logical group*. In this scenario, the `command_group` decorator is what you're looking for:

```python
@app.command_group('tasks')
def tasks_cmd():
    pass


@tasks_cmd.command('create')
def tasks_create_cmd():
    # some code here
```

As you can see we defined a `tasks` command group, and a nested `create` command. We can invoke the upper command using:

    > emmett tasks create

In case you need more information, please check the [click documentation](https://click.palletsprojects.com/en/7.x/commands/) about commands and groups.
