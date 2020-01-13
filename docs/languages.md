Languages and internationalization
==================================

Emmett provides *Severus* as its integrated internationalization engine for managing multiple languages in your application. How does it work?

```python
from emmett import App, T
app = App(__name__)

@app.route("/")
async def index():
    hello = T('Hello, my dear!')
    return dict(hello=hello)
```

As you can see, Emmett expose a language translator with the `T` object.
It tells Emmett to translate the string depending on clients locale, and is also available in the templating environment.

So what you should do with the other languages' text? You can just leave it in *json* or *yaml* files within a *languages* directory. Each file should be named after the international symbol for the language. For example, an Italian translation should be stored as *languages/it.json*:

```json
{
    "Hello, my dear!": "Ciao, mio caro!"
}
```

and the hello message will be translated when the user request the Italian language. 

> – awesome. Though, how does Emmett decides which language should be loaded for
a specific client?   
> – *actually, you can choose that*

Emmett has two different ways to handle languages in your application:

* using clients' HTTP headers
* using URLs

Let's see the differences between the two systems.

Translation using HTTP headers
------------------------------

Let's say your application has English for its default language and you want your application to also be available in Italian, as the above example.   
With default settings, the user's requested language is determined  by the "Accept-Language" field in the HTTP header. This means that if *User 1* has their browser set to accept Italian, he will see the Italian version when visiting 'http://127.0.0.1:8000/'. Meanwhile, if *User 2* has their browser set for any other language, they will see the english one.

Using this translation technique is quite easy. The available languages are
defined automatically, based on the translation files you have inside *languages*
folder of your application. 

```
/myapp
    /languages
        it.json
```

will make your application available in Italian in addition to the English written in your templates and exposed functions.

Simply add more translation programs to increase your multi-language support:

```
/myapp
    /languages
        it.json
        es.yaml
```

will make your application available in English, Italian and Spanish.

You can change the default language of your application with the following line in the file where you wrote your application's exposed functions:

```python
app.language_default = 'it'
```

Translation using routing
-------------------------

There are many scenarios where you want your application to use different URLs to separate contents based on the language.

Let's say again you have your application with English as the default language and you provide a supplementary Italian version; to achieve the routing translation behavior under Emmett, you should write:

```python
app.languages = ['en', 'it']
app.language_default = 'en'
app.language_force_on_url = True
```
and Emmett will automatically add the support for language on your routing rules to the follow:

| requested URL | behaviour |
| --- | --- |
| /anexampleurl | shows up the contents with the default language |
| /it/anexampleurl | shows up the contents with the italian language |

As you can see, the *routing* way requires that you to explicitly tell to Emmett which languages should be available into your application, so it can build the routing tables.
