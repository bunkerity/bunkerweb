#!/usr/bin/env python

#
#
#

import datetime
import sys
import logging
import urllib
import urlparse
try:
    import libinjection
except:
    pass

from tornado import template
import tornado.httpserver
import tornado.ioloop
import tornado.web
import tornado.wsgi
import tornado.escape
import tornado.options

def breakapart(s):
    """ attempts to add spaces in a SQLi so it renders nicely on the webpage
    """
    return s.replace(',', ', ').replace('/*',' /*')

# http://stackoverflow.com/questions/312443/how-do-you-split-a-list-into-evenly-sized-chunks-in-python
def chunks(l, n):
    """ Yield successive n-sized chunks from l.
    """
    for i in xrange(0, len(l), n):
        yield l[i:i+n]

def breakify(s):
    output = ""
    for c in chunks(s, 20):
        output += c
        if ' ' not in c:
            output += ' '
    return output

def print_token_string(tok):
    """
    returns the value of token, handling opening and closing quote characters
    """
    out = ''
    if tok.str_open != '\0':
        out += tok.str_open
    out += tok.val
    if tok.str_close != '\0':
        out += tok.str_close
    return out

def print_token(tok):
    """
    prints a token for use in unit testing
    """
    out = ''
    if tok.type == 's':
        out += print_token_string(tok)
    elif tok.type == 'v':
        vc = tok.count;
        if vc == 1:
            out += '@'
        elif vc == 2:
            out += '@@'
        out += print_token_string(tok)
    else:
        out += tok.val
    return (tok.type, out)

def alltokens(val, flags):

    if flags & libinjection.FLAG_QUOTE_SINGLE:
        contextstr = 'single'
    elif flags & libinjection.FLAG_QUOTE_DOUBLE:
        contextstr = 'double'
    else:
        contextstr = 'none'

    if flags & libinjection.FLAG_SQL_ANSI:
        commentstr = 'ansi'
    elif flags & libinjection.FLAG_SQL_MYSQL:
        commentstr = 'mysql'
    else:
        raise RuntimeException("bad quote context")

    parse = {
        'comment': commentstr,
        'quote': contextstr
    }
    args = []
    sqlstate = libinjection.sqli_state()
    libinjection.sqli_init(sqlstate, val, flags)
    count = 0
    while count < 25:
        count += 1
        ok = libinjection.sqli_tokenize(sqlstate)
        if ok == 0:
            break
        args.append(print_token(sqlstate.current))


    parse['tokens'] = args

    args = []
    fingerprint = libinjection.sqli_fingerprint(sqlstate, flags)
    for i in range(len(sqlstate.fingerprint)):
        args.append(print_token(libinjection.sqli_get_token(sqlstate,i)))
    parse['folds'] = args
    parse['sqli'] = bool(libinjection.sqli_blacklist(sqlstate) and libinjection.sqli_not_whitelist(sqlstate))
    parse['fingerprint'] = fingerprint
    # todo add stats

    return parse

class PageHandler(tornado.web.RequestHandler):
    def get(self, pagename):
        if pagename == '':
            pagename = 'home'

        self.add_header('X-Content-Type-Options', 'nosniff')
        self.add_header('X-XSS-Protection', '0')

        self.render(
            pagename + '.html',
            title = pagename.replace('-',' '),
            ssl_protocol=self.request.headers.get('X-SSL-Protocol', ''),
            ssl_cipher=self.request.headers.get('X-SSL-Cipher', '')
        )

class XssTestHandler(tornado.web.RequestHandler):
    def get(self):
        settings = self.application.settings

        ldr = template.Loader(".")

        args = ['', '', '', '', '', '', '', '', '', '']

        qsl = [ x.split('=', 1) for x in self.request.query.split('&') ]
        for kv in qsl:
            print kv
            try:
                index = int(kv[0])
                val = tornado.escape.url_unescape(kv[1])
                print "XXX", index, val
                args[index] = val
            except Exception,e:
                print e

        self.add_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.add_header('Pragma', 'no-cache')
        self.add_header('Expires', '0')
        self.add_header('X-Content-Type-Options', 'nosniff')
        self.add_header('X-XSS-Protection', '0')

        self.write(ldr.load('xsstest.html').generate(args=args))

class DaysSinceHandler(tornado.web.RequestHandler):
    def get(self):
        lastevasion = datetime.date(2013, 9, 12)
        today       = datetime.date.today()
        daynum = (today - lastevasion).days
        if daynum < 10:
            days = "00" + str(daynum)
        elif daynum < 100:
            days = "0" + str(daynum)
        else:
            days = str(daynum)

        self.render(
            "days-since-last-bypass.html",
            title='libinjection: Days Since Last Bypass',
            days=days,
            ssl_protocol=self.request.headers.get('X-SSL-Protocol', ''),
            ssl_cipher=self.request.headers.get('X-SSL-Cipher', '')
        )

