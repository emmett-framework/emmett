# -*- coding: utf-8 -*-
"""
    weppy.validators.helpers
    ------------------------

    Provides utilities for validators.

    Ported from the original validators of web2py (http://www.web2py.com)

    :copyright: (c) by Massimo Di Pierro <mdipierro@cs.depaul.edu>
    :license: LGPLv3 (http://www.gnu.org/licenses/lgpl.html)
"""

import re
from datetime import tzinfo, timedelta
from .._compat import StringIO, string_types, to_unicode
from ..globals import current
from ..security import simple_hash, uuid, DIGEST_ALG_BY_SIZE


def translate(text):
    if text is None:
        return None
    elif isinstance(text, string_types):
        return current.T(text)
    return str(text)


def options_sorter(x, y):
    return (str(x[1]).upper() > str(y[1]).upper() and 1) or -1


def is_empty(value, empty_regex=None):
    if isinstance(value, string_types):
        value = value.strip()
        if empty_regex is not None and empty_regex.match(value):
            value = ''
    if value is None or value == '' or value == []:
        return value, True
    return value, False


class _UTC(tzinfo):
    ZERO = timedelta(0)

    def utcoffset(self, dt):
        return _UTC.ZERO

    def tzname(self, dt):
        return "UTC"

    def dst(self, dt):
        return _UTC.ZERO


class LazyCrypt(object):
    def __init__(self, crypt, password):
        """
        crypt is an instance of the Crypt validator,
        password is the password as inserted by the user
        """
        self.crypt = crypt
        self.password = password
        self.crypted = None

    def __str__(self):
        """
        Encrypted self.password and caches it in self.crypted.
        If self.crypt.salt the output is in the format
        <algorithm>$<salt>$<hash>

        Try get the digest_alg from the key (if it exists)
        else assume the default digest_alg. If not key at all, set key=''

        If a salt is specified use it, if salt is True, set salt to uuid
        (this should all be backward compatible)

        Options:
        key = 'uuid'
        key = 'md5:uuid'
        key = 'sha512:uuid'
        ...
        key = 'pbkdf2(1000,64,sha512):uuid' 1000 iterations and 64 chars length
        """
        if self.crypted:
            return self.crypted
        if self.crypt.key:
            if ':' in self.crypt.key:
                digest_alg, key = self.crypt.key.split(':', 1)
            else:
                digest_alg, key = self.crypt.digest_alg, self.crypt.key
        else:
            digest_alg, key = self.crypt.digest_alg, ''
        if self.crypt.salt:
            if self.crypt.salt == True:
                salt = str(uuid()).replace('-', '')[-16:]
            else:
                salt = self.crypt.salt
        else:
            salt = ''
        hashed = simple_hash(self.password, key, salt, digest_alg)
        self.crypted = '%s$%s$%s' % (digest_alg, salt, hashed)
        return self.crypted

    def __eq__(self, stored_password):
        """
        compares the current lazy crypted password with a stored password
        """
        if isinstance(stored_password, self.__class__):
            return ((self is stored_password) or
                    ((self.crypt.key == stored_password.crypt.key) and
                    (self.password == stored_password.password)))

        if self.crypt.key:
            if ':' in self.crypt.key:
                key = self.crypt.key.split(':')[1]
            else:
                key = self.crypt.key
        else:
            key = ''
        if stored_password is None:
            return False
        elif stored_password.count('$') == 2:
            (digest_alg, salt, hash) = stored_password.split('$')
            h = simple_hash(self.password, key, salt, digest_alg)
            temp_pass = '%s$%s$%s' % (digest_alg, salt, h)
        else:  # no salting
            # guess digest_alg
            digest_alg = DIGEST_ALG_BY_SIZE.get(len(stored_password), None)
            if not digest_alg:
                return False
            else:
                temp_pass = simple_hash(self.password, key, '', digest_alg)
        return temp_pass == stored_password

    def __ne__(self, other):
        return not self.__eq__(other)


