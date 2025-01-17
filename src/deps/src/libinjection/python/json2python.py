#!/usr/bin/env python
#
#  Copyright 2012, 2013 Nick Galbreath
#  nickg@client9.com
#  BSD License -- see COPYING.txt for details
#

"""
Converts a libinjection JSON data file to python dict
"""

def toc(obj):
    """ main routine """

    print """
import libinjection

def lookup(state, stype, keyword):
    keyword = keyword.upper()
    if stype == libinjection.LOOKUP_FINGERPRINT:
        if keyword in fingerprints and libinjection.sqli_not_whitelist(state):
            return 'F'
        else:
            return chr(0)
    return words.get(keyword, chr(0))

"""

    words = {}
    keywords = obj['keywords']
    for k,v in keywords.iteritems():
        words[str(k)] = str(v)

    print 'words = {'
    for k in sorted(words.keys()):
        print "'{0}': '{1}',".format(k, words[k])
    print '}\n'


    keywords = obj['fingerprints']
    print 'fingerprints = set(['
    for k in sorted(keywords):
        print "'{0}',".format(k.upper())
    print '])'

    return 0

if __name__ == '__main__':
    import sys
    import json
    sys.exit(toc(json.load(sys.stdin)))

