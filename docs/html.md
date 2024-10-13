HTML without templates
======================

As we saw in the [templates chapter](./templates), Emmett comes with a template engine out of the box, which you can use to render HTML.

Under specific circumstances though, it might be convenient generating HTML directly in your route code, using the Python language. To support these scenarios, Emmett provides few helpers under the `html` module. Let's see them in details.

The `tag` helper
----------------

The `tag` object is the main interface provided by Emmett to produce HTML contents from Python code. It dinamically produces HTML elements based on its attributes, so you can produce even custom elements:

```python
from emmett.html import tag

# an empty <p></p>
p = tag.p()
# a custom element <card></card>
card = tag.card()
# a custom element <list-item></list-item>
list_item = tag["list-item"]()
```

Every element produced by the `tag` helper accepts both nested contents and attributes, with the caveat HTML attributes needs to start with `_`:

```python
# <p>Hello world</p>
p = tag.p("Hello world")
# <div class="foo"><p>bar</p></div>
div = tag.div(tag.p("bar"), _class="foo")
```

> **Note:** the reasons behind the underscore notation for HTML attributes are mainly:    
> - to avoid issues with Python reserved words (eg: `class`)    
> - to keep the ability to set custom attributes on the HTML objects in Python code but prevent those attributes to be rendered

Mind that the `tag` helper already takes care of *self-closing* elements and escaping contents, so you don't have to worry about those.

> – That's cool dude, but what if I need to set several attributes with the same prefix?   
> – *Like with HTMX? Sure, just use a dictionary*   

```python
# <button hx-post="/clicked" hx-swap="outerHTML">Click me</button>
btn = tag.button(
    "Click me",
    _hx={
        "post": url("clicked"),
        "swap": "outerHTML"
    }
)
```

The `cat` helper
----------------

Sometimes you may need to stack together HTML elements without a parent. For such cases, the `cat` helper can be used:

```python
from emmett.html import cat, tag

# <p>hello</p><p>world</p>
multi_p = cat(tag.p("hello"), tag.p("world"))
```

Building deep stacks
--------------------

All the elements produced with the `tag` helper supports `with` statements, so you can easily manage even complicated stacks. For instance the following code:

```python
root = tag.div(_class="root")
with root:
    with tag.div(_class="lv1"):
        with tag.div(_class="lvl2"):
            tag.p("foo")
            tag.p("bar")

str(root)
```

will produce the following HTML:

```html
<div class="root">
    <div class="lvl1">
        <div class="lvl2">
            <p>foo</p>
            <p>bar</p>
        </div>
    </div>
</div>
```

> **Note:** when compared to templates, HTML generation from Python will be noticeably slower. For cases in which you want to render long and almost static HTML contents, using templates is preferable.
