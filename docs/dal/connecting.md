Connections and transactions
============================

In order to start using a database in weppy, you have to initialize an instance of the `DAL` class:

```python
from weppy import DAL

db = DAL(app)
```

As you will learn in the next chapters, this `DAL` instance will be fundamental to perform operations on your database, as it will be the access point to the data you store.

Connections
-----------

As we seen in the [first example](./), the `DAL` instance gives you a handler to register into your application:

```python
app.common_handlers = [db.handler]
```

This handler will ensure the connection to the database during the request flow and the disconnection when the response is ready. As a consequence, you don't need to bother about connecting/disconnecting in your application flow, unless you're explicit working without a request context.    
Even in that case, you won't have troubles in connecting to the database, since the `DAL` instance will automatically open up a connection after initialization. This means that, even if you import your `DAL` instance from the console, you will have the connection opened with your database.

If somehow you need to manually open and close the connection with your database, you can use the adapter methods:

```python
# manually open a connection
db._adapter.reconnect()
# manually close the active connection
db._adapter.close()
```


Configuration
-------------

As you've seen from the example above, `DAL` class needs your application object as the first parameter, and reads the configuration from its `config` object.

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

### Passing explicit config to DAL

`DAL` class also accepts a specific config object that become particularly handy in situations where you have multiple databases in your application:

```python
app.config.db.uri = "postgres://localhost/mydb"
app.config.db2.uri = "mongodb://localhost/mydb"

db = DAL(app)
db2 = DAL(app, app.config.db2)
```

### Additional configuration parameters

`DAL` class accepts several configuration parameters, here we list them in detail:

| parameter | default | description |
| --- | --- | --- |
| pool_size | 0 | the pool size to use when connecting to the database |
| auto_migrate | `True` | turns on or off the automatic migration |
| folder | `databases` | the folder relative to your application path where to store the database (when using sqlite) and/or support data |
| adapter_args | `{}` | specific options for the pyDAL adapter |
| driver_args | `{}` | specific options for the driver |

Note that when you don't specify any `pool_size` value, weppy won't use any pool when connecting to the database, but just one connection.

Also, when the `auto_migrate` option is set to `False`, weppy won't migrate your data when you will made changes to your models, and requires you to generate migrations with the appropriate command or write down your own migrations. Please checkout the [appropriate section](./migrations) of the documentation for additional details.

Transactions
------------

As we seen above, the handler of your `DAL` instance will ensure the connection to the database during the request flow; but it's also responsible of the transactions during this flow.    
In fact, the handler treats the request as a single database transaction, ensuring the commit of the changes if the request had success. Otherwise, in the case of un-catched exceptions (resulting in a 500 HTTP error response), the handler will perform a rollback on the database data.

Since the handler is used only in a request context, every time you work without it you should commit or rollback your changes (also when you're working in the console), using the available methods of the `DAL` instance:

```python
# commit all the changes
db.commit()
# discard all the changes
db.rollback()
```

You can obviously use them also in the application code during the request in order to have a better control of what happens with your data. Just remember that when you call `commit()` or `rollback()` you're in fact ending the last transaction and starting a new one.
