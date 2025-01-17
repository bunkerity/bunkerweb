#!/usr/bin/env python

"""
Generates a Lua table of fingerprints.
One can then add, turn off or delete fingerprints from lua.
"""

def make_lua_table(obj):
    """
    Generates table.  Fingerprints don't contain any special chars
    so they don't need to be escaped.  The output may be
    sorted but it is not required.
    """
    fp = obj[u'fingerprints']
    print("sqlifingerprints = {")
    for f in fp:
        print('  ["{0}"]=true,'.format(f))
    print("}")
    return 0

if __name__ == '__main__':
    import sys
    import json
    with open('../c/sqlparse_data.json', 'r') as fd:
        make_lua_table(json.load(fd))

