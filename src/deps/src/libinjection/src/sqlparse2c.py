#!/usr/bin/env python3
#
#  Copyright 2012, 2013 Nick Galbreath
#  nickg@client9.com
#  BSD License -- see COPYING.txt for details
#

"""
Converts a libinjection JSON data file to a C header (.h) file
"""

import sys

def toc(obj):
    """ main routine """

    print("""
#ifndef LIBINJECTION_SQLI_DATA_H
#define LIBINJECTION_SQLI_DATA_H

#include "libinjection.h"
#include "libinjection_sqli.h"

typedef struct {
    const char *word;
    char type;
} keyword_t;

static size_t parse_money(sfilter * sf);
static size_t parse_other(sfilter * sf);
static size_t parse_white(sfilter * sf);
static size_t parse_operator1(sfilter *sf);
static size_t parse_char(sfilter *sf);
static size_t parse_hash(sfilter *sf);
static size_t parse_dash(sfilter *sf);
static size_t parse_slash(sfilter *sf);
static size_t parse_backslash(sfilter * sf);
static size_t parse_operator2(sfilter *sf);
static size_t parse_string(sfilter *sf);
static size_t parse_word(sfilter * sf);
static size_t parse_var(sfilter * sf);
static size_t parse_number(sfilter * sf);
static size_t parse_tick(sfilter * sf);
static size_t parse_ustring(sfilter * sf);
static size_t parse_qstring(sfilter * sf);
static size_t parse_nqstring(sfilter * sf);
static size_t parse_xstring(sfilter * sf);
static size_t parse_bstring(sfilter * sf);
static size_t parse_estring(sfilter * sf);
static size_t parse_bword(sfilter * sf);
""")

    #
    # Mapping of character to function
    #
    fnmap = {
        'CHAR_WORD' : 'parse_word',
        'CHAR_WHITE': 'parse_white',
        'CHAR_OP1'  : 'parse_operator1',
	'CHAR_UNARY': 'parse_operator1',
        'CHAR_OP2'  : 'parse_operator2',
	'CHAR_BANG' : 'parse_operator2',
        'CHAR_BACK' : 'parse_backslash',
        'CHAR_DASH' : 'parse_dash',
        'CHAR_STR'  : 'parse_string',
        'CHAR_HASH' : 'parse_hash',
        'CHAR_NUM'  : 'parse_number',
        'CHAR_SLASH': 'parse_slash',
        'CHAR_SEMICOLON' : 'parse_char',
	'CHAR_COMMA': 'parse_char',
	'CHAR_LEFTPARENS': 'parse_char',
	'CHAR_RIGHTPARENS': 'parse_char',
	'CHAR_LEFTBRACE': 'parse_char',
	'CHAR_RIGHTBRACE': 'parse_char',
        'CHAR_VAR'  : 'parse_var',
        'CHAR_OTHER': 'parse_other',
        'CHAR_MONEY': 'parse_money',
        'CHAR_TICK' : 'parse_tick',
        'CHAR_UNDERSCORE': 'parse_underscore',
        'CHAR_USTRING'   : 'parse_ustring',
        'CHAR_QSTRING'   : 'parse_qstring',
        'CHAR_NQSTRING'  : 'parse_nqstring',
        'CHAR_XSTRING'   : 'parse_xstring',
        'CHAR_BSTRING'   : 'parse_bstring',
        'CHAR_ESTRING'   : 'parse_estring',
        'CHAR_BWORD'     : 'parse_bword'
        }
    print()
    print("typedef size_t (*pt2Function)(sfilter *sf);")
    print("static const pt2Function char_parse_map[] = {")
    pos = 0
    for character in obj['charmap']:
        print("   &%s, /* %d */" % (fnmap[character], pos))
        pos += 1
    print("};")
    print()

    # keywords
    #  load them
    keywords = obj['keywords']

    for  fingerprint in list(obj['fingerprints']):
        fingerprint = '0' + fingerprint.upper()
        keywords[fingerprint] = 'F'

    needhelp = []
    for key  in keywords.keys():
        if key != key.upper():
            needhelp.append(key)

    for key in needhelp:
        tmpv = keywords[key]
        del keywords[key]
        keywords[key.upper()] = tmpv

    print("static const keyword_t sql_keywords[] = {")
    for k in sorted(keywords.keys()):
        if len(k) > 31:
            sys.stderr.write("ERROR: keyword greater than 32 chars\n")
            sys.exit(1)

        print("    {\"%s\", '%s'}," % (k, keywords[k]))
    print("};")
    print("static const size_t sql_keywords_sz = %d;" % (len(keywords), ))

    print("#endif")
    return 0

if __name__ == '__main__':
    import json
    sys.exit(toc(json.load(sys.stdin)))

