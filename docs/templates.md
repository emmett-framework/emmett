The templating system
=====================

weppy provides the same templating system of *web2py*, which means that you can use python code directly into your HTML files.   
Let's see it with an example. We can make a new application with this structure:

```
/myapp.py
/templates
    echo.html
```
with *myapp.py* looking like this:

```python
from weppy import App
app = App(__name__)

@app.route("/<str:msg>")
def echo():
    return dict(message=msg)
```
and *echo.html*:

```html
<html>
    <body>
        {{=message}}
    </body>
</html>
```

The dictionary returned by your functions is the *context* of the template, in which you can insert the values defined in python code.   
In addition, since everything you write inside `{{ }}` brackets is evaluated as normal python code you can easily generate html with conditions and cycles:

```html
<div class="container">
{{for post in posts:}}
    <div class="post">{{=post.text}}</div>
{{pass}}
</div>
{{if user_logged_in:}}
<div class="cp">User cp</div>
{{pass}}
```

As you can see the only difference between the weppy template and a pure python code is that you have to write `pass` after the statements to tell weppy where the python block ends – normally we have indentation under python, but we can't have it under HTML.

Templates structure
-------------------

Templates can extend and include other ones in a tree-like structure. For example, we can think of a template *index.html* that extends *layout.html*. At the same time, *layout.html* may include a *footer.html*.

Writing down the code of what we just said would produce something like this for the *index.html*:

```html
{{extend 'layout.html'}}

<h1>Hello World, this is index</h1>
```

and for the *layout.html*:

```html
<html>
  <head>
    <title>Page Title</title>
  </head>
  <body>
    {{include}}
  </body>
  {{include 'footer.html'}}
</html>
```

When the template is parsed, the extended template is loaded, and the calling template replaces the `{{include}}` directive inside it. Moreover, the contents of *footer.html* will be loaded inside the parent template.

Using weppy templates you have another important feature: the `block` directive. Let's see how it works updating a bit the last example, with *index.html* looking like this:

```html
{{extend 'layout.html'}}

<h1>Hello World, this is index</h1>

{{block sidebar}}
sidebar by index
{{end}}
```

and *layout.html* like this:

```html
<html>
  <head>
    <title>Page Title</title>
  </head>
  <body>
    <div class="sidebar">
      {{block sidebar}}
        default layout sidebar
      {{end}}
    </div>
    {{include}}
  </body>
  {{include 'footer.html'}}
</html>
```

as you have guessed, the contents of the extended template's block are overwritten by the called template. Moreover, if you want to include the parent's content you can add a `{{super}}` directive.

Included helpers
----------------
There are other statements you can use in weppy templates: `include_static`, `include_meta` and `include_helpers`.

`include_static` allows you to add a static link for javascripts or stylesheet from your static folder:

```html
<html>
    <head>
        {{include_static 'myjs.js'}}
        {{include_static 'mystyle.css'}}
    </head>
</html>
```

`include_meta` adds to the *head* the meta you define in the `response` object, for more details about it check out the [appropriate chapter](#) of the documentation.

`include_helpers` adds to your template *jQuery* and an helping javascript from weppy. This javascript does 2 things:

* allow you to use the `load_component()` function described next
* adds a useful `ajax` javascript function to your template

The `ajax()` function from weppy is a convenient shortcut to the *jQuery* ajax function and it can be used as follows:

```javascript
ajax(url, ['name1', 'name2'], 'target')
```

It asynchronously calls the `url`, passes the values of the field inputs with the name equal to one of the names in the list, then stores the response in the innerHTML of the tag which id equals to `target`.

The third argument can also be the `:eval` string, which lead to the evaluation via javascript of the string returned by the server. Seen with an example, if we have an exposed function:

```python
@app.route()
def my_ajaxf():
    return "$('#target').html('something');"
```

and in a template:

```html
<div id="target"></div>
<script type="text/javascript">
    ajax({{=url('my_ajaxf'), [], ':eval'}});
</script>
```

You will se the 'something' content inside the div.

Basic context
-------------

weppy adds some useful python elements to your templates' base context, first of all the `current` object. This allows you to access the global objects of weppy and the language translator from your templates:

```python
current.request
current.response
current.session
current.T
```

Moreover, the templating system adds the `url()`, `asis()` and `load_component()` methods, where the `url()` is the same weppy method you've encountered to create urls for routed functions.

The `asis()` method allows you to put something in the template without escaping it to html. It's useful, for example, when you need to write javascript objects from python, like an array:

```html
<script type="text/javascript">
    var mylist = {{=asis([myvar, my2ndvar, my3rdvar])}};
</script>
```

where `myvar`, `my2ndvar` and `my3rdvar` comes from your python exposed function.

The `load_component()` method is useful to load some components via ajax in your template. For instance, if you have an exposed function in your application you want to load with ajax inside another one, you can just put in the template:

```html
<div id="ajaxcontainer">
    {{=load_component(url('my_ajaxf'), 'ajaxcontainer')}}
</div>
```

Basically, `load_component()` calls an url and appends it's contents inside the element with the id you have specified as the second parameter.


