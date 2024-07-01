#!/usr/bin/env python
#
#  Copyright 2012, 2013 Nick Galbreath
#  nickg@client9.com
#  BSD License -- see COPYING.txt for details
#

"""
Converts a libinjection JSON data file to a C header (.h) file
"""

def toc(obj):
    """ main routine """
    if False:
        print 'fingerprints = {'
        for  fp in sorted(obj[u'fingerprints']):
            print "['{0}']='X',".format(fp)
        print '}'

    words = {}
    keywords = obj['keywords']

    for k,v in keywords.iteritems():
        words[str(k)] = str(v)

    for  fp in list(obj[u'fingerprints']):
        fp = '0' + fp.upper()
        words[str(fp)] = 'F';

    print 'words = {'
    for k in sorted(words.keys()):
        #print "['{0}']='{1}',".format(k, words[k])
        print "['{0}']={1},".format(k, ord(words[k]))
    print '}'
    return 0

if __name__ == '__main__':
    import sys
    import json
    sys.exit(toc(json.load(sys.stdin)))

