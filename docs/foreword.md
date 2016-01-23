
Foreword
========

When I started writing web applications, the first "big decision" I faced was the choice of the programming language.   
As a programmer, it's not a big deal to work with different languages, and switching from a language to another, apart from learning a bit of syntax, shouldn't be too hard; at the same time everybody needs pick a language to use as a *daily habit*, we are humans after all.

I wanted a dynamic language to write my applications, a language with an easier syntax than php, and more structured than javascript; I wanted something that allowed me to write that *little magic* every developer does behind the scenes in a handy way. And I finally chosen Python. Ruby was on the list (and it seems quite popular for the web development nowadays), but I've found its syntax, in some situation, less immediate; moreover python is someway more *solid* compared to Ruby – maybe even too much solid, I think even Python will take some advantages from a more dynamic community, just think about Python3 adoption status (Ed.).

I really enjoyed writing code in Python, and after taking confidence a bit, I faced the second "big decision": the framework to use to write my applications.   
Looking at the Python scene, I (obviously) started looking ad *django*, as the most famous one, but after a while I found I didn't like it, it wasn't user friendly as I hoped. Then I found *web2py*, and I loved it since the first line of the documentation book: it was simple, full of features and learning it was so quicker compared to *django*.

After some years using *web2py*, nevertheless, and inspecting deeply the code and it's logic, contributing it, I started having a feeling, a need grew up in my mind while writing applications, to write things differently. I found myself thinking "why should I write this stuff in *this* way? It's not cool or handy at all", and I had to face the problem that what I wanted would meant to completely re-design the whole framework.   
With this nagging feeling in my mind, I started looking around and found that a lot of syntax and logics in *Flask* were the answer to what I was looking for. Unfortunately, at the same time *Flask* had a huge lack of features I was used to have in the box with *web2py*, and even using extensions would not have been enough to cover it all.   
And I naturally came up to the conclusion that I was at *that point* of my coding life where you need a "custom-designed tool".

Why not?
--------

> – Hey dude, what you're doing?   
> – *writing a new python web framework..*   
> – Woah! Why you do that?   
> – *..why not?*

That was my answer when a friend of mine asked me the reasons behind my intention of building a new framework. But it was a legit question: there are many frameworks on the scene, is it really a good move to build a new tool rather than picking one of the available ones?   
I'd like to reply this doubt starting with a definition of *tool* I really love:

> **tool:** *something* intended to make a task easier.

So a framework, which is a tool, has by definition to let you write your application **easier** than without it. Now, I've found many frameworks – and I'm sure you can easily find them too – where you have to deal *a lot* with learning "how to do that" with the framework itself instead of focusing on the application.

This is the first principle I've based *weppy* on: it's easy to use and learn, so that you can focus on **your** product.   
Another key principle of *weppy* is the *preservation of the control* over the flow. What does it mean?   
There are several frameworks that do too much *magic* behind the scenes. I know that may sound weird because I've just talked about simplicity, but, if you think about it, you will find that a simple to use framework is not necessarily the one which hides a lot of his flow.   
As developers, we have to admit that when we use frameworks or libraries for our project, many times is hard to do something out of the ready-made scheme. I can think about several frameworks – even the famous *Ruby on Rails* – that, from time to time, force you to use a lot of formalism even when it's not really necessary, and you end up finding yourself writing code following useless rules you don't like.   
In other words: I like magic too, but isn't cool when you actually *control* the magic?

With these principles in mind, I've tried to build a complete tool, which means, let me repeat that again, something let you write applications *easier*, with a rich set of features in the box. The result of my recipe, is a framework which has an easy syntax, similar to *Flask*, but which also includes some of the lovable features of *web2py*.   
I hope you like it.

Acknowledgments
---------------

I would like to thank:

* All the **weppy contributors**
* **Guido Van Rossum**, for the Python language
* **Massimo Di Pierro** and **web2py's developers**, for what I learned from them and for their framework on which I based weppy
* **Armin Ronacher**, who really inspired me with the Flask framework
* **Marco Stagni**, **Michael Genesini** and **Filippo Zanella** for their advices and continuous support
