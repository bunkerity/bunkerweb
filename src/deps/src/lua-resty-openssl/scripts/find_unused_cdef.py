#!/usr/bin/env python3

import os
import re
import sys

current_script_path = os.path.abspath(sys.argv[0])

def load_files(path):
    file_contents = {}
    for root, _, files in os.walk(path):
        for file in files:
            if file.endswith(".lua"):
                p = os.path.join(root.replace(path, ""), file).lstrip("/")
                with open(os.path.join(root, file)) as f:
                    file_contents[p] = f.readlines()

    return file_contents

token = "[a-zA-Z0-9_]"
def find_cdefs(files):
    cdefs = {
        "funcs": {},
        "types": {},
    }

    for path, lines in files.items():
        start = False
        for i in range(len(lines)):
            line = lines[i]
            if "ffi.cdef" in line:
                start = True
            elif "]]" in line and start:
                start = False
            
            if start:
                if re.findall("^\s*//", line): # comment
                    continue

                func = re.findall(f"{token}+[\s\*]+({token}+)\(", line)
                if func:
                    cdefs["funcs"][func[0]] = f"{path}:{i}"
                type_ = re.findall(f"typedef.*?({token}+);", line)
                if type_:
                    cdefs["types"][type_[0]] = f"{path}:{i}"
                type_ = re.findall(f"}}\s*({token}+);", line)
                if type_:
                    cdefs["types"][type_[0]] = f"{path}:{i}"

    return cdefs

# those are dynamically called
ignore_list = [
    "OSSL_PARAM_(?:set|get)_",
    "PEM_read_bio_",
    "fake_openssl_",
    "(?:d2i|i2d)_(?:PUBKEY|PrivateKey)_bio",
    "_(?:gettable|settable)_params",
    "_(?:get|set)_params",
    "_do_all_(?:sorted|provided)",
    "_get0_name",
]

def check_cdefs(files, cdef):
    unused = {
        "funcs": {},
        "types": {},
    }
    undefined = {
        "funcs": {},
        "types": {},
    }

    patterns = {
        "funcs": "C.%s[^a-zA-Z0-9_]",
        "types": "%s[^a-zA-Z0-9_]",
    }

    ignore_regex = "(?:%s)" % "|".join(ignore_list)

    for name, regex_pattern in patterns.items():
        for token, path in cdef[name].items():
            found = False
            for _, lines in files.items():
                full_content = "".join(lines)
                if re.findall(regex_pattern % token, full_content):
                    found = True
                    break
            if not found and not re.findall(ignore_regex, token):
                unused[name][token] = path
    
    # TODO: find undefined
    
    return unused, undefined

def display(unused, undefined):
    for name, tokens in unused.items():
        if len(tokens) == 0:
            continue

        print(f"Unused {name} ({len(tokens)}):")
        for token, path in tokens.items():
            print(f"  {token} on {path}")

    for name, tokens in undefined.items():
        if len(tokens) == 0:
            continue

        print(f"Undefined {name} ({len(tokens)}):")
        for token, path in tokens.items():
            print(f"  {token} on {path}")


if __name__ == '__main__':
    files = load_files(os.path.join(os.path.dirname(current_script_path), "..", "lib"))
    cdefs = find_cdefs(files)
    display(*check_cdefs(files, cdefs))