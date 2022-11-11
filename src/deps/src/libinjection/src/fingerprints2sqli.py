#!/usr/bin/env python3
"""
Small script to convert fingerprints back to SQL or SQLi
"""
import subprocess


RMAP = {
    '1': '1',
    'f': 'convert',
    '&': 'and',
    'v': '@version',
    'n': 'aname',
    's': "\"1\"",
    '(': '(',
    ')': ')',
    'o': '*',
    'E': 'select',
    'U': 'union',
    'k': "JOIN",
    't': 'binary',
    ',': ',',
    ';': ';',
    'c': ' -- comment',
    'T': 'DROP',
    ':': ':',
    'A': 'COLLATE',
    'B': 'group by',
    'X': '/* /* nested comment */ */'
}

def fingerprint_to_sqli():
    """
    main code, expects to be run in main libinjection/src directory
    and hardwires "fingerprints.txt" as input file
    """
    mode = 'print'
    fingerprints = []
    with open('fingerprints.txt', 'r') as openfile:
        for line in openfile:
            fingerprints.append(line.strip())

    for fingerprint in fingerprints:
        sql = []
        for char in fingerprint:
            sql.append(RMAP[char])

        sqlstr = ' '.join(sql)
        if mode == 'print':
            print(fingerprint, ' '.join(sql))
        else:
            args = ['./fptool', '-0', sqlstr]
            actualfp = subprocess.check_output(args).strip()
            if fingerprint != actualfp:
                print(fingerprint, actualfp, ' '.join(sql))


if __name__ == '__main__':
    fingerprint_to_sqli()

