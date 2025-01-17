#!/usr/bin/env python

from libinjection import *

sqli= "1 UNION ALL SELECT * FROM FOO"

if False:
    s = sfilter()
    print sqli_fingerprint(s, sqli, CHAR_NULL, COMMENTS_ANSI)
    print "----"

if False:
    s = sfilter()
    current = stoken_t()
    sqli_init(s, sqli, CHAR_NULL, COMMENTS_ANSI)
    while sqli_tokenize(s, current):
        print current.type, current.val
    print "----"

def is_pattern(state):
    return sqli_blacklist(state) and sqli_not_whitelist(state)

s = sfilter()

if is_sqli(s, sqli, None):
    print "IS SQLI"
    print len(s.pat)
    print s.current.val
    print s.current.type
    vec = s.tokenvec
    for i in range(len(s.pat)):
        atoken = vec[i]
        print atoken.type, atoken.val
else:
    print "IS NOT SQLI"
