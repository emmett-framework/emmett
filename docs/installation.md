
Installation
============

So, how do you get Emmett on your computer quickly? There are many ways you could do that, but the most kick-ass method is virtualenv, so let’s have a look at that first.

You will need Python version 3.7 or higher in order to get Emmett working.

virtualenv
----------

Virtualenv is probably what you want to use during development, and if you have shell access to your production machines, you’ll probably want to use it there, too.

What problem does virtualenv solve? If you use Python a bit, you'll probably want to use it for other projects besides Emmett-based web applications. However, the more projects you have, the more likely it is that you will be working with different versions of Python itself, or at least different versions of Python libraries. Let’s face it: quite often, libraries break backwards compatibility, and it’s unlikely that any serious application will have zero dependencies. So what do you do if two or more of your projects have conflicting dependencies?

Virtualenv to the rescue! Virtualenv enables multiple side-by-side installations of Python, one for each project. It doesn’t actually install separate copies of Python, but it does provide a clever way to keep different project environments isolated.   
Let’s see how virtualenv works.

#### virtualenv on Python 3

You can just initialize your environment in the *.venv* folder using:

```bash
$ mkdir -p myproject
$ cd myproject
$ python -m venv .venv
```

### Installing Emmett on virtualenv

Now, whenever you want to work on a project, you only have to activate the corresponding environment. On OS X and Linux, you can do the following:

```bash
$ source .venv/bin/activate
```

You should now be using your virtualenv (notice how the prompt of your shell has changed to show the active environment).

Now you can just enter the following command to get Emmett activated in your virtualenv:

```bash
$ pip install emmett
```

And now you are good to go.

You can read more about virtualenv on [its documentation website](https://docs.python.org/3/library/venv.html).
