#!/usr/bin/env python3

import sys
import glob
import msc_pyparser
import os.path
import re

class FileTransform(object):
    def __init__(self, data):
        self.data        = data
        self.cverpatt    = "ver\.\d+\.\d+\.\d+$"
        self.re_cverpatt = re.compile(self.cverpatt)

    def change_version(self, version, cversion):
        # iterate through AST items
        # self.data: the parsed structure
        for d in self.data:
            # id the item has 'actions' then we can check the 'ver' key
            if "actions" in d:
                aidx = 0
                while aidx < len(d['actions']):
                    a = d['actions'][aidx]
                    # if we found one, replace the value
                    if a['act_name'] == "ver":
                        a['act_arg'] = version
                    aidx += 1
            else:
                # replace SecComponentSignature by same version string
                if d['type'].lower() == "seccomponentsignature":
                    d['arguments'][0]['argument'] = version

                # replace the versions in comments if cversion exists
                if cversion is not None:
                    if d['type'].lower() == "comment" and self.re_cverpatt.search(d['argument']):
                        d['argument'] = re.sub(self.cverpatt, "ver.%s" % (cversion), d['argument'])

class FileHandler(object):
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
        if not hasattr(self, 'cversion'):
            self.cversion = None

        self.output = self.output.rstrip("/") + "/"

        # iterate through the list of files
        for f in glob.glob(self.input):
            print(f"Working with file: %s" % (f))
            # read the file content
            try:
                with open(f) as file:
                    data = file.read()
            except:
                print("Exception caught - ", sys.exc_info())
                sys.exit(1)

            # build AST from content
            try:
                mparser = msc_pyparser.MSCParser()
                mparser.parser.parse(data)
            except:
                print(sys.exc_info()[1])
                sys.exit(1)

            # change version and comment version if exists
            try:
                t = FileTransform(mparser.configlines)
                t.change_version(self.version, self.cversion)
            except:
                print(sys.exc_info()[1])
                sys.exit(1)

            # save the new file
            try:
                mwriter = msc_pyparser.MSCWriter(mparser.configlines)
                output = os.path.join(self.output, os.path.basename(f).lstrip("/"))
                with open(output, "w") as file:
                    mwriter.generate()
                    # add extra new line at the end of file
                    mwriter.output.append("")
                    file.write("\n".join(mwriter.output))
            except:
                print("Exception caught - ", sys.exc_info())
                sys.exit(1)

if len(sys.argv) < 4:
    print("Argument missing!")
    print("Use: %s rule.conf /path/to/output/directory version" % sys.argv[0])
    print("     %s \"/path/to/rules/*.conf\" /path/to/output/directory version [comment_version]" % sys.argv[0])
    print("Example:")
    print("     mkdir ../../rulestmp")
    print("     %s \"../../rules/*.conf\" ../../rulestmp \"OWASP_CRS/3.4.0-dev\" \"3.4.0-dev\"" % sys.argv[0])
    sys.exit(1)

args = {
    'input'   : sys.argv[1],
    'output'  : sys.argv[2],
    'version' : sys.argv[3]
}

if len(sys.argv) > 4:
    args['cversion'] = sys.argv[4]

fh = FileHandler(**args)
