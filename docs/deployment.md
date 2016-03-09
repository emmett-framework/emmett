Deployment
==========

Depending on your setup and preferences, there are multiple ways to run weppy
applications. In this chapter, we'll try to document the most common ones.

As a note, please remember that even though weppy provides a built in server,
and it's quite good and handy for your development process,
its usage in production is **highly discouraged**.

If you want to use a WSGI server not listed in this section, 
please refer to its documentation, remembering that your weppy application object
is the actual WSGI application.

uWSGI with nginx
----------------
The recommended option to deploy weppy is actually using [uwsgi](http://projects.unbit.it/uwsgi/)
with *nginx* web server.

nginx is available as a package on almost every Linux distribution, while uWSGI
can be installed via pip:

```bash
$ pip install uwsgi
```

### Running your application with uWSGI
Given a weppy application in myapp.py or in myapp package, you can run it like so:

```bash
$ uwsgi -s /tmp/app.sock -w myapp:app
```

If you have a virtual environment for your app, you can use it with uWSGI too:

```bash
$ uwsgi -s /tmp/app.sock -w myapp:app -H /path/to/my/venv
```

### uWSGI emperor
*section under writing*

### Configuring nginx
Once you have configured nginx properly and have a `server` object in your configuration,
simply add the next lines, updated with your data:

```
location / {
    uwsgi_pass unix:/tmp/app.sock;
    include uwsgi_params;
}

# serve static files with nginx
location ~ ^/(\w+)/static(?:/_[\d]+.[\d]+.[\d]+)?/(.*) {
    try_files /static/$1/$2 /static/$2;
    expires 30d;
}
location ~ ^/static(?:/_[\d]+.[\d]+.[\d]+)?/(.*) {
    alias /path/to/myapp/static/$1;
    expires 30d;
}
```

Now you should have your application successfully deployed with nginx and uWSGI.