def _escape_unicode(string):
    '''
    Converts a unicode string into US-ASCII, using a simple conversion scheme.
    Each unicode character that does not have a US-ASCII equivalent is
    converted into a URL escaped form based on its hexadecimal value.
    For example, the unicode character '\u4e86' will become the string '%4e%86'

    Args:
        string: unicode string, the unicode string to convert into an
            escaped US-ASCII form

    Returns:
        string: the US-ASCII escaped form of the inputted string

    @author: Jonathan Benn
    '''
    returnValue = StringIO()

    for character in string:
        code = ord(character)
        if code > 0x7F:
            hexCode = hex(code)
            returnValue.write('%' + hexCode[2:4] + '%' + hexCode[4:6])
        else:
            returnValue.write(character)

    return returnValue.getvalue()


def _unicode_to_ascii_authority(authority):
    '''
    Follows the steps in RFC 3490, Section 4 to convert a unicode authority
    string into its ASCII equivalent.
    For example, u'www.Alliancefran\xe7aise.nu' will be converted into
    'www.xn--alliancefranaise-npb.nu'

    Args:
        authority: unicode string, the URL authority component to convert,
            e.g. u'www.Alliancefran\xe7aise.nu'

    Returns:
        string: the US-ASCII character equivalent to the inputed authority,
             e.g. 'www.xn--alliancefranaise-npb.nu'

    Raises:
        Exception: if the function is not able to convert the inputed
            authority

    @author: Jonathan Benn
    '''
    label_split_regex = re.compile(u'[\u002e\u3002\uff0e\uff61]')

    #RFC 3490, Section 4, Step 1
    #The encodings.idna Python module assumes that AllowUnassigned == True

    #RFC 3490, Section 4, Step 2
    labels = label_split_regex.split(authority)

    #RFC 3490, Section 4, Step 3
    #The encodings.idna Python module assumes that UseSTD3ASCIIRules == False

    #RFC 3490, Section 4, Step 4
    #We use the ToASCII operation because we are about to put the authority
    #into an IDN-unaware slot
    asciiLabels = []
    try:
        import encodings.idna
        for label in labels:
            if label:
                asciiLabels.append(encodings.idna.ToASCII(label))
            else:
                #encodings.idna.ToASCII does not accept an empty string, but
                #it is necessary for us to allow for empty labels so that we
                #don't modify the URL
                asciiLabels.append('')
    except:
        asciiLabels = [str(label) for label in labels]
    #RFC 3490, Section 4, Step 5
    return str(reduce(lambda x, y: x + unichr(0x002E) + y, asciiLabels))


def unicode_to_ascii_url(url, prepend_scheme):
    '''
    Converts the inputed unicode url into a US-ASCII equivalent. This function
    goes a little beyond RFC 3490, which is limited in scope to the domain name
    (authority) only. Here, the functionality is expanded to what was observed
    on Wikipedia on 2009-Jan-22:

       Component    Can Use Unicode?
       ---------    ----------------
       scheme       No
       authority    Yes
       path         Yes
       query        Yes
       fragment     No

    The authority component gets converted to punycode, but occurrences of
    unicode in other components get converted into a pair of URI escapes (we
    assume 4-byte unicode). E.g. the unicode character U+4E2D will be
    converted into '%4E%2D'. Testing with Firefox v3.0.5 has shown that it can
    understand this kind of URI encoding.

    Args:
        url: unicode string, the URL to convert from unicode into US-ASCII
        prepend_scheme: string, a protocol scheme to prepend to the URL if
            we're having trouble parsing it.
            e.g. "http". Input None to disable this functionality

    Returns:
        string: a US-ASCII equivalent of the inputed url

    @author: Jonathan Benn
    '''
    #convert the authority component of the URL into an ASCII punycode string,
    #but encode the rest using the regular URI character encoding

    groups = url_split_regex.match(url).groups()
    #If no authority was found
    if not groups[3]:
        #Try appending a scheme to see if that fixes the problem
        scheme_to_prepend = prepend_scheme or 'http'
        groups = url_split_regex.match(
            to_unicode(scheme_to_prepend) + u'://' + url).groups()
    #if we still can't find the authority
    if not groups[3]:
        raise Exception('No authority component found, ' +
                        'could not decode unicode to US-ASCII')

    #We're here if we found an authority, let's rebuild the URL
    scheme = groups[1]
    authority = groups[3]
    path = groups[4] or ''
    query = groups[5] or ''
    fragment = groups[7] or ''

    if prepend_scheme:
        scheme = str(scheme) + '://'
    else:
        scheme = ''
    return scheme + _unicode_to_ascii_authority(authority) +\
        _escape_unicode(path) + _escape_unicode(query) + str(fragment)

