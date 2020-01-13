Connections and transactions
============================

In order to start using a database in Emmett, you have to initialize an instance of the `Database` class:

```python
from emmett.orm import Database

db = Database(app)
```

As you will learn in the next chapters, this `Database` instance will be fundamental to perform operations on your database, as it will be the access point to the data you store.

Connections
-----------

As we seen in the [first example](./), the `Database` instance gives you a pipe to be registered into your application pipeline:

```python
app.pipeline = [db.pipe]
```

This pipe will ensure the connection to the database during the request flow and the disconnection when the response is ready. As a consequence, you don't need to bother about connecting/disconnecting in your application flow, unless you're explicit working without a request context.    
Even in that case, you won't have troubles in connecting to the database, since the `Database` instance will automatically open up a connection after initialization. This means that, even if you import your `Database` instance from the console, you will have the connection opened with your database.

In the case you need to manually open and close the connection with your database, for example in test suites, you have two possibilities. You can use a `with` block:

```python
with db.connection():
    # some code dealing with database
```

or the explicit open and close methods:

```python
# manually open a connection
db.connection_open()
# manually close the active connection
db.connection_close()
```


Configuration
-------------

As you've seen from the example above, `Database` class needs your application object as the first parameter, and reads the configuration from its `config` object.

The minimal configuration needed is the database address to connect to, and you can pass it directly as uri, for example:

```python
# with a local sqlite database:
app.config.db.uri = 'sqlite://filename.sqlite'
# with a remote postgre database with auth access:
app.config.db.uri = 'postgres://username:yourpassword@localhost/database'
```

Or you can set all the connection details in the config object:

```python
app.config.db.adapter = 'postgres'
app.config.db.host = 'localhost'
app.config.db.user = 'username'
app.config.db.password = 'yourpassword'
app.config.db.database = 'database'
```

This becomes useful when you're using yaml config files and/or environment dependencies, as you can write down your *db.yml* file in a *config* folder:

```yaml
adapter: postgres
host: localhost
user: username
password: yourpassword
database: databasename
```

and then do:

```python
app.config_from_yaml('db.yml', 'db')
```

where the first parameter is the filename and the second is the attribute to be set in the application config.

### Passing explicit config to Database

`Database` class also accepts a specific config object that become particularly handy in situations where you have multiple databases in your application:

```python
app.config.db.uri = "postgres://localhost/mydb"
app.config.db2.uri = "mongodb://localhost/mydb"

db = Database(app)
db2 = Database(app, app.config.db2)
```

### Additional configuration parameters

*Changed in version 1.3*

`Database` class accepts several configuration parameters, here we list them in detail:

| parameter | default | description |
| --- | --- | --- |
| pool_size | 0 | the pool size to use when connecting to the database |
| keep\_alive\_timeout | 3600 | the maximum interval in seconds a connection can be recycled in the pool |
| auto\_connect | `None` | automatically connects to the DBMS on init |
| auto\_migrate | `False` | turns on or off the automatic migration |
| big\_id\_fields | `False` | uses big integer fields for id and reference columns |
| folder | `databases` | the folder relative to your application path where to store the database (when using sqlite) and/or support data |
| adapter\_args | `{}` | specific options for the pyDAL adapter |
| driver\_args | `{}` | specific options for the driver |

Note that when you don't specify any `pool_size` value, Emmett won't use any pool when connecting to the database, but just one connection.

Also, when the `auto_migrate` option is set to `False`, Emmett won't migrate your data when you will made changes to your models, and requires you to generate migrations with the appropriate command or write down your own migrations. Please checkout the [appropriate section](./migrations) of the documentation for additional details.

Transactions
------------

As we seen above, the pipe of your `Database` instance will ensure the connection to the database is alive during the request flow; but it's also responsible of the transactions during this flow.    
In fact, the pipe treats the request as a single database transaction, ensuring changes are committed if the request succeeded. Otherwise, in the case of un-catched exceptions (resulting in a 500 HTTP error response), the pipe will perform a rollback on the database data.

Since the pipe is used only in a request context, every time you work without it you should commit or rollback your changes (also when you're working in the console), using the available methods of the `Database` instance:

```python
# commit all the changes
db.commit()
# discard all the changes
db.rollback()
```

You can obviously use them also in the application code during the request in order to have a better control of what happens with your data. Just remember that when you call `commit()` or `rollback()` you're in fact ending the last transaction and starting a new one.

### Nested transactions

*New in version 1.2*

Emmett also supports working with nested transactions. A few methods are available for the purpose, and the most general is `atomic`. These blocks will be run in a transaction or in a savepoint, depending on the nesting level:

```python
# This code runs in a transaction
User.create(username='walter')
with db.atomic():
    # This block corresponds to a savepoint.
    User.create(username='olivia')
    # This will roll back the above create() command.
    db.rollback()
User.create(username='william')
db.commit()
```

At the last commit, the outer transaction is committed. At that point there will be two users, "walter" and "william".

> **Note:** remember that Emmett `Database` class will automatically start a transaction after connection.

In the case you want to explicitly use a transaction or a savepoint, you may also use the specific methods `transaction` and `savepoint`:

```python
with db.transaction() as txn:
    # some code
    with db.savepoint() as sp:
        # some code
```

All the code blocks running in `atomic`, `transaction` and `savepoint` will commit changes at the end unless an exception occurs within the block. In that case, the block will issue a rollback and the exception will be raised.

> **Note:** the savepoint support relies on the adapter you configured. Please check your specific DBMS for this feature support.
