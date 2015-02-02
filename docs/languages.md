Languages and internationalization
==================================

weppy provides an integrated powerful multi-language system, based on the *web2py's* one, which helps you to write application supporting different languages.   
But how does it work?

```python
from weppy import App, T
app = App(__name__)

@app.route("/")
def index():
    hello = T('Hello, my dear!')
    return dict(hello=hello)
```

As you can see, weppy provide a language translator with the `T` object: this is available also into the templating environment, and it tells weppy to translate the string depending on clients locale.

So what you should do with languages? You can just write in *languages/it.py* file of your application:

```python
{
"Hello, my dear!": "Ciao, mio caro!"
}
```

and the hello message will be translated when the user request the italian language. 

> – awesome. But how weppy decides which language should load for a specific client?   
> – *actually, you can choose that*

weppy has two different ways to handle languages in your application: using clients' HTTP headers or using urls. Let's see the differences between the two systems.

Translation using HTTP headers
------------------------------

Let's say your application has english as default language and you want your application to be available also in italian language, as the above example.   
On default settings, the user's requested language is determined by the "Accept-Language" field in the HTTP header, which means that if *user1* has its browser accepting italian language, visiting 'http://127.0.0.1:8000/' he will see the italian version, while *user2* that has its browser accepting any other language different from italian will see the english one.

As you imagined, using this translation technique is quite easy, as the available languages are automatically defined based on the translation files you have inside *languages* folder of your application. For example

```
/myapp
    /languages
         it.py
```

will make your application available in english and italian, while

```
/myapp
    /languages
        it.py
        es.py
```

will make your application available in english, italian and spanish.

You can obviously change the default language of your application, just writing:

```python
app.language_default = 'it'
```

Translation using routing
-------------------------

There are many scenarios where you want your application to use different urls to separate contents depending on the language.

Let's say again you have your application with english as the default language and you provide also an italian version; to achieve the routing translation behavior under weppy you should write:

```python
app.languages = ['en', 'it']
app.language_default = 'en'
app.language_force_on_url = True
```
and weppy will automatically add the support for language on your routing rules to the follow:

| requested url | behaviour |
| --- | --- |
| /anexampleurl | shows up the contents with the default language |
| /it/anexampleurl | shows up the contents with the italian language |

As you can see, the *routing* way needs you to explicitly tells to weppy which languages should be available into your application so it can build the routing tables.
