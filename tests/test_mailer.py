# -*- coding: utf-8 -*-
"""
    tests.mailer
    ------------

    Test Emmett mailer
"""

import base64
import email
import pytest
import re
import time

from email.header import Header
from emmett import App
from emmett.tools.mailer import Mailer, sanitize_address


@pytest.fixture(scope='module')
def app():
    rv = App(__name__)
    rv.config.mailer.sender = 'support@example.com'
    return rv


@pytest.fixture(scope='module')
def mailer(app):
    rv = Mailer(app)
    return rv


def test_message_init(mailer):
    msg = mailer.mail(subject="subject", recipients="to@example.com")
    assert msg.sender == 'support@example.com'
    assert msg.recipients == ["to@example.com"]


def test_recipients(mailer):
    msg = mailer.mail(subject="subject")
    assert msg.recipients == []
    msg.add_recipient("to@example.com")
    assert msg.recipients == ["to@example.com"]


def test_all_recipients(mailer):
    msg = mailer.mail(
        subject="subject", recipients=["somebody@here.com"],
        cc=["cc@example.com"], bcc=["bcc@example.com"])
    assert len(msg.all_recipients) == 3
    msg.add_recipient("cc@example.com")
    assert len(msg.all_recipients) == 3


def test_sender(mailer):
    msg = mailer.mail(
        subject="subject",
        sender=u'ÄÜÖ → ✓ <from@example.com>>',
        recipients=["to@example.com"])
    assert 'From: =?utf-8?b?w4TDnMOWIOKGkiDinJM=?= <from@example.com>' in \
        str(msg)


def test_sender_as_tuple(mailer):
    msg = mailer.mail(
        subject="testing", sender=("tester", "tester@example.com"))
    assert msg.sender == "tester <tester@example.com>"
    msg = mailer.mail(
        subject="subject",
        sender=(u"ÄÜÖ → ✓", 'from@example.com>'),
        recipients=["to@example.com"])
    assert 'From: =?utf-8?b?w4TDnMOWIOKGkiDinJM=?= <from@example.com>' in \
        str(msg)


def test_reply_to(mailer):
    msg = mailer.mail(
        subject="testing",
        recipients=["to@example.com"],
        sender="spammer <spammer@example.com>",
        reply_to="somebody <somebody@example.com>",
        body="testing")
    h = Header(
        "Reply-To: %s" % sanitize_address('somebody <somebody@example.com>'))
    assert h.encode() in str(msg)


def test_missing_sender(mailer):
    msg = mailer.mail(
        subject="testing", recipients=["to@example.com"], body="testing")
    msg.sender = None
    with pytest.raises(AssertionError):
        msg.send()


def test_missing_recipients(mailer):
    msg = mailer.mail(subject="testing", recipients=[], body="testing")
    with pytest.raises(AssertionError):
        msg.send()


def test_bcc(mailer):
    msg = mailer.mail(
        sender="from@example.com",
        subject="testing",
        recipients=["to@example.com"],
        body="testing",
        bcc=["tosomeoneelse@example.com"])
    assert "tosomeoneelse@example.com" not in str(msg)


def test_cc(mailer):
    msg = mailer.mail(
        sender="from@example.com",
        subject="testing",
        recipients=["to@example.com"],
        body="testing",
        cc=["tosomeoneelse@example.com"])
    assert "Cc: tosomeoneelse@example.com" in str(msg)


def test_attach(mailer):
    msg = mailer.mail(
        subject="testing", recipients=["to@example.com"], body="testing")
    msg.attach(data=b"this is a test", content_type="text/plain")
    a = msg.attachments[0]
    assert a.filename is None
    assert a.disposition == 'attachment'
    assert a.content_type == 'text/plain'
    assert a.data == b"this is a test"


def test_bad_subject(mailer):
    msg = mailer.mail(
        subject="testing\r\n",
        sender="from@example.com",
        body="testing",
        recipients=["to@example.com"])
    with pytest.raises(RuntimeError):
        msg.send()


def test_subject(mailer):
    msg = mailer.mail(
        subject=u"sübject",
        sender='from@example.com',
        recipients=["to@example.com"])
    assert '=?utf-8?q?s=C3=BCbject?=' in str(msg)


