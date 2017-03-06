# -*- coding: utf-8 -*-
"""
    weppy.tools.mailer
    ------------------

    Provides mail facilities for weppy.

    :copyright: (c) 2014-2017 by Giovanni Barillari

    Based on the code of flask-mail
    :copyright: (c) 2010 by Dan Jacob.

    :license: BSD, see LICENSE for more details.
"""

import smtplib
import time
from contextlib import contextmanager
from email import charset as _charsetreg
from email.encoders import encode_base64
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formatdate, formataddr, make_msgid, parseaddr
from functools import wraps
from .._compat import PY2, string_types, to_bytes, to_unicode
from ..libs.contenttype import contenttype
from ..extensions import Extension
from ..utils import cachedprop


if PY2:
    message_policy = None
else:
    from email import policy
    message_policy = policy.SMTP

_charsetreg.add_charset('utf-8', _charsetreg.SHORTEST, None, 'utf-8')


def _has_newline(line):
    if line and ('\r' in line or '\n' in line):
        return True
    return False


def sanitize_subject(subject, encoding='utf-8'):
    try:
        subject.encode('ascii')
    except UnicodeEncodeError:
        subject = Header(subject, encoding).encode()
    return subject


def sanitize_address(address, encoding='utf-8'):
    if isinstance(address, string_types):
        address = parseaddr(to_unicode(address))
    name, address = address
    name = Header(name, encoding).encode()
    try:
        address.encode('ascii')
    except UnicodeEncodeError:
        if '@' in address:
            localpart, domain = address.split('@', 1)
            localpart = str(Header(localpart, encoding))
            domain = domain.encode('idna').decode('ascii')
            address = '@'.join([localpart, domain])
        else:
            address = Header(address, encoding).encode()
    return formataddr((name, address))


def sanitize_addresses(addresses, encoding='utf-8'):
    return map(lambda address: sanitize_address(address, encoding), addresses)


class MailServer(object):
    def __init__(self, ext):
        self.ext = ext
        self.config = self.ext.config

    def __enter__(self):
        self.host = self.configure_host()
        return self

    def __exit__(self, exc_type, exc_value, tb):
        self.host.quit()

    def configure_host(self):
        if self.config.use_ssl:
            host = smtplib.SMTP_SSL(self.config.server, self.config.port)
        else:
            host = smtplib.SMTP(self.config.server, self.config.port)
        host.set_debuglevel(int(self.config.debug))
        if self.config.use_tls:
            host.starttls()
        if self.config.username and self.config.password:
            host.login(self.config.username, self.config.password)
        return host

    def send(self, message):
        self.host.sendmail(
            sanitize_address(message.sender),
            list(sanitize_addresses(message.all_recipients)),
            to_bytes(str(message)),
            message.mail_options,
            message.rcpt_options)
        return True


class Attachment(object):
    def __init__(
        self, filename=None, data=None, content_type=None, disposition=None,
        headers=None
    ):
        if not content_type and filename:
            content_type = contenttype(filename).split(";")[0]
        self.filename = filename
        self.content_type = content_type or contenttype(filename).split(";")[0]
        self.data = data
        self.disposition = disposition or 'attachment'
        self.headers = headers or {}


