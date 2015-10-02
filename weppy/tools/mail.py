# -*- coding: utf-8 -*-
"""
    weppy.tools.mail
    ----------------

    provide a mailing system

    adapted from the original code of web2py (http://www.web2py.com)

    :copyright: (c) by Massimo Di Pierro <mdipierro@cs.depaul.edu>
    :license: LGPLv3 (http://www.gnu.org/licenses/lgpl.html)
"""

import os
import time
import smtplib

from .._compat import iteritems, PY2
from ..utils import read_file
from ..datastructures import sdict
from ..libs.contenttype import contenttype

if PY2:
    from email.MIMEBase import MIMEBase
    from email import MIMEMultipart, MIMEText, Encoders, Header, \
        message_from_string, Charset
else:
    from email import message_from_string
    from email.mime.base import MIMEBase
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email import encoders as Encoders
    from email.header import Header
    from email.charset import Charset


class Mail(object):
    """
    Class for configuring and sending emails with alternative text / html
    body, multiple attachments and encryption support

    Works with SMTP and Google App Engine.
    """

    class Attachment(MIMEBase):
        """
        Email attachment

        Arguments:

            payload: path to file or file-like object with read() method
            filename: name of the attachment stored in message; if set to
                      None, it will be fetched from payload path; file-like
                      object payload must have explicit filename specified
            content_id: id of the attachment; automatically contained within
                        < and >
            content_type: content type of the attachment; if set to None,
                          it will be fetched from filename using gluon.contenttype
                          module
            encoding: encoding of all strings passed to this function (except
                      attachment body)

        Content ID is used to identify attachments within the html body;
        in example, attached image with content ID 'photo' may be used in
        html message as a source of img tag <img src="cid:photo" />.

        Examples:

            #Create attachment from text file:
            attachment = Mail.Attachment('/path/to/file.txt')

            Content-Type: text/plain
            MIME-Version: 1.0
            Content-Disposition: attachment; filename="file.txt"
            Content-Transfer-Encoding: base64

            SOMEBASE64CONTENT=

            #Create attachment from image file with custom filename and cid:
            attachment = Mail.Attachment('/path/to/file.png',
                                             filename='photo.png',
                                             content_id='photo')

            Content-Type: image/png
            MIME-Version: 1.0
            Content-Disposition: attachment; filename="photo.png"
            Content-Id: <photo>
            Content-Transfer-Encoding: base64

            SOMEOTHERBASE64CONTENT=
        """

        def __init__(
            self,
            payload,
            filename=None,
            content_id=None,
            content_type=None,
                encoding='utf-8'):
            if isinstance(payload, str):
                if filename is None:
                    filename = os.path.basename(payload)
                payload = read_file(payload, 'rb')
            else:
                if filename is None:
                    raise Exception('Missing attachment name')
                payload = payload.read()
            filename = filename.encode(encoding)
            if content_type is None:
                content_type = contenttype(filename)
            self.my_filename = filename
            self.my_payload = payload
            MIMEBase.__init__(self, *content_type.split('/', 1))
            self.set_payload(payload)
            self['Content-Disposition'] = 'attachment; filename="%s"' % filename
            if not content_id is None:
                self['Content-Id'] = '<%s>' % content_id.encode(encoding)
            Encoders.encode_base64(self)

    def __init__(self, app, server=None, sender=None, login=None, tls=True):
        """
        Main Mail object

        Arguments:

            server: SMTP server address in address:port notation
            sender: sender email address
            login: sender login name and password in login:password notation
                   or None if no authentication is required
            tls: enables/disables encryption (True by default)

        In Google App Engine use:

            server='gae'

        For sake of backward compatibility all fields are optional and default
        to None, however, to be able to send emails at least server and sender
        must be specified. They are available under following fields:

            mail.settings.server
            mail.settings.sender
            mail.settings.login

        When server is 'logging', email is logged but not sent (debug mode)

        Optionally you can use PGP encryption or X509:

            mail.settings.cipher_type = None
            mail.settings.gpg_home = None
            mail.settings.sign = True
            mail.settings.sign_passphrase = None
            mail.settings.encrypt = True
            mail.settings.x509_sign_keyfile = None
            mail.settings.x509_sign_certfile = None
            mail.settings.x509_nocerts = False
            mail.settings.x509_crypt_certfiles = None

            cipher_type       : None
                                gpg - need a python-pyme package and gpgme lib
                                x509 - smime
            gpg_home          : you can set a GNUPGHOME environment variable
                                to specify home of gnupg
            sign              : sign the message (True or False)
            sign_passphrase   : passphrase for key signing
            encrypt           : encrypt the message
                             ... x509 only ...
            x509_sign_keyfile : the signers private key filename (PEM format)
            x509_sign_certfile: the signers certificate filename (PEM format)
            x509_nocerts      : if True then no attached certificate in mail
            x509_crypt_certfiles: the certificates file to encrypt the messages
                                  with can be a file name or a list of
                                  file names (PEM format)

        Examples:

            #Create Mail object with authentication data for remote server:
            mail = Mail('example.com:25', 'me@example.com', 'me:password')
        """

        self.app = app
        ## read config from app
        ##
        settings = self.settings = sdict()
        settings.server = server
        settings.sender = sender
        settings.login = login
        settings.tls = tls
        settings.hostname = None
        settings.ssl = False
        settings.cipher_type = None
        settings.gpg_home = None
        settings.sign = True
        settings.sign_passphrase = None
        settings.encrypt = True
        settings.x509_sign_keyfile = None
        settings.x509_sign_certfile = None
        settings.x509_nocerts = False
        settings.x509_crypt_certfiles = None
        settings.debug = False
        settings.lock_keys = True
        self.result = {}
        self.error = None

    def send(
        self,
        to,
        subject = '[no subject]',
        message = '[no message]',
        attachments=None,
        cc=None,
        bcc=None,
        reply_to=None,
        sender=None,
        encoding='utf-8',
        raw=False,
        headers={}
    ):
        """
        Sends an email using data specified in constructor

        Arguments:

            to: list or tuple of receiver addresses; will also accept single
                object
            subject: subject of the email
            message: email body text; depends on type of passed object:
                     if 2-list or 2-tuple is passed: first element will be
                     source of plain text while second of html text;
                     otherwise: object will be the only source of plain text
                     and html source will be set to None;
                     If text or html source is:
                     None: content part will be ignored,
                     string: content part will be set to it,
                     file-like object: content part will be fetched from
                                       it using it's read() method
            attachments: list or tuple of Mail.Attachment objects; will also
                         accept single object
            cc: list or tuple of carbon copy receiver addresses; will also
                accept single object
            bcc: list or tuple of blind carbon copy receiver addresses; will
                also accept single object
            reply_to: address to which reply should be composed
            encoding: encoding of all strings passed to this method (including
                      message bodies)
            headers: dictionary of headers to refine the headers just before
                     sending mail, e.g. {'Return-Path' : 'bounces@example.org'}

        Examples:

            #Send plain text message to single address:
            mail.send('you@example.com',
                      'Message subject',
                      'Plain text body of the message')

            #Send html message to single address:
            mail.send('you@example.com',
                      'Message subject',
                      '<html>Plain text body of the message</html>')

            #Send text and html message to three addresses (two in cc):
            mail.send('you@example.com',
                      'Message subject',
                      ('Plain text body', '<html>html body</html>'),
                      cc=['other1@example.com', 'other2@example.com'])

            #Send html only message with image attachment available from
            the message by 'photo' content id:
            mail.send('you@example.com',
                      'Message subject',
                      (None, '<html><img src="cid:photo" /></html>'),
                      Mail.Attachment('/path/to/photo.jpg'
                                      content_id='photo'))

            #Send email with two attachments and no body text
            mail.send('you@example.com,
                      'Message subject',
                      None,
                      [Mail.Attachment('/path/to/fist.file'),
                       Mail.Attachment('/path/to/second.file')])

        Returns True on success, False on failure.

        Before return, method updates two object's fields:
        self.result: return value of smtplib.SMTP.sendmail() or GAE's
                     mail.send_mail() method
        self.error: Exception message or None if above was successful
        """

        # We don't want to use base64 encoding for unicode mail
        Charset.add_charset('utf-8', Charset.QP, Charset.QP, 'utf-8')

        def encode_header(key):
            if [c for c in key if 32 > ord(c) or ord(c) > 127]:
                return Header.Header(key.encode('utf-8'), 'utf-8')
            else:
                return key

        # encoded or raw text
        def encoded_or_raw(text):
            if raw:
                text = encode_header(text)
            return text

        sender = sender or self.settings.sender

        if not isinstance(self.settings.server, str):
            raise Exception('Server address not specified')
        if not isinstance(sender, str):
            raise Exception('Sender address not specified')

        if not raw and attachments:
            # Use multipart/mixed if there is attachments
            payload_in = MIMEMultipart.MIMEMultipart('mixed')
        elif raw:
            # no encoding configuration for raw messages
            if not isinstance(message, basestring):
                message = message.read()
            if isinstance(message, unicode):
                text = message.encode('utf-8')
            elif not encoding == 'utf-8':
                text = message.decode(encoding).encode('utf-8')
            else:
                text = message
            # No charset passed to avoid transport encoding
            # NOTE: some unicode encoded strings will produce
            # unreadable mail contents.
            payload_in = MIMEText.MIMEText(text)
        if to:
            if not isinstance(to, (list, tuple)):
                to = [to]
        else:
            raise Exception('Target receiver address not specified')
        if cc:
            if not isinstance(cc, (list, tuple)):
                cc = [cc]
        if bcc:
            if not isinstance(bcc, (list, tuple)):
                bcc = [bcc]
        if message is None:
            text = html = None
        elif isinstance(message, (list, tuple)):
            text, html = message
        elif message.strip().startswith('<html') and \
                message.strip().endswith('</html>'):
            text = self.settings.server == 'gae' and message or None
            html = message
        else:
            text = message
            html = None

        if (not text is None or not html is None) and (not raw):

            if not text is None:
                if not isinstance(text, basestring):
                    text = text.read()
                if isinstance(text, unicode):
                    text = text.encode('utf-8')
                elif not encoding == 'utf-8':
                    text = text.decode(encoding).encode('utf-8')
            if not html is None:
                if not isinstance(html, basestring):
                    html = html.read()
                if isinstance(html, unicode):
                    html = html.encode('utf-8')
                elif not encoding == 'utf-8':
                    html = html.decode(encoding).encode('utf-8')

            # Construct mime part only if needed
            if text is not None and html:
                # We have text and html we need multipart/alternative
                attachment = MIMEMultipart.MIMEMultipart('alternative')
                attachment.attach(MIMEText.MIMEText(text, _charset='utf-8'))
                attachment.attach(
                    MIMEText.MIMEText(html, 'html', _charset='utf-8'))
            elif text is not None:
                attachment = MIMEText.MIMEText(text, _charset='utf-8')
            elif html:
                attachment = \
                    MIMEText.MIMEText(html, 'html', _charset='utf-8')

            if attachments:
                # If there is attachments put text and html into
                # multipart/mixed
                payload_in.attach(attachment)
            else:
                # No attachments no multipart/mixed
                payload_in = attachment

        if (attachments is None) or raw:
            pass
        elif isinstance(attachments, (list, tuple)):
            for attachment in attachments:
                payload_in.attach(attachment)
        else:
            payload_in.attach(attachments)

        #######################################################
        #                      CIPHER                         #
        #######################################################
        cipher_type = self.settings.cipher_type
        sign = self.settings.sign
        sign_passphrase = self.settings.sign_passphrase
        encrypt = self.settings.encrypt
        #######################################################
        #                       GPGME                         #
        #######################################################
        if cipher_type == 'gpg':
            if self.settings.gpg_home:
                # Set GNUPGHOME environment variable to set home of gnupg
                import os
                os.environ['GNUPGHOME'] = self.settings.gpg_home
            if not sign and not encrypt:
                self.error = "No sign and no encrypt is set but cipher type to gpg"
                return False

            # need a python-pyme package and gpgme lib
            from pyme import core, errors
            from pyme.constants.sig import mode
            ############################################
            #                   sign                   #
            ############################################
            if sign:
                import string
                core.check_version(None)
                pin = string.replace(payload_in.as_string(), '\n', '\r\n')
                plain = core.Data(pin)
                sig = core.Data()
                c = core.Context()
                c.set_armor(1)
                c.signers_clear()
                # search for signing key for From:
                for sigkey in c.op_keylist_all(sender, 1):
                    if sigkey.can_sign:
                        c.signers_add(sigkey)
                if not c.signers_enum(0):
                    self.error = 'No key for signing [%s]' % sender
                    return False
                c.set_passphrase_cb(lambda x, y, z: sign_passphrase)
                try:
                    # make a signature
                    c.op_sign(plain, sig, mode.DETACH)
                    sig.seek(0, 0)
                    # make it part of the email
                    payload = MIMEMultipart.MIMEMultipart('signed',
                                                          boundary=None,
                                                          _subparts=None,
                                                          **dict(
                                                          micalg="pgp-sha1",
                                                          protocol="application/pgp-signature"))
                    # insert the origin payload
                    payload.attach(payload_in)
                    # insert the detached signature
                    p = MIMEBase("application", 'pgp-signature')
                    p.set_payload(sig.read())
                    payload.attach(p)
                    # it's just a trick to handle the no encryption case
                    payload_in = payload
                except errors.GPGMEError as ex:
                    self.error = "GPG error: %s" % ex.getstring()
                    return False
            ############################################
            #                  encrypt                 #
            ############################################
            if encrypt:
                core.check_version(None)
                plain = core.Data(payload_in.as_string())
                cipher = core.Data()
                c = core.Context()
                c.set_armor(1)
                # collect the public keys for encryption
                recipients = []
                rec = to[:]
                if cc:
                    rec.extend(cc)
                if bcc:
                    rec.extend(bcc)
                for addr in rec:
                    c.op_keylist_start(addr, 0)
                    r = c.op_keylist_next()
                    if r is None:
                        self.error = 'No key for [%s]' % addr
                        return False
                    recipients.append(r)
                try:
                    # make the encryption
                    c.op_encrypt(recipients, 1, plain, cipher)
                    cipher.seek(0, 0)
                    # make it a part of the email
                    payload = MIMEMultipart.MIMEMultipart('encrypted',
                                                          boundary=None,
                                                          _subparts=None,
                                                          **dict(protocol="application/pgp-encrypted"))
                    p = MIMEBase("application", 'pgp-encrypted')
                    p.set_payload("Version: 1\r\n")
                    payload.attach(p)
                    p = MIMEBase("application", 'octet-stream')
                    p.set_payload(cipher.read())
                    payload.attach(p)
                except errors.GPGMEError as ex:
                    self.error = "GPG error: %s" % ex.getstring()
                    return False
        #######################################################
        #                       X.509                         #
        #######################################################
        elif cipher_type == 'x509':
            if not sign and not encrypt:
                self.error = "No sign and no encrypt is set but cipher type to x509"
                return False
            x509_sign_keyfile = self.settings.x509_sign_keyfile
            if self.settings.x509_sign_certfile:
                x509_sign_certfile = self.settings.x509_sign_certfile
            else:
                # if there is no sign certfile we'll assume the
                # cert is in keyfile
                x509_sign_certfile = self.settings.x509_sign_keyfile
            # crypt certfiles could be a string or a list
            x509_crypt_certfiles = self.settings.x509_crypt_certfiles
            x509_nocerts = self.settings.x509_nocerts

            # need m2crypto
            try:
                from M2Crypto import BIO, SMIME, X509
            except Exception as e:
                self.error = "Can't load M2Crypto module"
                return False
            msg_bio = BIO.MemoryBuffer(payload_in.as_string())
            s = SMIME.SMIME()

            #                   SIGN
            if sign:
                #key for signing
                try:
                    s.load_key(x509_sign_keyfile, x509_sign_certfile,
                               callback=lambda x: sign_passphrase)
                except Exception as e:
                    self.error = "Something went wrong on certificate / private key loading: <%s>" % str(e)
                    return False
                try:
                    if x509_nocerts:
                        flags = SMIME.PKCS7_NOCERTS
                    else:
                        flags = 0
                    if not encrypt:
                        flags += SMIME.PKCS7_DETACHED
                    p7 = s.sign(msg_bio, flags=flags)
                    msg_bio = BIO.MemoryBuffer(payload_in.as_string(
                    ))  # Recreate coz sign() has consumed it.
                except Exception as e:
                    self.error = "Something went wrong on signing: <%s> %s" % (
                        str(e), str(flags))
                    return False

            #                   ENCRYPT
            if encrypt:
                try:
                    sk = X509.X509_Stack()
                    if not isinstance(x509_crypt_certfiles, (list, tuple)):
                        x509_crypt_certfiles = [x509_crypt_certfiles]

                    # make an encryption cert's stack
                    for x in x509_crypt_certfiles:
                        sk.push(X509.load_cert(x))
                    s.set_x509_stack(sk)

                    s.set_cipher(SMIME.Cipher('des_ede3_cbc'))
                    tmp_bio = BIO.MemoryBuffer()
                    if sign:
                        s.write(tmp_bio, p7)
                    else:
                        tmp_bio.write(payload_in.as_string())
                    p7 = s.encrypt(tmp_bio)
                except Exception as e:
                    self.error = "Something went wrong on encrypting: <%s>" % str(e)
                    return False

            #                 Final stage in sign and encryption
            out = BIO.MemoryBuffer()
            if encrypt:
                s.write(out, p7)
            else:
                if sign:
                    s.write(out, p7, msg_bio, SMIME.PKCS7_DETACHED)
                else:
                    out.write('\r\n')
                    out.write(payload_in.as_string())
            out.close()
            st = str(out.read())
            payload = message_from_string(st)
        else:
            # no cryptography process as usual
            payload = payload_in

        payload['From'] = encoded_or_raw(sender.decode(encoding))
        origTo = to[:]
        if to:
            payload['To'] = encoded_or_raw(', '.join(to).decode(encoding))
        if reply_to:
            payload['Reply-To'] = encoded_or_raw(reply_to.decode(encoding))
        if cc:
            payload['Cc'] = encoded_or_raw(', '.join(cc).decode(encoding))
            to.extend(cc)
        if bcc:
            to.extend(bcc)
        payload['Subject'] = encoded_or_raw(subject.decode(encoding))
        payload['Date'] = time.strftime("%a, %d %b %Y %H:%M:%S +0000",
                                        time.gmtime())
        for k, v in iteritems(headers):
            payload[k] = encoded_or_raw(v.decode(encoding))
        result = {}
        try:
            if self.settings.server == 'logging':
                self.app.log.warn('email not sent\n%s\nFrom: %s\nTo: %s\nSubject: %s\n\n%s\n%s\n' %
                            ('-' * 40, sender,
                             ', '.join(to), subject,
                             text or html, '-' * 40))
            elif self.settings.server == 'gae':
                xcc = dict()
                if cc:
                    xcc['cc'] = cc
                if bcc:
                    xcc['bcc'] = bcc
                if reply_to:
                    xcc['reply_to'] = reply_to
                from google.appengine.api import mail
                attachments = attachments and [(a.my_filename, a.my_payload) for a in attachments if not raw]
                if attachments:
                    result = mail.send_mail(
                        sender=sender, to=origTo,
                        subject=subject, body=text, html=html,
                        attachments=attachments, **xcc)
                elif html and (not raw):
                    result = mail.send_mail(
                        sender=sender, to=origTo,
                        subject=subject, body=text, html=html, **xcc)
                else:
                    result = mail.send_mail(
                        sender=sender, to=origTo,
                        subject=subject, body=text, **xcc)
            else:
                smtp_args = self.settings.server.split(':')
                if self.settings.ssl:
                    server = smtplib.SMTP_SSL(*smtp_args)
                else:
                    server = smtplib.SMTP(*smtp_args)
                if self.settings.tls and not self.settings.ssl:
                    server.ehlo(self.settings.hostname)
                    server.starttls()
                    server.ehlo(self.settings.hostname)
                if self.settings.login:
                    server.login(*self.settings.login.split(':', 1))
                result = server.sendmail(
                    sender, to, payload.as_string())
                server.quit()
        except Exception as e:
            self.app.log.warn('Mail.send failure:%s' % e)
            self.result = result
            self.error = e
            return False
        self.result = result
        self.error = None
        return True