def test_empty_subject(mailer):
    msg = mailer.mail(sender="from@example.com", recipients=["foo@bar.com"])
    msg.body = "normal ascii text"
    assert 'Subject:' not in str(msg)


def test_multiline_subject(mailer):
    msg = mailer.mail(
        subject="testing\r\n testing\r\n testing \r\n \ttesting",
        sender="from@example.com",
        body="testing",
        recipients=["to@example.com"])
    msg_as_string = str(msg)
    assert "From: from@example.com" in msg_as_string
    assert "testing\r\n testing\r\n testing \r\n \ttesting" in msg_as_string
    msg = mailer.mail(
        subject="testing\r\n testing\r\n ",
        sender="from@example.com",
        body="testing",
        recipients=["to@example.com"])
    with pytest.raises(RuntimeError):
        msg.send()
    msg = mailer.mail(
        subject="testing\r\n testing\r\n\t",
        sender="from@example.com",
        body="testing",
        recipients=["to@example.com"])
    with pytest.raises(RuntimeError):
        msg.send()
    msg = mailer.mail(
        subject="testing\r\n testing\r\n\n",
        sender="from@example.com",
        body="testing",
        recipients=["to@example.com"])
    with pytest.raises(RuntimeError):
        msg.send()


def test_bad_sender(mailer):
    msg = mailer.mail(
        subject="testing",
        sender="from@example.com\r\n",
        recipients=["to@example.com"],
        body="testing")
    assert 'From: from@example.com' in str(msg)


def test_bad_reply_to(mailer):
    msg = mailer.mail(
        subject="testing",
        sender="from@example.com",
        reply_to="evil@example.com\r",
        recipients=["to@example.com"],
        body="testing")
    msg_as_string = str(msg)
    assert 'From: from@example.com' in msg_as_string
    assert 'To: to@example.com' in msg_as_string
    assert 'Reply-To: evil@example.com' in msg_as_string


def test_bad_recipient(mailer):
    msg = mailer.mail(
        subject="testing",
        sender="from@example.com",
        recipients=["to@example.com", "to\r\n@example.com"],
        body="testing")
    assert 'To: to@example.com' in str(msg)


def test_address_sanitize(mailer):
    msg = mailer.mail(
        subject="testing",
        sender="sender\r\n@example.com",
        reply_to="reply_to\r\n@example.com",
        recipients=["recipient\r\n@example.com"])
    msg_as_string = str(msg)
    assert 'sender@example.com' in msg_as_string
    assert 'reply_to@example.com' in msg_as_string
    assert 'recipient@example.com' in msg_as_string


def test_plain_message(mailer):
    plain_text = "Hello Joe,\nHow are you?"
    msg = mailer.mail(
        sender="from@example.com",
        subject="subject",
        recipients=["to@example.com"],
        body=plain_text)
    assert plain_text == msg.body
    assert 'Content-Type: text/plain' in str(msg)


def test_plain_message_with_attachments(mailer):
    msg = mailer.mail(
        sender="from@example.com",
        subject="subject",
        recipients=["to@example.com"],
        body="hello")
    msg.attach(data=b"this is a test", content_type="text/plain")
    assert 'Content-Type: multipart/mixed' in str(msg)


def test_plain_message_with_unicode_attachments(mailer):
    msg = mailer.mail(
        subject="subject", recipients=["to@example.com"], body="hello")
    msg.attach(
        data=b"this is a test",
        content_type="text/plain",
        filename=u'ünicöde ←→ ✓.txt')
    parsed = email.message_from_string(str(msg))
    assert (
        re.sub(r'\s+', ' ', parsed.get_payload()[1].get('Content-Disposition'))
        in [
            'attachment; filename*="UTF8\'\''
            '%C3%BCnic%C3%B6de%20%E2%86%90%E2%86%92%20%E2%9C%93.txt"',
            'attachment; filename*=UTF8\'\''
            '%C3%BCnic%C3%B6de%20%E2%86%90%E2%86%92%20%E2%9C%93.txt'
        ])


