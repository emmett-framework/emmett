
Installation
============

So, how do you get weppy on your computer quickly? There are many ways you could do that, but the most kick-ass method is virtualenv, so let’s have a look at that first.

You will need Python 2.6 or higher to get started, so be sure to have an up-to-date Python 2.x installation. At the moment weppy is not supporting Python 3, but stay tuned and follow up the project on github for the Python 3 Support.

virtualenv
----------

Virtualenv is probably what you want to use during development, and if you have shell access to your production machines, you’ll probably want to use it there, too.

What problem does virtualenv solve? If you use Python a bit, you probably want to use it for other projects besides weppy-based web applications. But the more projects you have, the more likely it is that you will be working with different versions of Python itself, or at least different versions of Python libraries. Let’s face it: quite often libraries break backwards compatibility, and it’s unlikely that any serious application will have zero dependencies. So what do you do if two or more of your projects have conflicting dependencies?

Virtualenv to the rescue! Virtualenv enables multiple side-by-side installations of Python, one for each project. It doesn’t actually install separate copies of Python, but it does provide a clever way to keep different project environments isolated.   
Let’s see how virtualenv works.

If you are on Linux or Mac OS X, one of the following two commands should work for you:

```bash
$ sudo easy_install virtualenv
```

or even better:

```bash
$ sudo pip install virtualenv
```

Once you have virtualenv installed, just fire up a shell and create your own environment.   
An easy way is to create a project folder and a venv folder within:

```bash
$ mkdir myproject
$ cd myproject
$ virtualenv venv
New python executable in venv/bin/python
Installing distribute............done.
```

Now, whenever you want to work on a project, you only have to activate the corresponding environment. On OS X and Linux, you can do the following:

```bash
$ . venv/bin/activate
```

You should now be using your virtualenv (notice how the prompt of your shell has changed to show the active environment).

Now you can just enter the following command to get weppy activated in your virtualenv:

```bash
$ pip install weppy
```

and now you are good to go.
