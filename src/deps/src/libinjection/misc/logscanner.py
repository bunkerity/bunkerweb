#!/usr/bin/env python
import sys
import re
import libinjection
import urllib
import urlparse

logre = re.compile(r' /diagnostics\?([^ ]+) HTTP')

notsqli = set([
'1ov',
'UEvEv',
'v',
'Uv',
'Uv,',
'UoEvE',
'1v',
'sov',
'1nn',
'UonnE',
'no1',
'Evk',
'E1k',
'E11k',
'Ek',
'Uv,Ev',
'UvEvk',
'UvEv,',
'Uvon'
])

def doline(logline):
    """
    ...GET /diagnostics?id=%22union+select HTTP/1.1
    """
    mo = logre.search(logline)
    if not mo:
        return

    sqli= False
    fp = None
    for key, val in urlparse.parse_qsl(mo.group(1)):
        val = urllib.unquote(val)
        extra = {}
        argsqli = libinjection.detectsqli(val, extra)
        if argsqli:
            fp = extra['fingerprint']
            print urllib.quote(val)
        sqli = sqli or argsqli

    if False: # and not sqli:
        #print "\n---"
        #print mo.group(1)
        for key, val in urlparse.parse_qsl(mo.group(1)):
            val = urllib.unquote(val)
            extra = {}
            argsqli = libinjection.detectsqli(val, extra)
            if not argsqli and extra['fingerprint'] not in notsqli:
                print "NO", extra['fingerprint'], mo.group(1)
                print "  ", val

if __name__ == '__main__':
    for line in sys.stdin:
        doline(line)
