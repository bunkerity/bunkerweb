#!/usr/bin/env python

import glob
import sys

def readtestdata(filename):
    """
    Read a test file and split into components
    """

    state = None
    info = {
        '--TEST--': '',
        '--INPUT--': '',
        '--EXPECTED--': ''
        }

    for line in open(filename, 'r'):
        line = line.rstrip()
        if line in ('--TEST--', '--INPUT--', '--EXPECTED--'):
            state = line
        elif state:
            info[state] += line + '\n'

    # remove last newline from input
    info['--INPUT--'] = info['--INPUT--'][0:-1]

    return (info['--TEST--'], info['--INPUT--'].strip(), info['--EXPECTED--'].strip())

def luaescape(s):
    return s.strip().replace("\\", "\\\\").replace("\n", "\\n").replace("'", "\\'")

def genluatest(fname, data):
    # TBD: change to python os.path
    name = fname.split('/')[-1]
    if name.startswith('test-tokens-'):
        testname = 'test_tokens'
        extra = "\\n"
    elif name.startswith('test-tokens_mysql'):
        testname = 'test_tokens_mysql'
        extra = "\\n"
    elif name.startswith('test-folding-'):
        testname = 'test_folding'
        extra = "\\n"
    elif name.startswith('test-sqli-'):
        testname = 'test_fingerprints'
        extra = ''
    else:
        #print "IGNORING: " + name
        return

    name = name.replace('.txt', '')

    print "is({0}('{1}'),\n   '{2}{3}',\n   '{4}')\n".format(
        testname,
        luaescape(data[1]),
        extra,
        luaescape(data[2]),
        name
    )

def test2lua(fname):
    data = readtestdata(fname)
    genluatest(fname, data)

def main():
    print "require 'testdriver'\n"
    files = glob.glob('../tests/test-*.txt')
    print "plan({0})\n".format(len(files))
    for testfile in sorted(files):
        test2lua(testfile)

if __name__ == '__main__':
    main()
