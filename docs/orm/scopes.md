Filter data with scopes
=======================

As we saw in the [previous chapter](./operations), Emmett allows you to write queries easily using python objects.

Still, sometimes, it might be handy to have some shortcuts for the queries we write more often in our application, or to have some helpers that allow us to write less code.

In order to address this need, Emmett implements *scopes*, special methods inside models that will be bound to models themselves and to sets matching the involved tables.

But how do they work?    
Let's say, for example, that you're writing some blog application, where every post can be in a different state, like when is just a draft, or is published, or maybe retired. Let's say that you're mapping this *state* with an *integer* column, and you're ending up with a model like this:

```python
class Post(Model):
    title = Field()
    body = Field.text()
    created_at = Field.datetime()
    changed_at = Field.datetime()
    state = Field.int()

    STATES = {'draft': 0, 'published': 1, 'retired': 2}

    validation = {
        'state': {'in': {
            'set': list(STATES.values()), 
            'labels': list(STATES)}}
    }
```

Now, if you often works with published posts, you will probably ending up writing a lot of lines like this:

```python
db((Post.state == 0) & (...))
# or
db(Post.state == Post.STATES['published']).where(...)
```

And since this can be quite annoying, you can write a scope in your model:

```python
from emmett.orm import scope

class Post(Model):
    @scope('published')
    def filter_published(self):
        return self.state == self.STATES['published']
```

as you can see the scope we just write is a method returning the query we need to be applied. Now, we are able to use it as a method with the name we specified in the argument of the `scope` decorator:

```python
>>> Post.published()
<Set (posts.state = 1)>
>>> db(Post.created_at >= datetime(2016, 1, 15)).published()
<Set ((posts.created_at >= '2016-01-15 00:00:00') AND (posts.state = 1))>
>>> Post.published().where(Post.created_at >= datetime(2015, 12, 10))
<Set ((posts.state = 1) AND (posts.created_at >= '2015-12-10 00:00:00'))>
```

As you can see you can use scopes on the model classes and on `Set` object for the model table, and combine them with other query conditions.

Scopes with arguments
---------------------

Since scopes are methods, they can obviously accepts arguments. This becomes quite handy when you want to use scopes to build often used queries with some variables.

Considering the posts example we've seen above, if you often works with time and date ranges, then repeatedly writing this:

```python
db(
   (Post.created_at >= datetime(2016, 1, 15)) &
   (Post.created_at < datetime(2016, 1, 16))
) 
```

can be uncomfortable. You can instead write a scope for that:

```python
class Post(Model):
    @scope('between')
    def filter_between(self, start, end):
        return (self.created_at >= start) & (self.created_at < end)
```

Then in your application code you can write the cleaner:

```python
Post.between(datetime(2016, 1, 15), datetime(2015, 1, 16))
```

Using arguments in scopes can be handy also when you want to keep your routed functions cleaner and keep the filtering logic into the models. Let's consider another example and suppose that you're writing a todo manager application where you want to allow the filtering of the todos with a query parameter for a specific state of the todos. Given the model:

```python
class Todo(Model):
    action = Field()
    done = Field.bool()
    overdue_at = Field.datetime()
```

we want to make available these states using a *filter* query parameter:

- *done* for the completed todos
- *overdue* for the todos with an overdue date prior than now
- *upcoming* for the todos with an overdue date in the next 7 days

Then we can add to our model:

```python
from datetime import timedelta
from emmett import request

class Todo(Model):
    permitted_filters = ['done', 'overdue', 'upcoming']

    @scope('with_state')
    def filter_by_state(self, state):
        if state == 'done':
            return self.done == True
        elif state == 'overdue':
            return self.overdue_at < request.now
        elif state == 'upcoming':
            d = request.now.date()
            return (self.overdue_at >= d+timedelta(days=1)) & \
                (self.overdue_at < d+timedelta(days=7))
```

and write down a routing function like this:

```python
from emmett import request

@app.route()
async def todos():
    dbset = Todo.all()
    if request.query_params.filter in Todo.permitted_filters:
        dbset = dbset.with_state(request.query_params.filter)
    return {'todos': dbset.select(paginate=1)}
```

then your can provide filtering just using the urls:

- /todos?filter=done
- /todos?filter=overdue
- /todos?filter=upcoming

Combining scopes
----------------

Scopes can be combined to build a `Set` corresponding to the intersection of their queries, so that the resulting set of records will be the same of concatenating queries with the `&` operator.

Considering back the posts example we given before, you can write:

```python
Post.published().between(
    datetime(2016, 1, 15), datetime(2016, 1, 16))
```

that will produce the same result of writing the respective queries:

```python
Post.where(
    lambda p: 
        (p.state == Post.STATES['published']) &
        (p.created_at >= datetime(2015, 1, 15)) &
        (p.created_at < datetime(2015, 1, 16))
)
```
