Helpers
=======

Helper funcitons used as shortcuts to assist with various tasks, such as a
quick HTTP response, streaming files, flashing messages, and
loading compontents .

`abort`: Aborts the current request and return an HTTP response with the
specified status code and body.

```python
from emmett import abort


@app.route('/post/<int:id>')
async def post(id):
    editor = request.query_params.editor
    if editor == 'markdown':
        # code
    elif editor == 'html':
        # code
    else:
        abort(404, 'Page not found')
```

`stream_file`: Streams a file from the applicaiton's root path to the client.

```python
from emmett import stream_file
from emmett.tools import service


@app.route('/settings/')
@service.json
async def posts(id):
    stream_file('static/storage.json')
```

`stream_dbfile`: Streams a file stored in a databse to the client.

```python
from emmett.helpers import stream_dbfile

stream_file(db, 'user.profile_picture.1234')
```

`flash`: Flashes a message to the next request.

```python
from emmett.helpers import flash


flash('Your changes have been saved successfully!', 'success')
```

`get_flashed_messages`: Retrieves and optionally filters flashed messages from
the session.

```python
from emmett.helpers import get_flashed_messages

messages = get_flashed_messages(with_categories=True)
for category, message in messages:
    print(f'{category}: {message}')
```

`load_compontent`: Generates an HTML `div` tag for dynamic content loading.
Accepts a URL, target ID, and content.

```python
from emmett.helpers import load_compontent

component = load_component(
    url='https://example.com/data',
    target='myComponent',
    content='Loading data...',
)
```