def test_html_message(mailer):
    html_text = "<p>Hello World</p>"
    msg = mailer.mail(
        sender="from@example.com",
        subject="subject",
        recipients=["to@example.com"],
        html=html_text)
    assert html_text == msg.html
    assert 'Content-Type: multipart/alternative' in str(msg)


def test_json_message(mailer):
    json_text = '{"msg": "Hello World!}'
    msg = mailer.mail(
        sender="from@example.com",
        subject="subject",
        recipients=["to@example.com"],
        alts={'json': json_text})
    assert json_text == msg.alts['json']
    assert 'Content-Type: multipart/alternative' in str(msg)


def test_html_message_with_attachments(mailer):
    html_text = "<p>Hello World</p>"
    plain_text = 'Hello World'
    msg = mailer.mail(
        sender="from@example.com",
        subject="subject",
        recipients=["to@example.com"],
        body=plain_text,
        html=html_text)
    msg.attach(data=b"this is a test", content_type="text/plain")
    assert html_text == msg.html
    assert 'Content-Type: multipart/alternative' in str(msg)
    parsed = email.message_from_string(str(msg))
    assert len(parsed.get_payload()) == 2
    body, attachment = parsed.get_payload()
    assert len(body.get_payload()) == 2
    plain, html = body.get_payload()
    assert plain.get_payload() == plain_text
    assert html.get_payload() == html_text
    assert base64.b64decode(attachment.get_payload()) == b'this is a test'


def test_date(mailer):
    before = time.time()
    msg = mailer.mail(
        sender="from@example.com",
        subject="subject",
        recipients=["to@example.com"],
        body="hello",
        date=time.time())
    after = time.time()
    assert before <= msg.date <= after
    fmt_date = email.utils.formatdate(msg.date, localtime=True)
    assert 'Date: {}'.format(fmt_date) in str(msg)


def test_msgid(mailer):
    msg = mailer.mail(
        sender="from@example.com",
        subject="subject",
        recipients=["to@example.com"],
        body="hello")
    r = re.compile(r"<\S+@\S+>").match(msg.msgId)
    assert r is not None
    assert 'Message-ID: {}'.format(msg.msgId) in str(msg)


def test_unicode_addresses(mailer):
    msg = mailer.mail(
        subject="subject",
        sender=u'ÄÜÖ → ✓ <from@example.com>',
        recipients=[u"Ä <t1@example.com>", u"Ü <t2@example.com>"],
        cc=[u"Ö <cc@example.com>"])
    msg_as_string = str(msg)
    a1 = sanitize_address(u"Ä <t1@example.com>")
    a2 = sanitize_address(u"Ü <t2@example.com>")
    h1_a = Header("To: %s, %s" % (a1, a2))
    h1_b = Header("To: %s, %s" % (a2, a1))
    h2 = Header("From: %s" % sanitize_address(u"ÄÜÖ → ✓ <from@example.com>"))
    h3 = Header("Cc: %s" % sanitize_address(u"Ö <cc@example.com>"))
    try:
        assert h1_a.encode() in msg_as_string
    except AssertionError:
        assert h1_b.encode() in msg_as_string
    assert h2.encode() in msg_as_string
    assert h3.encode() in msg_as_string


def test_extra_headers(mailer):
    msg = mailer.mail(
        sender="from@example.com",
        subject="subject",
        recipients=["to@example.com"],
        body="hello",
        extra_headers={'X-Extra-Header': 'Yes'})
    assert 'X-Extra-Header: Yes' in str(msg)


def test_send(mailer):
    with mailer.store_mails() as outbox:
        msg = mailer.mail(
            subject="testing", recipients=["tester@example.com"], body="test")
        msg.send()
        assert msg.date is not None
        assert len(outbox) == 1
        sent_msg = outbox[0]
        assert sent_msg.sender == 'support@example.com'


def test_send_mail(mailer):
    with mailer.store_mails() as outbox:
        mailer.send_mail(
            subject="testing", recipients=["tester@example.com"], body="test")
        assert len(outbox) == 1
        sent_msg = outbox[0]
        assert sent_msg.subject == 'testing'
        assert sent_msg.recipients == ["tester@example.com"]
        assert sent_msg.body == 'test'
        assert sent_msg.sender == 'support@example.com'
