Sending mails
=============

Sooner or later you will need to send mails to your users from your application. Emmett provides a simple interface to set up SMTP with your application and to send messages to your users.

Let's start configuring a simple mailer within our application:

```python
from emmett import App
from emmett.tools import Mailer

app = App(__name__)
app.config.mailer.sender = "nina@massivedynamic.com"

mailer = Mailer(app)
```

With just these lines the mailer is ready to send messages, using the local machine as the SMTP server and sending messages from the address *nina@massivedynamic.com*.

The mailer also accepts additional configuration parameters, here is the complete list:

| parameter | default value | description |
| --- | --- | --- |
| sender | `None` | the address to use for the *From* value |
| server | 127.0.0.1 | the SMTP host to use |
| port | 25 | the SMTP port to use |
| username | `None` | the username to authenticate with (if needed) |
| password | `None` | the password to authenticate with (if needed) |
| use\_tls | `False` | decide if TLS should be used |
| use\_ssl | `False` | decide if SSL should be used |

Now, let's see how to send messages.

Sending messages
----------------

We can create a simple message using the `mail` method of our mailer:

```python
message = mailer.mail(
    subject="Hello", 
    body="A very important message",
    recipients=["walter@massivedynamic.com"])
```

and add another recipient later:

```python
message.add_recipient("william@massivedynamics.com")
```

and when we are ready, we can just send it:

```python
message.send()
```

We can also create a message and send it directly:

```python
mailer.send_mail(
    subject="Hello", 
    body="A very important message",
    recipients=["walter@massivedynamic.com"])
```

or set an html content for the message:

```python
message.html = "<b>Testing</b>"
```

Attachments
-----------

Once you created a message, adding attachments is quite easy:

```python
msg = mailer.mail(subject="See this")

with open("image.png") as fp:
    msg.attach(filename="image.png", data=fp.read())

msg.recipients = ["walter@massivedynamic.com"]
msg.send()
```

> **Note:** The default encoding used by the mailer is utf-8.

Tests and suppression
---------------------

When you are testing your application, or if you are in a development environment, it’s useful to be able to suppress email sending. Still, you may want to test some message was generated in your code, and you want to catch it.

The mailer provide a `store_mails` method for this, so you can just write down:

```python
with mailer.store_mails() as outbox:
    mailer.send_mail(
        subject='testing', body='test', recipients=["foo@bar.com"])
    assert len(outbox) == 1
    assert outbox[0].subject == "testing"
```

and the mailer just avoid the *real sending* of the message.

If you want to totally disable email sending, you can use the `suppress` parameter in the configuration:

```python
app.config.mailer.suppress = True
```

This will completely disable message sending.
