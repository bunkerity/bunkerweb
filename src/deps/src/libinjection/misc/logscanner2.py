#!/usr/bin/env python

import datetime
import json
import sys
from urlparse import *
import urllib
import libinjection

from tornado import template
from tornado.escape import *

import re
import calendar

months = {
    'Jan':'01',
    'Feb':'02',
    'Mar':'03',
    'Apr':'04',
    'May':'05',
    'Jun':'06',
    'Jul':'07',
    'Aug':'08',
    'Sep':'09',
    'Oct':'10',
    'Nov':'11',
    'Dec':'12'
}

# "time_iso8601":"2013-08-04T03:51:18+00:00"
def parse_date(datestr):
    elems = (
        datestr[7:11],
        months[datestr[3:6]],
        datestr[0:2],
        datestr[12:14],
        datestr[15:17],
        datestr[18:20],
    )

    return ( "{0}-{1}-{2}T{3}:{4}:{5}+00:00".format(*elems), calendar.timegm( [ int(i) for i in elems] ) )


apachelogre = re.compile(r'^(\S*) (\S*) (\S*) \[([^\]]+)\] \"([^"\\]*(?:\\.[^"\\]*)*)\" (\S*) (\S*) \"([^"\\]*(?:\\.[^"\\]*)*)\" \"([^"]*)\" \"([^"]*)\"')

def parse_apache(line):
    mo = apachelogre.match(line)
    if not mo:
        return None
    (time_iso, timestamp) = parse_date(mo.group(4))
    try:
        (method, uri, protocol) = mo.group(5).split(' ', 2)
    except ValueError:
        (method, uri, protocol) = ('-', '-', '-')
    data = {
        'remote_addr': mo.group(1),
        'time_iso8601': time_iso,
        'timestamp'   : timestamp,
        'request_protocol': protocol,
        'request_method': method,
        'request_uri': uri,
        'request_length': '',
        'request_time': '',
        'status': mo.group(6),
        'bytes_sent': '',
        'body_bytes-sent': int(mo.group(7)),
        'http_referrer': mo.group(8),
        'http_user_agent': mo.group(9),
        'ssl_cipher': '',
        'ssl_protocol': ''
    }
    return data

# http://stackoverflow.com/questions/312443/how-do-you-split-a-list-into-evenly-sized-chunks-in-python
def chunks(l, n):
    """
    Yield successive n-sized chunks from l.
    """
    for i in xrange(0, len(l), n):
        yield l[i:i+n]

def breakify(s):
    output = ""
    for c in chunks(s, 40):
        output += c
        if ' ' not in c:
            output += ' '
    return output

def doline(line):

    line = line.replace("\\x", "%").strip()
    try:
        data = json.loads(line)
    except ValueError, e:
        data = parse_apache(line)

    if data is None:
        sys.stderr.write("BAD LINE: {0}\n".format(line))
        return None

    if  not data.get('request_uri','').startswith("/diagnostics"):
        return None

    urlparts = urlparse(data['request_uri'])
    if len(urlparts.query) == 0:
        return None

    qsl = [ x.split('=', 1) for x in urlparts.query.split('&') ]

    target = None
    for k,v in qsl:
        if k == 'id':
            target = v
            break

    if target is None:
        #print "no 'id'"
        return None

    # part one, normal decode
    target = urllib.unquote_plus(target)

    # do it again, but preserve '+'
    target = urllib.unquote(target)

    sstate = libinjection.sqli_state()
    # BAD the string created by target.encode is stored in
    #   sstate but not reference counted, so it can get
    #   deleted by python
    #    libinjection.sqli_init(sstate, target.encode('utf-8'), 0)

    # instead make a temporary var in python
    # with the same lifetime as sstate (above)
    try:
        targetutf8 = target.encode('utf-8')
        #targetutf8 = target
    except UnicodeDecodeError, e:
        targetutf8 = target
        #if type(target) == str:
        #    sys.stderr.write("Target is a string\n")
        #if type(target) == unicode:
        #    sys.stderr.write("Target is unicde\n")
        #sys.stderr.write("OOps: {0}\n".format(e))
        #sys.stderr.write("Encode error: {0}\n".format(target))


    try:
        libinjection.sqli_init(sstate, targetutf8, 0)
    except TypeError:
        sys.stderr.write("fail in decode: {0}".format(targetutf8))
        if type(target) == str:
            sys.stderr.write("Target is a string\n")
        if type(target) == unicode:
            sys.stderr.write("Target is unicde\n")
        return None

    sqli = bool(libinjection.is_sqli(sstate))

    return (target, sqli, sstate.fingerprint, data['remote_addr'])

if __name__ == '__main__':
    s = """
174.7.27.149 - - [29/Jul/2013:01:30:19 +0000] "GET /diagnostics?id=x|x||1&type=fingerprints HTTP/1.1" 200 1327 "-" "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/28.0.1500.72 Safari/537.36" "-"
"""
    s = """
{"timestamp":1371091563,"remote_ip":"219.110.171.2","request":"/diagnostics?id=1+UNION+ALL+SELECT+1<<<&type=fingerprints","method":"GET","status":200,"user_agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_8_4) AppleWebKit/536.30.1 (KHTML, like Gecko) Version/6.0.5 Safari/536.30.1","referrer":"https://libinjection.client9.com/diagnostics","duration_usec":160518 }
{"timestamp":1371091563,"remote_ip":"219.110.171.2","request":"/diagnostics?id=2+UNION+ALL+SELECT+1<<<&type=fingerprints","method":"GET","status":200,"user_agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_8_4) AppleWebKit/536.30.1 (KHTML, like Gecko) Version/6.0.5 Safari/536.30.1","referrer":"https://libinjection.client9.com/diagnostics","duration_usec":160518 }
"""
    if len(sys.argv) == 2:
        fh = open(sys.argv[1], 'r')
    else:
        fh = sys.stdin

    targets = set()
    table = []
    for line in fh:
        parts = doline(line.strip())
        if parts is None:
            continue

        # help it render in HTML
        if parts[0] in targets:
            continue
        else:
            targets.add(parts[0])

            # add link
            # add form that might render ok in HTML
            # is sqli
            # fingerprint
            table.append( (
                "/diagnostics?id=" + url_escape(parts[0]),
                breakify(parts[0].replace(',', ', ').replace('/*', ' /*')),
                parts[1],
                parts[2],
                parts[3]
                )
            )

    table = reversed(table)

    loader = template.Loader(".")

    txt = loader.load("logtable.html").generate(
        table=table,
        now = str(datetime.datetime.now()),
        ssl_protocol='',
        ssl_cipher=''
        )

    print txt
