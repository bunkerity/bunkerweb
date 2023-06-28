#!/usr/bin/env python3

from jinja2 import Environment, FileSystemLoader

import re

ANCHOR_START = '((?:--|#) START AUTO GENERATED CODE)'
ANCHOR_END = '((?:--|#) END AUTO GENERATED CODE)'

LUA_TYPES = ('number', 'string', 'table')

data = {
  "x509": __import__("type_x509").defines,
  "x509.csr": __import__("type_x509_req").defines,
  "x509.crl": __import__("type_x509_crl").defines,
}

from types_test import tests

fl = FileSystemLoader('templates')
env = Environment(loader=fl)

tmpl = {
    "output": env.get_template('x509_functions.j2'),
    "output_test": env.get_template('x509_tests.j2')
}

for k in tmpl:
    for modname in data:
        mod = data[modname]
        output = mod[k]
        ct = None
        with open(output, "r") as f:
            ct = f.read()
        
        test_idx = re.findall('TEST (\d+)(?!.+AUTOGEN)', ct)
        if test_idx:
            test_idx = max([int(i) for i in test_idx]) + 1
        else:
            test_idx = None
        
        repl = tmpl[k].render(
            module=mod,
            modname=modname,
            test_idx=test_idx,
            tests=tests,
            LUA_TYPES=LUA_TYPES,
        )

        ct = re.sub(
            ANCHOR_START + '.+' + ANCHOR_END,
            '\g<1>\n' + repl + '\n\g<2>',
            ct,
            flags = re.DOTALL,
        )

        open(output, 'w').write(ct)

        print("%-40s: wrote %d %s (%dl)" % (
            output,
            len(re.findall("(?:_M\:|===)", ct)),
            "tests" if k == 'output_test' else 'functions',
            len(repl.split('\n')))
        )