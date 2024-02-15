#!/usr/bin/env python3

# This file helps to find the rules which does not have any test cases.
#
# You just have to pass the CORERULESET_ROOT as argument.
#
# At the end, the script will print the list of rules without any tests.
#
# Please note, that there are some exclusions:
# * only REQUEST-NNN rules are checked
# * there are some hardcoded exlucions:
#   * REQUEST-900-
#   * REQUEST-901-
#   * REQUEST-905-
#   * REQUEST-910-
#   * REQUEST-912.
#   * REQUEST-949-
#
#   and the rule 921170

import sys
import glob
import msc_pyparser
import argparse

EXCLUSION_LIST = ["900", "901", "905", "910", "912", "949", "921170", "942441", "942442"]
oformat = "native"

def find_ids(s, test_cases):
    """
        s: the parsed structure
        test_cases: all available test cases
    """
    rids = {}
    for i in s:
        # only SecRule counts
        if i['type'] == "SecRule":
            for a in i['actions']:
                # find the `id` action
                if a['act_name'] == "id":
                    # get the argument of the action
                    rid = int(a['act_arg']) # int
                    srid = a['act_arg']     # string
                    if (rid%1000) >= 100:   # skip the PL control rules
                        # also skip these hardcoded rules
                        need_check = True
                        for excl in EXCLUSION_LIST:
                            if srid[:len(excl)] == excl:
                                need_check = False
                        if need_check:
                            # if there is no test cases, just print it
                            if rid not in test_cases:
                                rids[rid] = a['lineno']
    return rids

def errmsgf(msg):
    if oformat == "github":
        print("::error file={file},line={line},endLine={endLine},title={title}::{message}".format(**msg))
    else:
        print("file={file}, line={line}, endLine={endLine}, title={title}: {message}".format(**msg))

if __name__ == "__main__":

    desc = """This script helps to find the rules without test cases. It needs a mandatory
argument where you pass the path to your coreruleset. The tool collects the
tests with name REQUEST-*, but not with RESPONSE-*. Then reads the rule id's,
and check which rule does not have any test. Some rules does not need test
case, these are hardcoded as exclusions: 900NNN, 901NNN, 905NNN, 910NNN,
912NNN, 949NNN."""

    parser = argparse.ArgumentParser(description=desc, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--output", dest="output", help="Output format native[default]|github", required=False)
    parser.add_argument('crspath', metavar='/path/to/coreruleset', type=str,
                        help='Directory path to CRS')
    args = parser.parse_args()

    if args.output is not None:
        if args.output not in ["native", "github"]:
            print("--output can be one of the 'native' or 'github'. Default value is 'native'")
            sys.exit(1)
    oformat = args.output

    test_cases = {}
    # from argument, build the rules path and regression test paths
    crspath = args.crspath.rstrip("/") + "/rules/*.conf"
    testpath = args.crspath.rstrip("/") + "/tests/regression/tests/*"
    retval = 0
    # collect rules
    flist = glob.glob(crspath)
    flist.sort()
    if len(flist) == 0:
        print("Can't open files in given path!")
        sys.exit(1)

    # collect test cases
    tlist = glob.glob(testpath)
    tlist.sort()
    if len(tlist) == 0:
        print("Can't open files in given path (%s)!" % (testpath))
        sys.exit(1)
    # find the yaml files with name REQUEST at the begin
    # collect them in a dictionary
    for t in tlist:
        tname = t.split("/")[-1]
        if tname[:7] == "REQUEST":
            testlist = glob.glob(t + "/*.yaml")
            testlist.sort()
            for tc in testlist:
                tcname = tc.split("/")[-1].split(".")[0]
                test_cases[int(tcname)] = 1

    # iterate the rule files
    for f in flist:
        fname = f.split("/")[-1]
        if fname[:7] == "REQUEST":
            try:
                with open(f, 'r') as inputfile:
                    data = inputfile.read()
            except:
                print("Can't open file: %s" % f)
                print(sys.exc_info())
                sys.exit(1)

            try:
                # make a structure
                mparser = msc_pyparser.MSCParser()
                mparser.parser.parse(data)
                # add the parsed structure to a function, which finds the 'id'-s,
                # and the collected test cases
                rids = find_ids(mparser.configlines, test_cases)
                for k in rids.keys():
                    errmsgf({'file': f, 'line': rids[k], 'endLine': rids[k], 'title': "Test file missing", 'message': ("rule %d does not have any regression test" % k)})
            except:
                print("Can't parse config file: %s" % (f))
                print(sys.exc_info()[1])
                sys.exit(1)
    sys.exit(retval)
