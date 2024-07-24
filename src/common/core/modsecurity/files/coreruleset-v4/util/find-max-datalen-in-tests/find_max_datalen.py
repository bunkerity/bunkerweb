#!/usr/bin/env python3

# This file helps to find the longest data size in all test cases under
# CORERULESET_ROOT/test/regression/tests directory.

# You just have to pass the CORERULESET_ROOT as argument.
# Optional argument can be passed -i or --ignoretests - the listed test
# cases will skipped.

# At the end, the script will print the longest length, and the rule where
# the data is.


import sys
import os
import os.path
import yaml
import argparse

if __name__ == "__main__":

    desc = """This script needs a mandatory argument where you pass the path to your
coreruleset. Then it iterates through tests, and finds the longest request
body (data) between test cases. To ignore a test case, pass the number of the
test with '-i' or '--ignoretests', eg.: '... -i 920410-1'"""

    parser = argparse.ArgumentParser(description=desc, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-i', '--ignoretests', metavar='ignoretests',
                        help='Ignore listed rules, separated by comma', required=False,
                        nargs=1)
    parser.add_argument('crspath', metavar='/path/to/coreruleset', type=str,
                        help='Directory path to CRS')
    args = parser.parse_args()

    test_cases = {}
    testpath = args.crspath.rstrip("/") + "/tests/regression/tests"

    if not os.path.isdir(testpath):
        print("Directory does not exist: %s" % (testpath))
        sys.exit(1)

    ignoretests = []
    if args.ignoretests is not None:
        ignoretests = args.ignoretests[0].split(",")

    try:
        max_len = 0
        max_title = ""
        for root, dirs, files in os.walk(testpath):
            path = root.split(os.sep)
            for file in files:
                if file.endswith(".yaml"):
                    with open(os.path.join(root, file)) as f:
                        test = yaml.full_load(f)
                        for t in test['tests']:
                            title = t['test_title']
                            for s in t['stages']:
                                if 'stage' in s:
                                    if 'input' in s['stage']:
                                        if 'data' in s['stage']['input']:
                                            if len(s['stage']['input']['data']) > max_len \
                                                and title not in ignoretests:
                                                max_len = len(s['stage']['input']['data'])
                                                max_title = title
        print("Longest data: %d in test %s" % (max_len, max_title))
    except:
        print("Can't open files in given path!")
        print(sys.exc_info())
        sys.exit(1)
