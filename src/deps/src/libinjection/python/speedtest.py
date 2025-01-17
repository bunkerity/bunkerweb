#!/usr/bin/env python
from libinjection import *
from words import *
import time

def lookup_null(state, style, keyword):
    return ''

def lookup_c(state, style, keyword):
    return ''
    #return sqli_lookup_word(state, style, keyword)

def lookup_upcase(state, stype, keyword):
    if stype == libinjection.LOOKUP_FINGERPRINT:
        return words.get('0' + keyword.upper(), '')
    else:
        return words.get(keyword.upper(), '')

def main():

    inputs = (
        "123 LIKE -1234.5678E+2;",
        "APPLE 19.123 'FOO' \"BAR\"",
        "/* BAR */ UNION ALL SELECT (2,3,4)",
        "1 || COS(+0X04) --FOOBAR",
        "dog apple @cat banana bar",
        "dog apple cat \"banana \'bar",
        "102 TABLE CLOTH"
        )
    imax = 100000

    t0 = time.clock()
    sfilter = sqli_state()
    for i in xrange(imax):
        s = inputs[i % 7]
        sqli_init(sfilter, s, 0)
        is_sqli(sfilter)
    t1 = time.clock()
    total = imax / (t1 - t0)
    print("python->c TPS            = {0}".format(total))

    t0 = time.clock()
    sfilter = sqli_state()
    for i in xrange(imax):
        s = inputs[i % 7]
        sqli_init(sfilter, s, 0)
        sqli_callback(sfilter, lookup_null)
        is_sqli(sfilter)
    t1 = time.clock()
    total = imax / (t1 - t0)
    print("python lookup_null TPS    = {0}".format(total))

    t0 = time.clock()
    sfilter = sqli_state()
    for i in xrange(imax):
        s = inputs[i % 7]
        sqli_init(sfilter, s, 0)
        sqli_callback(sfilter, lookup_upcase)
        is_sqli(sfilter)
    t1 = time.clock()
    total = imax / (t1 - t0)
    print("python lookup_upcase TPS    = {0}".format(total))

    t0 = time.clock()
    sfilter = sqli_state()
    for i in xrange(imax):
        s = inputs[i % 7]
        sqli_init(sfilter, s, 0)
        sqli_callback(sfilter, lookup_c)
        is_sqli(sfilter)
    t1 = time.clock()
    total = imax / (t1 - t0)
    print("python lookup_c TPS    = {0}".format(total))


    t0 = time.clock()
    sfilter = sqli_state()
    for i in xrange(imax):
        s = inputs[i % 7]
        sqli_init(sfilter, s, 0)
        sqli_callback(sfilter, lookup)
        is_sqli(sfilter)
    t1 = time.clock()
    total = imax / (t1 - t0)
    print("python lookup TPS = {0}".format(total))


if __name__ == '__main__':
    main()
