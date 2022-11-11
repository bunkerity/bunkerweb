#!/usr/bin/env python3
#
#  Copyright 2012, 2013 Nick Galbreath
#  nickg@client9.com
#  BSD License -- see COPYING.txt for details
#

"""
Converts a libinjection JSON data file to PHP array
"""

def toc(obj):
    """ main routine """

    print("""<?php
function lookup($state, $stype, $keyword) {
    $keyword = struper(keyword);
    if ($stype == libinjection.LOOKUP_FINGERPRINT) {
        if ($keyword == $fingerprints && libinjection.sqli_not_whitelist($state)) {
            return 'F';
        } else {
            return chr(0);
        }
    }
    return $words.get(keyword, chr(0));
}
""")

    words = {}
    keywords = obj['keywords']
    for k,v in keywords.items():
        words[str(k)] = str(v)

    print('$words = array(')
    for k in sorted(words.keys()):
        print("'{0}' => '{1}',".format(k, words[k]))
    print(');\n')


    keywords = obj['fingerprints']
    print('$fingerprints = array(')
    for k in sorted(keywords):
        print("'{0}',".format(k.upper()))
    print(');')

    return 0

if __name__ == '__main__':
    import sys
    import json
    sys.exit(toc(json.load(sys.stdin)))


