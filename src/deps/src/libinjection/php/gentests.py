#!/usr/bin/env python3

"""
Takes testing files and turns them PHP module tests
"""

import glob
import os

def phpescape(s):
    """
    escapes plain text into php-code
    """
    return s.replace("\\", "\\\\").replace("$", "\\$")

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

def gentest_tokens():
    """
    generate token phpt test
    """
    for testname in sorted(glob.glob('../tests/test-tokens-*.txt')):
        data =  readtestdata(os.path.join('../tests', testname))
        testname = os.path.basename(testname)
        phpt = """
--TEST--
{1}
--FILE--
<?php
require(sprintf("%s/../testsupport.php", dirname(__FILE__)));
$sqlistate = new_libinjection_sqli_state();
$s = <<<EOT
{2}
EOT;
$s = trim($s);
libinjection_sqli_init($sqlistate, $s, FLAG_QUOTE_NONE | FLAG_SQL_ANSI);
while (libinjection_sqli_tokenize($sqlistate)) {{
  echo(print_token(libinjection_sqli_state_current_get($sqlistate)) . "\\n");
}}
--EXPECT--
{3}
"""
        phpt = phpt.format(testname, data[0], phpescape(data[1]), data[2])

        with open('build/tests/' + testname.replace('.txt', '.phpt'), 'w') as fd:
            fd.write(phpt.strip())


def gentest_folding():
    for testname in sorted(glob.glob('../tests/test-folding-*.txt')):
        data =  readtestdata(os.path.join('../tests', testname))
        testname = os.path.basename(testname)
        phpt = """
--TEST--
{1}
--FILE--
<?php
require(sprintf("%s/../testsupport.php", dirname(__FILE__)));
$sqlistate = new_libinjection_sqli_state();
$s = <<<EOT
{2}
EOT;
$s = trim($s);
libinjection_sqli_init($sqlistate, $s, FLAG_QUOTE_NONE | FLAG_SQL_ANSI);
$fingerprint = libinjection_sqli_fingerprint($sqlistate, FLAG_QUOTE_NONE | FLAG_SQL_ANSI);
for ($i  = 0; $i < strlen($fingerprint); $i++) {{
  echo(print_token(libinjection_sqli_get_token($sqlistate, $i)) . "\\n");
}}
--EXPECT--
{3}
"""
        phpt = phpt.format(testname, data[0], phpescape(data[1]), data[2])

        with open('build/tests/' + testname.replace('.txt', '.phpt'), 'w') as fd:
            fd.write(phpt.strip())

def gentest_fingerprints():
    """
    generate phpt for testing sqli testing
    """
    for testname in sorted(glob.glob('../tests/test-sqli-*.txt')):
        data =  readtestdata(os.path.join('../tests', testname))
        testname = os.path.basename(testname)
        phpt = """
--TEST--
{0}
--DESCRIPTION--
{1}
--FILE--
<?php
require(sprintf("%s/../testsupport.php", dirname(__FILE__)));
$sqlistate = new_libinjection_sqli_state();
$s = <<<EOT
{2}
EOT;
$s = trim($s);
libinjection_sqli_init($sqlistate, $s, FLAG_QUOTE_NONE | FLAG_SQL_ANSI);
$ok = libinjection_is_sqli($sqlistate);
if ($ok == 1) {{
    echo(libinjection_sqli_state_fingerprint_get($sqlistate) . "\n");
}}
--EXPECT--
{3}
"""
        phpt = phpt.format(testname, data[0], phpescape(data[1]), data[2])

        with open('build/tests/' + testname.replace('.txt', '.phpt'), 'w') as fd:
            fd.write(phpt.strip())


if __name__ == '__main__':
    gentest_tokens()
    gentest_folding()
    gentest_fingerprints()