url_split_regex = \
    re.compile('^(([^:/?#]+):)?(//([^/?#]*))?([^?#]*)(\?([^#]*))?(#(.*))?')

official_url_schemes = [
    'aaa', 'aaas', 'acap', 'cap', 'cid', 'crid', 'data', 'dav', 'dict',
    'dns', 'fax', 'file', 'ftp', 'go', 'gopher', 'h323', 'http', 'https',
    'icap', 'im', 'imap', 'info', 'ipp', 'iris', 'iris.beep', 'iris.xpc',
    'iris.xpcs', 'iris.lws', 'ldap', 'mailto', 'mid', 'modem', 'msrp',
    'msrps', 'mtqp', 'mupdate', 'news', 'nfs', 'nntp', 'opaquelocktoken',
    'pop', 'pres', 'prospero', 'rtsp', 'service', 'shttp', 'sip', 'sips',
    'snmp', 'soap.beep', 'soap.beeps', 'tag', 'tel', 'telnet', 'tftp',
    'thismessage', 'tip', 'tv', 'urn', 'vemmi', 'wais', 'xmlrpc.beep',
    'xmlrpc.beep', 'xmpp', 'z39.50r', 'z39.50s'
]

unofficial_url_schemes = [
    'about', 'adiumxtra', 'aim', 'afp', 'aw', 'callto', 'chrome', 'cvs',
    'ed2k', 'feed', 'fish', 'gg', 'gizmoproject', 'iax2', 'irc', 'ircs',
    'itms', 'jar', 'javascript', 'keyparc', 'lastfm', 'ldaps', 'magnet',
    'mms', 'msnim', 'mvn', 'notes', 'nsfw', 'psyc', 'paparazzi:http',
    'rmi', 'rsync', 'secondlife', 'sgn', 'skype', 'ssh', 'sftp', 'smb',
    'sms', 'soldat', 'steam', 'svn', 'teamspeak', 'unreal', 'ut2004',
    'ventrilo', 'view-source', 'webcal', 'wyciwyg', 'xfire', 'xri', 'ymsgr'
]

