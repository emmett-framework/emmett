
Foreword
========

When I started writing web applications, the first "big decision" I faced was the choice of the programming language.   

As a programmer, it's not a big deal to work with different languages, and switching from a language to another, shouldn't be too hard, apart from learning a bit of syntax; at the same time everybody needs pick a language  to use as a *daily habit*. We are humans, after all.

I wanted a dynamic language to write my applications, a language with an easier syntax than PHP, and more structured than JavaScript. I wanted something that allowed me to write that *little magic* every developer does behind the scenes in a handy way. And I finally chose Python. Ruby was on the list (it seemed quite popular for web development at the time), but I've found its syntax, in some situation, less immediate; moreover, Python is somewhat more *solid* than  Ruby – maybe even too much solid. I think even Python would be advantaged by a more dynamic community: just think about Python 3's adoption status (Ed.).

I really enjoyed writing code in Python, and after gaining some confidence, I faced the second "big decision": which framework to use to write my applications Looking at the Python scene, I (obviously) started looking at  *django*, the most famous one, but after a while I found I didn't like it. It wasn't as user friendly as I had hoped. Then I found *web2py*, and I loved it from the first line of the documentation book: it was simple, full of features, and learning it was much quicker than *django*.

Nevertheless, after some years of using *web2py*, inspecting deeply the code and logic, and contributing it, I started having a feeling. A need grew in my mind while writing applications, to write things differently. I found myself thinking "Why should I write this stuff in *this* way? It's not cool or handy at all," and I had to face the problem that doing what I wanted would involve completely re-designing the whole framework. 

With this nagging feeling in my mind, I started looking around and found that a lot of the syntax and logic in *Flask* were the answer to what I was looking for.   
Unfortunately, at the same time, *Flask* had a lacked many of the features I was used to having out of the box with *web2py*, and not even using extensions would have been enough to cover it all.   

I naturally came to the conclusion that I was at *that point* of my coding life where I needed a "custom-designed tool".

Why not?
--------

> – Hey dude, what are you doing?   
> – *writing a new python web framework..*   
> – Whoa! Why would you do that?   
> – *...why not?*

That was my answer when a friend of mine asked me the reasons behind my intention of building a new framework. It was a legitimate question: there are many frameworks on the scene. Is it really a good move to build a new tool rather than picking one of the available ones?   

I'd like to reply to this doubt with a definition of *tool* I really love:

> **tool:** *something* intended to make a task easier.

So a framework, which is a tool, has to let you write your application **easier** than without it. Now, I've found many frameworks – and I'm sure you can easily find them, too – where you have to deal with learning *a lot* of "how to do that" with the framework itself instead of focusing on the application.

This is the first principle I've based *Emmett* on: **it should be easy to use and learn, so that you can focus on *your* product.**   

Another key principle of *Emmett* is the *preservation of your control* over the flow. What do I mean? There are several frameworks that do too much *magic* behind the scenes. I know that may sound weird because I've just talked about simplicity, but, if you think about it, you will find that a framework that is simple to use is not necessarily one which hides a lot of his flow.   

As developers, we have to admit that when we use frameworks or libraries for our project, many times it is hard to do something out of the ready-made scheme. I can think about several frameworks – even the famous *Ruby on Rails* – that, from time to time, force you to use a lot of formalism even when it's not really necessary. You find yourself writing code while following useless rules you don't like.   

In other words: I like magic too, but **isn't cooler when you actually *control* the magic?**

With these principles in mind, I've tried to build a complete tool, something intended to make your task easier, with a rich set of features in the box.   
The result of my recipe is a framework which has an easy syntax, similar to *Flask*, but which also includes some of the lovable features of *web2py*.   

I hope you like it.

Acknowledgments
---------------

I would like to thank:

* All the **Emmett contributors**
* **Guido Van Rossum**, for the Python language
* **Massimo Di Pierro** and **web2py's developers**, for what I learned from them and for their framework on which I based Emmett
* **Armin Ronacher**, who really inspired me with the Flask framework
* **Marco Stagni**, **Michael Genesini** and **Filippo Zanella** for their advices and continuous support