class Mail(object):
    def __init__(
        self, ext, subject='', recipients=None, body=None, html=None,
        alts=None, sender=None, cc=None, bcc=None, attachments=None,
        reply_to=None, date=None, charset='utf-8', extra_headers=None,
        mail_options=None, rcpt_options=None
    ):
        sender = sender or ext.config.sender
        if isinstance(sender, tuple):
            sender = "%s <%s>" % sender
        self.ext = ext
        self.recipients = recipients or []
        self.subject = subject
        self.sender = sender
        self.reply_to = reply_to
        self.cc = cc or []
        self.bcc = bcc or []
        self.body = body
        self.alts = dict(alts or {})
        self.html = html
        self.date = date
        self.msgId = make_msgid()
        self.charset = charset
        self.extra_headers = extra_headers
        self.mail_options = mail_options or []
        self.rcpt_options = rcpt_options or []
        self.attachments = attachments or []
        for attr in ['recipients', 'cc', 'bcc']:
            if not isinstance(getattr(self, attr), list):
                setattr(self, attr, [getattr(self, attr)])

    @property
    def all_recipients(self):
        return set(self.recipients) | set(self.bcc) | set(self.cc)

    @property
    def html(self):
        return self.alts.get('html')

    @html.setter
    def html(self, value):
        if value is None:
            self.alts.pop('html', None)
        else:
            self.alts['html'] = value

    def has_bad_headers(self):
        headers = [self.sender, self.reply_to] + self.recipients
        for header in headers:
            if _has_newline(header):
                return True
        if self.subject:
            if _has_newline(self.subject):
                for linenum, line in enumerate(self.subject.split('\r\n')):
                    if not line:
                        return True
                    if linenum > 0 and line[0] not in '\t ':
                        return True
                    if _has_newline(line):
                        return True
                    if len(line.strip()) == 0:
                        return True
        return False

    def _mimetext(self, text, subtype='plain'):
        return MIMEText(text, _subtype=subtype, _charset=self.charset)

    @cachedprop
    def message(self):
        attachments = self.attachments or []
        if len(attachments) == 0 and not self.alts:
            # No html content and zero attachments means plain text
            msg = self._mimetext(self.body)
        elif len(attachments) > 0 and not self.alts:
            # No html and at least one attachment means multipart
            msg = MIMEMultipart()
            msg.attach(self._mimetext(self.body))
        else:
            # Anything else
            msg = MIMEMultipart()
            alternative = MIMEMultipart('alternative')
            alternative.attach(self._mimetext(self.body, 'plain'))
            for mimetype, content in self.alts.items():
                alternative.attach(self._mimetext(content, mimetype))
            msg.attach(alternative)
        if self.subject:
            msg['Subject'] = sanitize_subject(
                to_unicode(self.subject), self.charset)
        msg['From'] = sanitize_address(self.sender, self.charset)
        msg['To'] = ', '.join(
            list(set(sanitize_addresses(self.recipients, self.charset))))
        msg['Date'] = formatdate(self.date, localtime=True)
        msg['Message-ID'] = self.msgId
        if self.cc:
            msg['Cc'] = ', '.join(
                list(set(sanitize_addresses(self.cc, self.charset))))
        if self.reply_to:
            msg['Reply-To'] = sanitize_address(self.reply_to, self.charset)
        if self.extra_headers:
            for k, v in self.extra_headers.items():
                msg[k] = v
        for attachment in attachments:
            f = MIMEBase(*attachment.content_type.split('/'))
            f.set_payload(attachment.data)
            encode_base64(f)
            filename = attachment.filename
            try:
                filename and filename.encode('ascii')
            except UnicodeEncodeError:
                if PY2:
                    filename = filename.encode('utf8')
                filename = ('UTF8', '', filename)
            f.add_header(
                'Content-Disposition', attachment.disposition,
                filename=filename)
            for key, value in attachment.headers.items():
                f.add_header(key, value)
            msg.attach(f)
        if message_policy:
            msg.policy = message_policy
        return msg

    def __str__(self):
        return self.message.as_string()

    def send(self):
        return self.ext.send(self)

    def add_recipient(self, recipient):
        self.recipients.append(recipient)

    def attach(
        self, filename=None, data=None, content_type=None, disposition=None,
        headers=None
    ):
        self.attachments.append(
            Attachment(filename, data, content_type, disposition, headers))


class MailExtension(Extension):
    namespace = 'mailer'

    default_config = {
        'server': '127.0.0.1',
        'username': None,
        'password': None,
        'port': 25,
        'use_tls': False,
        'use_ssl': False,
        'sender': None,
        'debug': False,
        'suppress': False
    }

    def on_load(self):
        self.after_send = []
        self.dispatch = self._send

    def _send(self, message):
        with self.server() as server:
            return server.send(message)

    def mail(self, *args, **kwargs):
        return Mail(self, *args, **kwargs)

    def send(self, message):
        assert message.all_recipients, "No recipients have been added"
        assert message.sender, "The message does not specify a sender"
        if message.has_bad_headers():
            raise RuntimeError("Bad headers in message")
        if message.date is None:
            message.date = time.time()
        if not self.config.suppress:
            rv = self.dispatch(message)
        else:
            rv = True
        for callback in self.after_send:
            callback(message)
        return rv

    def send_mail(self, *args, **kwargs):
        return self.send(Mail(self, *args, **kwargs))

    def server(self):
        return MailServer(self)


class Mailer(object):
    def __init__(self, app):
        app.use_extension(MailExtension)
        self.ext = app.ext.MailExtension

    def mail(self, *args, **kwargs):
        return self.ext.mail(*args, **kwargs)

    def send(self, message):
        return self.ext.send(message)

    def send_mail(self, *args, **kwargs):
        return self.ext.send_mail(*args, **kwargs)

    def dispatcher(self, f):
        self.ext.dispatch = _wrap_dispatcher(f)
        return f

    @contextmanager
    def store_mails(self, suppress=True):
        outbox = []

        def _record(message):
            outbox.append(message)

        suppress = suppress and suppress != self.ext.config.suppress
        if suppress:
            _last_suppress = self.ext.config.suppress
            self.ext.config.suppress = True

        self.ext.after_send.append(_record)
        try:
            yield outbox
        finally:
            if suppress:
                self.ext.config.suppress = _last_suppress
            self.ext.after_send.pop()


def _wrap_dispatcher(dispatcher):
    @wraps(dispatcher)
    def wrapped(ext, *args, **kwargs):
        return dispatcher(*args, **kwargs)
    return wrapped