official_top_level_domains = [
    # a
    'abogado', 'ac', 'academy', 'accountants', 'active', 'actor',
    'ad', 'adult', 'ae', 'aero', 'af', 'ag', 'agency', 'ai',
    'airforce', 'al', 'allfinanz', 'alsace', 'am', 'amsterdam', 'an',
    'android', 'ao', 'apartments', 'aq', 'aquarelle', 'ar', 'archi',
    'army', 'arpa', 'as', 'asia', 'associates', 'at', 'attorney',
    'au', 'auction', 'audio', 'autos', 'aw', 'ax', 'axa', 'az',
    # b
    'ba', 'band', 'bank', 'bar', 'barclaycard', 'barclays',
    'bargains', 'bayern', 'bb', 'bd', 'be', 'beer', 'berlin', 'best',
    'bf', 'bg', 'bh', 'bi', 'bid', 'bike', 'bingo', 'bio', 'biz',
    'bj', 'black', 'blackfriday', 'bloomberg', 'blue', 'bm', 'bmw',
    'bn', 'bnpparibas', 'bo', 'boo', 'boutique', 'br', 'brussels',
    'bs', 'bt', 'budapest', 'build', 'builders', 'business', 'buzz',
    'bv', 'bw', 'by', 'bz', 'bzh',
    # c
    'ca', 'cab', 'cal', 'camera', 'camp', 'cancerresearch', 'canon',
    'capetown', 'capital', 'caravan', 'cards', 'care', 'career',
    'careers', 'cartier', 'casa', 'cash', 'casino', 'cat',
    'catering', 'cbn', 'cc', 'cd', 'center', 'ceo', 'cern', 'cf',
    'cg', 'ch', 'channel', 'chat', 'cheap', 'christmas', 'chrome',
    'church', 'ci', 'citic', 'city', 'ck', 'cl', 'claims',
    'cleaning', 'click', 'clinic', 'clothing', 'club', 'cm', 'cn',
    'co', 'coach', 'codes', 'coffee', 'college', 'cologne', 'com',
    'community', 'company', 'computer', 'condos', 'construction',
    'consulting', 'contractors', 'cooking', 'cool', 'coop',
    'country', 'cr', 'credit', 'creditcard', 'cricket', 'crs',
    'cruises', 'cu', 'cuisinella', 'cv', 'cw', 'cx', 'cy', 'cymru',
    'cz',
    # d
    'dabur', 'dad', 'dance', 'dating', 'day', 'dclk', 'de', 'deals',
    'degree', 'delivery', 'democrat', 'dental', 'dentist', 'desi',
    'design', 'dev', 'diamonds', 'diet', 'digital', 'direct',
    'directory', 'discount', 'dj', 'dk', 'dm', 'dnp', 'do', 'docs',
    'domains', 'doosan', 'durban', 'dvag', 'dz',
    # e
    'eat', 'ec', 'edu', 'education', 'ee', 'eg', 'email', 'emerck',
    'energy', 'engineer', 'engineering', 'enterprises', 'equipment',
    'er', 'es', 'esq', 'estate', 'et', 'eu', 'eurovision', 'eus',
    'events', 'everbank', 'exchange', 'expert', 'exposed',
    # f
    'fail', 'fans', 'farm', 'fashion', 'feedback', 'fi', 'finance',
    'financial', 'firmdale', 'fish', 'fishing', 'fit', 'fitness',
    'fj', 'fk', 'flights', 'florist', 'flowers', 'flsmidth', 'fly',
    'fm', 'fo', 'foo', 'football', 'forsale', 'foundation', 'fr',
    'frl', 'frogans', 'fund', 'furniture', 'futbol',
    # g
    'ga', 'gal', 'gallery', 'garden', 'gb', 'gbiz', 'gd', 'gdn',
    'ge', 'gent', 'gf', 'gg', 'ggee', 'gh', 'gi', 'gift', 'gifts',
    'gives', 'gl', 'glass', 'gle', 'global', 'globo', 'gm', 'gmail',
    'gmo', 'gmx', 'gn', 'goldpoint', 'goog', 'google', 'gop', 'gov',
    'gp', 'gq', 'gr', 'graphics', 'gratis', 'green', 'gripe', 'gs',
    'gt', 'gu', 'guide', 'guitars', 'guru', 'gw', 'gy',
    # h
    'hamburg', 'hangout', 'haus', 'healthcare', 'help', 'here',
    'hermes', 'hiphop', 'hiv', 'hk', 'hm', 'hn', 'holdings',
    'holiday', 'homes', 'horse', 'host', 'hosting', 'house', 'how',
    'hr', 'ht', 'hu',
    # i
    'ibm', 'id', 'ie', 'ifm', 'il', 'im', 'immo', 'immobilien', 'in',
    'industries', 'info', 'ing', 'ink', 'institute', 'insure', 'int',
    'international', 'investments', 'io', 'iq', 'ir', 'irish', 'is',
    'it', 'iwc',
    # j
    'jcb', 'je', 'jetzt', 'jm', 'jo', 'jobs', 'joburg', 'jp',
    'juegos',
    # k
    'kaufen', 'kddi', 'ke', 'kg', 'kh', 'ki', 'kim', 'kitchen',
    'kiwi', 'km', 'kn', 'koeln', 'kp', 'kr', 'krd', 'kred', 'kw',
    'ky', 'kyoto', 'kz',
    # l
    'la', 'lacaixa', 'land', 'lat', 'latrobe', 'lawyer', 'lb', 'lc',
    'lds', 'lease', 'legal', 'lgbt', 'li', 'lidl', 'life',
    'lighting', 'limited', 'limo', 'link', 'lk', 'loans',
    'localhost', 'london', 'lotte', 'lotto', 'lr', 'ls', 'lt',
    'ltda', 'lu', 'luxe', 'luxury', 'lv', 'ly',
    # m
    'ma', 'madrid', 'maison', 'management', 'mango', 'market',
    'marketing', 'marriott', 'mc', 'md', 'me', 'media', 'meet',
    'melbourne', 'meme', 'memorial', 'menu', 'mg', 'mh', 'miami',
    'mil', 'mini', 'mk', 'ml', 'mm', 'mn', 'mo', 'mobi', 'moda',
    'moe', 'monash', 'money', 'mormon', 'mortgage', 'moscow',
    'motorcycles', 'mov', 'mp', 'mq', 'mr', 'ms', 'mt', 'mu',
    'museum', 'mv', 'mw', 'mx', 'my', 'mz',
    # n
    'na', 'nagoya', 'name', 'navy', 'nc', 'ne', 'net', 'network',
    'neustar', 'new', 'nexus', 'nf', 'ng', 'ngo', 'nhk', 'ni',
    'nico', 'ninja', 'nl', 'no', 'np', 'nr', 'nra', 'nrw', 'ntt',
    'nu', 'nyc', 'nz',
    # o
    'okinawa', 'om', 'one', 'ong', 'onl', 'ooo', 'org', 'organic',
    'osaka', 'otsuka', 'ovh',
    # p
    'pa', 'paris', 'partners', 'parts', 'party', 'pe', 'pf', 'pg',
    'ph', 'pharmacy', 'photo', 'photography', 'photos', 'physio',
    'pics', 'pictures', 'pink', 'pizza', 'pk', 'pl', 'place',
    'plumbing', 'pm', 'pn', 'pohl', 'poker', 'porn', 'post', 'pr',
    'praxi', 'press', 'pro', 'prod', 'productions', 'prof',
    'properties', 'property', 'ps', 'pt', 'pub', 'pw', 'py',
    # q
    'qa', 'qpon', 'quebec',
    # r
    're', 'realtor', 'recipes', 'red', 'rehab', 'reise', 'reisen',
    'reit', 'ren', 'rentals', 'repair', 'report', 'republican',
    'rest', 'restaurant', 'reviews', 'rich', 'rio', 'rip', 'ro',
    'rocks', 'rodeo', 'rs', 'rsvp', 'ru', 'ruhr', 'rw', 'ryukyu',
    # s
    'sa', 'saarland', 'sale', 'samsung', 'sarl', 'saxo', 'sb', 'sc',
    'sca', 'scb', 'schmidt', 'school', 'schule', 'schwarz',
    'science', 'scot', 'sd', 'se', 'services', 'sew', 'sexy', 'sg',
    'sh', 'shiksha', 'shoes', 'shriram', 'si', 'singles', 'sj', 'sk',
    'sky', 'sl', 'sm', 'sn', 'so', 'social', 'software', 'sohu',
    'solar', 'solutions', 'soy', 'space', 'spiegel', 'sr', 'st',
    'style', 'su', 'supplies', 'supply', 'support', 'surf',
    'surgery', 'suzuki', 'sv', 'sx', 'sy', 'sydney', 'systems', 'sz',
    # t
    'taipei', 'tatar', 'tattoo', 'tax', 'tc', 'td', 'technology',
    'tel', 'temasek', 'tennis', 'tf', 'tg', 'th', 'tienda', 'tips',
    'tires', 'tirol', 'tj', 'tk', 'tl', 'tm', 'tn', 'to', 'today',
    'tokyo', 'tools', 'top', 'toshiba', 'town', 'toys', 'tp', 'tr',
    'trade', 'training', 'travel', 'trust', 'tt', 'tui', 'tv', 'tw',
    'tz',
    # u
    'ua', 'ug', 'uk', 'university', 'uno', 'uol', 'us', 'uy', 'uz',
    # v
    'va', 'vacations', 'vc', 've', 'vegas', 'ventures',
    'versicherung', 'vet', 'vg', 'vi', 'viajes', 'video', 'villas',
    'vision', 'vlaanderen', 'vn', 'vodka', 'vote', 'voting', 'voto',
    'voyage', 'vu',
    # w
    'wales', 'wang', 'watch', 'webcam', 'website', 'wed', 'wedding',
    'wf', 'whoswho', 'wien', 'wiki', 'williamhill', 'wme', 'work',
    'works', 'world', 'ws', 'wtc', 'wtf',
    # x
    'xn--1qqw23a', 'xn--3bst00m', 'xn--3ds443g', 'xn--3e0b707e',
    'xn--45brj9c', 'xn--45q11c', 'xn--4gbrim', 'xn--55qw42g',
    'xn--55qx5d', 'xn--6frz82g', 'xn--6qq986b3xl', 'xn--80adxhks',
    'xn--80ao21a', 'xn--80asehdb', 'xn--80aswg', 'xn--90a3ac',
    'xn--90ais', 'xn--b4w605ferd', 'xn--c1avg', 'xn--cg4bki',
    'xn--clchc0ea0b2g2a9gcd', 'xn--czr694b', 'xn--czrs0t',
    'xn--czru2d', 'xn--d1acj3b', 'xn--d1alf', 'xn--fiq228c5hs',
    'xn--fiq64b', 'xn--fiqs8s', 'xn--fiqz9s', 'xn--flw351e',
    'xn--fpcrj9c3d', 'xn--fzc2c9e2c', 'xn--gecrj9c', 'xn--h2brj9c',
    'xn--hxt814e', 'xn--i1b6b1a6a2e', 'xn--io0a7i', 'xn--j1amh',
    'xn--j6w193g', 'xn--kprw13d', 'xn--kpry57d', 'xn--kput3i',
    'xn--l1acc', 'xn--lgbbat1ad8j', 'xn--mgb9awbf',
    'xn--mgba3a4f16a', 'xn--mgbaam7a8h', 'xn--mgbab2bd',
    'xn--mgbayh7gpa', 'xn--mgbbh1a71e', 'xn--mgbc0a9azcg',
    'xn--mgberp4a5d4ar', 'xn--mgbx4cd0ab', 'xn--ngbc5azd',
    'xn--node', 'xn--nqv7f', 'xn--nqv7fs00ema', 'xn--o3cw4h',
    'xn--ogbpf8fl', 'xn--p1acf', 'xn--p1ai', 'xn--pgbs0dh',
    'xn--q9jyb4c', 'xn--qcka1pmc', 'xn--rhqv96g', 'xn--s9brj9c',
    'xn--ses554g', 'xn--unup4y', 'xn--vermgensberater-ctb',
    'xn--vermgensberatung-pwb', 'xn--vhquv', 'xn--wgbh1c',
    'xn--wgbl6a', 'xn--xhq521b', 'xn--xkc2al3hye2a',
    'xn--xkc2dl3a5ee0h', 'xn--yfro4i67o', 'xn--ygbi2ammx',
    'xn--zfr164b', 'xxx', 'xyz',
    # y
    'yachts', 'yandex', 'ye', 'yodobashi', 'yoga', 'yokohama',
    'youtube', 'yt',
    # z
    'za', 'zip', 'zm', 'zone', 'zuerich', 'zw'
]
