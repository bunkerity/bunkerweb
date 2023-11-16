#!/usr/bin/python

"""
Work-in-progress
"""

from libinjection import *
from words import words

print dir(libinjection)

def print_token_string(tok):
    """
    returns the value of token, handling opening and closing quote characters
    """
    out = ''
    if tok.str_open != "\0":
        out += tok.str_open
    out += tok.val
    if tok.str_close != "\0":
        out += tok.str_close
    return out

def print_token(tok):
    """
    prints a token for use in unit testing
    """
    out = ''
    out += tok.type
    out += ' '
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
    return out

def lookup(state, stype, keyword):
    keyword = keyword.upper()
    if stype == 'v':
        keyword = '0' + keyword
    ch = words.get(keyword, '')
    return ch

sqli = '1 union all select 1 --'

s = sqli_state()
sqli_init(s, sqli, libinjection.FLAG_QUOTE_NONE | libinjection.FLAG_SQL_ANSI)
sqli_callback(s, lookup)

while sqli_tokenize(s):
    print print_token(s.current)
