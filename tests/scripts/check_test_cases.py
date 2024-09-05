#!/usr/bin/env python3

"""Sanity checks for test data.

This program contains a class for traversing test cases that can be used
independently of the checks.
"""

# Copyright The Mbed TLS Contributors
# SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later

import argparse
import glob
import os
import re
import subprocess
import sys

class ScriptOutputError(ValueError):
    """A kind of ValueError that indicates we found
    the script doesn't list test cases in an expected
    pattern.
    """

    @property
    def script_name(self):
        return super().args[0]

    @property
    def idx(self):
        return super().args[1]

    @property
    def line(self):
        return super().args[2]

class Results:
    """Store file and line information about errors or warnings in test suites."""

    def __init__(self, options):
        self.errors = 0
        self.warnings = 0
        self.ignore_warnings = options.quiet

    def error(self, file_name, line_number, fmt, *args):
        sys.stderr.write(('{}:{}:ERROR:' + fmt + '\n').
                         format(file_name, line_number, *args))
        self.errors += 1

    def warning(self, file_name, line_number, fmt, *args):
        if not self.ignore_warnings:
            sys.stderr.write(('{}:{}:Warning:' + fmt + '\n')
                             .format(file_name, line_number, *args))
            self.warnings += 1

class TestDescriptionExplorer:
    """An iterator over test cases with descriptions.

The test cases that have descriptions are:
* Individual unit tests (entries in a .data file) in test suites.
* Individual test cases in ssl-opt.sh.

This is an abstract class. To use it, derive a class that implements
the process_test_case method, and call walk_all().
"""

    def process_test_case(self, per_file_state,
                          file_name, line_number, description):
        """Process a test case.

per_file_state: an object created by new_per_file_state() at the beginning
                of each file.
file_name: a relative path to the file containing the test case.
line_number: the line number in the given file.
description: the test case description as a byte string.
"""
        raise NotImplementedError

    def new_per_file_state(self):
        """Return a new per-file state object.

The default per-file state object is None. Child classes that require per-file
state may override this method.
"""
        #pylint: disable=no-self-use
        return None

    def walk_test_suite(self, data_file_name):
        """Iterate over the test cases in the given unit test data file."""
        in_paragraph = False
        descriptions = self.new_per_file_state() # pylint: disable=assignment-from-none
        with open(data_file_name, 'rb') as data_file:
            for line_number, line in enumerate(data_file, 1):
                line = line.rstrip(b'\r\n')
                if not line:
                    in_paragraph = False
                    continue
                if line.startswith(b'#'):
                    continue
                if not in_paragraph:
                    # This is a test case description line.
                    self.process_test_case(descriptions,
                                           data_file_name, line_number, line)
                in_paragraph = True

    def collect_from_script(self, script_name):
        """Collect the test cases in a script by calling its listing test cases
option"""
        descriptions = self.new_per_file_state() # pylint: disable=assignment-from-none
        listed = subprocess.check_output(['sh', script_name, '--list-test-cases'])
        # Assume test file is responsible for printing identical format of
        # test case description between --list-test-cases and its OUTCOME.CSV
        #
        # idx indicates the number of test case since there is no line number
        # in the script for each test case.
        for idx, line in enumerate(listed.splitlines()):
            # We are expecting the script to list the test cases in
            # `<suite_name>;<description>` pattern.
            script_outputs = line.split(b';', 1)
            if len(script_outputs) == 2:
                suite_name, description = script_outputs
            else:
                raise ScriptOutputError(script_name, idx, line.decode("utf-8"))

            self.process_test_case(descriptions,
                                   suite_name.decode('utf-8'),
                                   idx,
                                   description.rstrip())

    @staticmethod
    def collect_test_directories():
        """Get the relative path for the TLS and Crypto test directories."""
        if os.path.isdir('tests'):
            tests_dir = 'tests'
        elif os.path.isdir('suites'):
            tests_dir = '.'
        elif os.path.isdir('../suites'):
            tests_dir = '..'
        directories = [tests_dir]
        return directories

    def walk_all(self):
        """Iterate over all named test cases."""
        test_directories = self.collect_test_directories()
        for directory in test_directories:
            for data_file_name in glob.glob(os.path.join(directory, 'suites',
                                                         '*.data')):
                self.walk_test_suite(data_file_name)

            for sh_file in ['ssl-opt.sh', 'compat.sh']:
                sh_file = os.path.join(directory, sh_file)
                self.collect_from_script(sh_file)

class TestDescriptions(TestDescriptionExplorer):
    """Collect the available test cases."""

    def __init__(self):
        super().__init__()
        self.descriptions = set()

    def process_test_case(self, _per_file_state,
                          file_name, _line_number, description):
        """Record an available test case."""
        base_name = re.sub(r'\.[^.]*$', '', re.sub(r'.*/', '', file_name))
        key = ';'.join([base_name, description.decode('utf-8')])
        self.descriptions.add(key)

def collect_available_test_cases():
    """Collect the available test cases."""
    explorer = TestDescriptions()
    explorer.walk_all()
    return sorted(explorer.descriptions)

class DescriptionChecker(TestDescriptionExplorer):
    """Check all test case descriptions.

* Check that each description is valid (length, allowed character set, etc.).
* Check that there is no duplicated description inside of one test suite.
"""

    def __init__(self, results):
        self.results = results

    def new_per_file_state(self):
        """Dictionary mapping descriptions to their line number."""
        return {}

    def process_test_case(self, per_file_state,
                          file_name, line_number, description):
        """Check test case descriptions for errors."""
        results = self.results
        seen = per_file_state
        if description in seen:
            results.error(file_name, line_number,
                          'Duplicate description (also line {})',
                          seen[description])
            return
        if re.search(br'[\t;]', description):
            results.error(file_name, line_number,
                          'Forbidden character \'{}\' in description',
                          re.search(br'[\t;]', description).group(0).decode('ascii'))
        if re.search(br'[^ -~]', description):
            results.error(file_name, line_number,
                          'Non-ASCII character in description')
        if len(description) > 66:
            results.warning(file_name, line_number,
                            'Test description too long ({} > 66)',
                            len(description))
        seen[description] = line_number

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--list-all',
                        action='store_true',
                        help='List all test cases, without doing checks')
    parser.add_argument('--quiet', '-q',
                        action='store_true',
                        help='Hide warnings')
    parser.add_argument('--verbose', '-v',
                        action='store_false', dest='quiet',
                        help='Show warnings (default: on; undoes --quiet)')
    options = parser.parse_args()
    if options.list_all:
        descriptions = collect_available_test_cases()
        sys.stdout.write('\n'.join(descriptions + ['']))
        return
    results = Results(options)
    checker = DescriptionChecker(results)
    try:
        checker.walk_all()
    except ScriptOutputError as e:
        results.error(e.script_name, e.idx,
                      '"{}" should be listed as "<suite_name>;<description>"',
                      e.line)
    if (results.warnings or results.errors) and not options.quiet:
        sys.stderr.write('{}: {} errors, {} warnings\n'
                         .format(sys.argv[0], results.errors, results.warnings))
    sys.exit(1 if results.errors else 0)

if __name__ == '__main__':
    main()
