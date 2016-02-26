
Installation
============

So, how do you get weppy on your computer quickly? There are many ways you could do that, but the most kick-ass method is virtualenv, so let’s have a look at that first.

If you're using Python 2, you will need Python 2.7 or higher to get started, so be sure to have an up-to-date Python 2.x installation. On the other hand, if you're on Python 3, you will need version 3.3 or higher in order to get weppy working.

virtualenv
----------

Virtualenv is probably what you want to use during development, and if you have shell access to your production machines, you’ll probably want to use it there, too.

What problem does virtualenv solve? If you use Python a bit, you'll probably want to use it for other projects besides weppy-based web applications. However, the more projects you have, the more likely it is that you will be working with different versions of Python itself, or at least different versions of Python libraries. Let’s face it: quite often, libraries break backwards compatibility, and it’s unlikely that any serious application will have zero dependencies. So what do you do if two or more of your projects have conflicting dependencies?

Virtualenv to the rescue! Virtualenv enables multiple side-by-side installations of Python, one for each project. It doesn’t actually install separate copies of Python, but it does provide a clever way to keep different project environments isolated.   
Let’s see how virtualenv works.

### virtualenv on Python 2

If you are on Linux or Mac OS X, one of the following two commands should work for you:

```bash
$ sudo pip install virtualenv
```

or, if pip doesn't work:

```bash
$ sudo easy_install virtualenv
```

Once you have virtualenv installed, just fire up a shell and create your own environment.   
An easy way is to create a project folder and a venv folder within:

```bash
$ mkdir myproject
$ cd myproject
$ virtualenv venv --no-site-packages
New Python executable in venv/bin/python
Installing distribute............done.
```

### virtualenv on Python 3

With Python 3.3, virtualenv became part of the standard library. This means you won't need to install it anymore, and you can just initialize your environment:

```bash
$ mkdir myproject
$ cd myproject
$ pyvenv venv
```

### Installing weppy on virtualenv

Now, whenever you want to work on a project, you only have to activate the corresponding environment. On OS X and Linux, you can do the following:

```bash
$ source venv/bin/activate
```

You should now be using your virtualenv (notice how the prompt of your shell has changed to show the active environment).

Now you can just enter the following command to get weppy activated in your virtualenv:

```bash
$ pip install weppy
```

And now you are good to go.

You can read more about virtualenv on [its documentation website](https://virtualenv.readthedocs.org/en/latest/) (Python 2) or on the [Python 3 documentation](https://docs.python.org/3/library/venv.html) (python 3).
