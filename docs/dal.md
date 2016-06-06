Using databases
===============

> – OK, what if I need to use a database in my application?   
> – *you can use the included ORM*

weppy comes with an integrated ORM based on [pyDAL](https://github.com/web2py/pydal),
which gives you the ability to use a database in your application writing simple
Python code without worrying about queries and specific syntax of the database
engine you want to use.   

Thanks to this database layer, you can write the same code and use the same syntax
independently of which of the available adapters you want to use during development
or when you're deploying your app to the world.

This is the list of the supported database engines, where we included the appropriate
driver(s) you need to install, separately from weppy (just use pip):

| Supported DBMS | python driver(s) |
| --- | --- |
| SQLite | sqlite3, pysqlite2, zxjdbc |
| PostgreSQL | psycopg2, pg8000, zxjdbc |
| MySQL | pymysql, mysqldb |
| Oracle | cxoracle |
| MSSQL | pyodbc |
| FireBird | kinterbasdb, fdb, pyodbc |
| DB2 | pyodbc |
| Informix | informixdb |
| Ingres | ingresdbi |
| Cubrid | cubridb |
| Sybase | Sybase |
| Teradata | pyodbc |
| SAPDB | sapdb |
| MongoDB | pymongo |

> **Note:**   
> This list may change, and depends on the engine support of pyDAL. For any
further information, please check out the [project page](https://github.com/web2py/pydal).

So, how do you use weppy's ORM? Let's see it with an example:

```python
from weppy import App
from weppy.dal import DAL, Model, Field

app = App(__name__)
app.config.db.uri = "sqlite://storage.sqlite"

class Post(Model):
    author = Field()
    title = Field()
    body = Field('text')

db = DAL(app)
db.define_models(Post)

app.common_handlers = [db.handler]

@app.route('/posts/<str:author>')
def post_by(author):
    posts = db(Post.author == author).select()
    return dict(posts=posts)
```

The above code is quite simple: the `post_by()` function lists posts from a
specific author. Let's retrace what we done in those simple lines:

* we added an *sqlite* database to our application, stored on file *storage.sqlite*
* we defined the *Post* model and its properties, which will create a *posts* table
* we registered the database handler to our application so that it will be available during requests
* we did a select on the *posts* table querying the *author* column

As you noticed, the fields defined for the table are available for queries as
attributes, and calling *db* with a query argument provides you a set on
which you can do operations like the `select()`.

In the next chapters, we will inspect how to define models, all the available options,
and how to use weppy's ORM to perform operations on the database. 