class NullHandler(tornado.web.RequestHandler):
    def get(self):
        arg = self.request.arguments.get('type', [])
        if len(arg) > 0 and arg[0] == 'tokens':
            return self.get_tokens()
        else:
            return self.get_fingerprints()

    def get_tokens(self):
        ids = self.request.arguments.get('id', [])

        if len(ids) == 1:
            formvalue = ids[0]
        else:
            formvalue = ''

        val = urllib.unquote(formvalue)
        parsed = []
        parsed.append(alltokens(val, libinjection.FLAG_QUOTE_NONE | libinjection.FLAG_SQL_ANSI))
        parsed.append(alltokens(val, libinjection.FLAG_QUOTE_NONE | libinjection.FLAG_SQL_MYSQL))
        parsed.append(alltokens(val, libinjection.FLAG_QUOTE_SINGLE | libinjection.FLAG_SQL_ANSI))
        parsed.append(alltokens(val, libinjection.FLAG_QUOTE_SINGLE | libinjection.FLAG_SQL_MYSQL))
        parsed.append(alltokens(val, libinjection.FLAG_QUOTE_DOUBLE | libinjection.FLAG_SQL_MYSQL))

        self.add_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.add_header('Pragma', 'no-cache')
        self.add_header('Expires', '0')
        self.add_header('X-Content-Type-Options', 'nosniff')
        self.add_header('X-XSS-Protection', '0')

        self.render("tokens.html",
                    title='libjection sqli token parsing diagnostics',
                    version = libinjection.version(),
                    parsed=parsed,
                    formvalue=val,
                    ssl_protocol=self.request.headers.get('X-SSL-Protocol', ''),
                    ssl_cipher=self.request.headers.get('X-SSL-Cipher', '')
                    )

    def get_fingerprints(self):
        #unquote = urllib.unquote
        #detectsqli = libinjection.detectsqli

        ids = self.request.arguments.get('id', [])
        if len(ids) == 1:
            formvalue = ids[0]
        else:
            formvalue = ''

        args = []
        extra = {}
        qssqli = False

        sqlstate = libinjection.sqli_state()

        allfp = {}
        for name,values in self.request.arguments.iteritems():
            if name == 'type':
                continue

            fps = []

            val = values[0]
            val = urllib.unquote(val)
            if len(val) == 0:
                continue
            libinjection.sqli_init(sqlstate, val, 0)
            pat = libinjection.sqli_fingerprint(sqlstate, libinjection.FLAG_QUOTE_NONE | libinjection.FLAG_SQL_ANSI)
            issqli = bool(libinjection.sqli_blacklist(sqlstate) and libinjection.sqli_not_whitelist(sqlstate))
            fps.append(['unquoted', 'ansi', issqli, pat])

            pat = libinjection.sqli_fingerprint(sqlstate, libinjection.FLAG_QUOTE_NONE | libinjection.FLAG_SQL_MYSQL)
            issqli = bool(libinjection.sqli_blacklist(sqlstate) and libinjection.sqli_not_whitelist(sqlstate))
            fps.append(['unquoted', 'mysql', issqli, pat])

            pat = libinjection.sqli_fingerprint(sqlstate, libinjection.FLAG_QUOTE_SINGLE | libinjection.FLAG_SQL_ANSI)
            issqli = bool(libinjection.sqli_blacklist(sqlstate) and libinjection.sqli_not_whitelist(sqlstate))
            fps.append(['single', 'ansi', issqli, pat])

            pat = libinjection.sqli_fingerprint(sqlstate, libinjection.FLAG_QUOTE_SINGLE | libinjection.FLAG_SQL_MYSQL)
            issqli = bool(libinjection.sqli_blacklist(sqlstate) and libinjection.sqli_not_whitelist(sqlstate))
            fps.append(['single', 'mysql', issqli, pat])

            pat = libinjection.sqli_fingerprint(sqlstate, libinjection.FLAG_QUOTE_DOUBLE | libinjection.FLAG_SQL_MYSQL)
            issqli = bool(libinjection.sqli_blacklist(sqlstate) and libinjection.sqli_not_whitelist(sqlstate))
            fps.append(['double', 'mysql', issqli, pat])

            allfp[name] = {
                'value': breakify(breakapart(val)),
                'fingerprints': fps
            }

        for name,values in self.request.arguments.iteritems():
            if name == 'type':
                continue
            for val in values:
                # do it one more time include cut-n-paste was already url-encoded
                val = urllib.unquote(val)
                if len(val) == 0:
                    continue

                # swig returns 1/0, convert to True False
                libinjection.sqli_init(sqlstate, val, 0)
                issqli = bool(libinjection.is_sqli(sqlstate))

                # True if any issqli values are true
                qssqli = qssqli or issqli
                val = breakapart(val)

                pat = sqlstate.fingerprint
                if not issqli:
                    pat = 'see below'
                args.append([name, val, issqli, pat])

        self.add_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.add_header('Pragma', 'no-cache')
        self.add_header('Expires', '0')
        self.add_header('X-Content-Type-Options', 'nosniff')
        self.add_header('X-XSS-Protection', '0')

        self.render("form.html",
                    title='libjection sqli diagnostic',
                    version = libinjection.version(),
                    is_sqli=qssqli,
                    args=args,
                    allfp = allfp,
                    formvalue=formvalue,
                    ssl_protocol=self.request.headers.get('X-SSL-Protocol', ''),
                    ssl_cipher=self.request.headers.get('X-SSL-Cipher', '')
                    )

import os
settings = {
    "static_path": os.path.join(os.path.dirname(__file__), "static"),
    "template_path": os.path.join(os.path.dirname(__file__), "."),
    "xsrf_cookies": False,
    "gzip": False
}

application = tornado.web.Application([
    (r"/diagnostics", NullHandler),
    (r'/xsstest', XssTestHandler),
    (r'/bootstrap/(.*)', tornado.web.StaticFileHandler, {'path': '/opt/bootstrap' }),
    (r'/jquery/(.*)', tornado.web.StaticFileHandler, {'path': '/opt/jquery' }),
    (r'/robots.txt', tornado.web.StaticFileHandler, {'path': os.path.join(os.path.dirname(__file__), "static")}),
    (r'/favicon.ico', tornado.web.StaticFileHandler, {'path': os.path.join(os.path.dirname(__file__), "static")}),
    (r"/([a-z-]*)", PageHandler)
    ], **settings)


if __name__ == "__main__":
    tornado.options.parse_command_line()

    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(process)d %(message)s")

    application.listen(8888)
    tornado.ioloop.IOLoop.instance().start()

