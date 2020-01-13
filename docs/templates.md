The templating system
=====================

Emmett provides the *Renoir* templating engine, which means you can insert Python code in your HTML files directly.   

Let's see it with an example. We can make a new application with this structure:

```
/myapp.py
/templates
    echo.html
```

with *myapp.py* looking like this:

```python
from emmett import App
app = App(__name__)

@app.route("/<str:msg>")
async def echo(msg):
    return dict(message=msg)
```

and *echo.html*:

```html
<html>
  <body>
    {{ =message }}
  </body>
</html>
```

The dictionary returned by your functions is the *context* of the template,
in which you can insert the values defined in Python code by using the `{{=myvar}}` notation.

In addition, since everything you write inside the curly braces is evaluated
as normal Python code, you can easily generate HTML with conditions and cycles:

```html
<div class="container">
  {{ for post in posts: }}
  <div class="post">{{ =post.text }}</div>
  {{ pass }}
</div>
{{ if user_logged_in: }}
<div class="cp">User cp</div>
{{ pass }}
```

As you can see, the only difference between the Renoir template and pure Python
code is that you have to write `pass` after the statements to tell Emmett where 
the Python block ends. Normally, Python uses indentation for this, but HTML is
not structured the same way and just undoing the indentation would be ambiguous.

Template structure
-------------------

Templates can extend other templates in a tree-like structure. For example, 
we can think of a template *index.html* that extends *layout.html*.

### include

A structure like that would produce something like this for *index.html*:

```html
{{ extend 'layout.html' }}

<h1>Hello World, this is index</h1>
```

and for *layout.html*:

```html
<html>
  <head>
    <title>Page Title</title>
  </head>
  <body>
    {{ include }}
  </body>
  {{ include 'footer.html' }}
</html>
```

Note that *layout.html* may also include a *footer.html*. This action is
recursive. When the template is parsed, the extended template is loaded,
and the calling template replaces the `{{include}}` directive inside it.
The contents of *footer.html* will be loaded inside the parent template.

### block

Renoir templates have another important feature that accomplishes the same task
as include, but in a different way: the `block` directive. Let's see how it
works by updating the last example, with *index.html* looking like this:

```html
{{ extend 'layout.html' }}

<h1>Hello World, this is index</h1>

{{ block sidebar }}
sidebar by index
{{ end }}
```

and *layout.html* like this:

```html
<html>
  <head>
    <title>Page Title</title>
  </head>
  <body>
    <div class="sidebar">
      {{ block sidebar }}
        default layout sidebar
      {{ end }}
    </div>
    {{ include }}
  </body>
  {{ include 'footer.html' }}
</html>
```

As you guessed, the contents of the extended template's block are
overwritten by the called template. Moreover, if you want to include the
parent's content you can add a `{{super}}` directive.

Included helpers
----------------
There are other statements you can use in Emmett templates: `include_static`, 
`include_meta` and `include_helpers`.

`include_static` allows you to add a static link for JavaScript or stylesheet
from your static folder:

```html
<html>
  <head>
    {{ include_static 'myjs.js' }}
    {{ include_static 'mystyle.css' }}
  </head>
</html>
```

`include_meta` adds to the *head* the meta you define in the `response` object,
for more details about it check out the [appropriate chapter](#) of the
documentation.

`include_helpers` adds to your template *jQuery* and an helping JavaScript from 
Emmett. This JavaScript does two things:

* allow you to use the `load_component()` function described next
* adds a useful `ajax` JavaScript function to your template

The `ajax()` function from Emmett is a convenient shortcut to the *jQuery* AJAX 
function and it can be used as follows:

```javascript
ajax(url, ['name1', 'name2'], 'target')
```

It asynchronously calls the `url`, passes the values of the field inputs with
the name equal to one of the names in the list, then stores the response in the
innerHTML of the tag with its id equal to `target`.

The third argument can also be the `:eval` string, which leads to the evaluation
via JavaScript of the string returned by the server. Seen with an example,
if we have an exposed function:

```python
@app.route()
async def my_ajaxf():
    return "$('#target').html('something');"
```

and in a template:

```html
<div id="target"></div>
<script type="text/javascript">
  ajax("{{ =url('my_ajaxf') }}", [], ':eval');
</script>
```

You will see the 'something' content inside the div.

Basic context
-------------

Emmett adds some useful Python elements to your templates' base context.
First of all, the `current` object. This allows you to access the global objects
of Emmett and the language translator from your templates:

```python
current.request
current.response
current.session
current.T
```

Moreover, the templating system adds the `url()`, `asis()` and `load_component()`
methods, where the `url()` is the same Emmett method you've encountered to create
URLs for routed functions.

All these methods are python powered, so when you need to use them in your template file, you have to put an `=` before them, as we saw in this chapter:

```html
<a href="{{ =url('someroute') }}">Some link</a>
<img src="{{ =url('static', 'img/foo.png) }}" />
```

Now, let's inspect the other methods more deeply.   
The `asis()` method allows you to put something in the template without escaping it to HTML. It's useful, for example, when you need to write JavaScript objects from Python, like an array:

```html
<script type="text/javascript">
    var mylist = {{ =asis([myvar, my2ndvar, my3rdvar]) }};
</script>
```

where `myvar`, `my2ndvar` and `my3rdvar` comes from your Python exposed function.

The `load_component()` method is useful for loading components via AJAX in
your template. If you have an exposed function in your application and
you want to load with AJAX inside another one, you can just put in the template:

```html
<div id="ajaxcontainer">
    {{ =load_component(url('my_ajaxf'), 'ajaxcontainer') }}
</div>
```

Basically, `load_component()` calls an URL and appends its contents inside the
element with the id you have specified as the second parameter.
