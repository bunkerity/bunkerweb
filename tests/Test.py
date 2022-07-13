from abc import ABC, abstractmethod
from sys import stderr
from time import time, sleep
from requests import get
from traceback import format_exc
from shutil import copytree
from os.path import isdir, join
from os import mkdir, makedirs, walk, chmod
from re import sub, match, MULTILINE
from datetime import datetime
from subprocess import run

class Test(ABC) :

    def __init__(self, name, kind, timeout, tests) :
        self._name = name
        self.__kind = kind
        self.__timeout = timeout
        self.__tests = tests
        self._log("instiantiated with " + str(len(tests)) + " tests and timeout of " + str(timeout) + "s")

    def _log(self, msg, error=False) :
        when = datetime.today().strftime("[%Y-%m-%d %H:%M:%S]")
        what = self._name + " - " + self.__kind + " - " + msg
        if error :
            print(when + " " + what, flush=True, file=stderr)
        else :
            print(when + " " + what, flush=True)

    # Class method
    # called once before running all the different tests for a given integration
    def init() :
        try :
            if not isdir("/tmp/bw-data") :
                mkdir("/tmp/bw-data")
            chmod("/tmp/bw-data", 0o777)
            rm_dirs = ["configs", "plugins", "www"]
            for rm_dir in rm_dirs :
                if isdir(rm_dir) :
                    run("sudo rm -rf /tmp/bw-data/" + rm_dir, shell=True)
            if not isdir("/tmp/tests") :
                mkdir("/tmp/tests")
        except :
            print("exception while running Test.init()\n" + format_exc(), flush=True, file=stderr)
            return False
        return True

    # called before starting the tests
    # must be override if specific actions needs to be done
    def _setup_test(self) :
        try :
            rm_dirs = ["configs", "plugins", "www"]
            for rm_dir in rm_dirs :
                if isdir("/tmp/bw-data/" + rm_dir) :
                    run("sudo rm -rf /tmp/bw-data/" + rm_dir, shell=True)
            if isdir("/tmp/tests/" + self._name) :
                run("sudo rm -rf /tmp/tests/" + self._name, shell=True)
            copytree("./examples/" + self._name, "/tmp/tests/" + self._name)
        except :
            self._log("exception while running Test._setup_test()\n" + format_exc(), error=True)
            return False
        return True

    # called after running the tests
    def _cleanup_test(self) :
        try :
            rmtree("/tmp/tests/" + self._name)
        except :
            self._log("exception while running Test._cleanup_test()\n" + format_exc(), error=True)
            return False
        return True

    # run all the tests
    def run_tests(self) :
        if not self._setup_test() :
            return False
        start = time()
        while time() < start + self.__timeout :
            all_ok = True
            for test in self.__tests :
                ok = self.__run_test(test)
                if not ok :
                    all_ok = False
                    break
            if all_ok :
                elapsed = str(int(time() - start))
                self._log("success (" + elapsed + "/" + str(self.__timeout) + "s)")
                return self._cleanup_test()
            self._log("tests not ok, retrying in 1s ...", error=True)
            sleep(1)
        self._log("failed (timeout = " + str(self.__timeout) + "s)", error=True)
        self._cleanup_test()
        return False

    # run a single test
    def __run_test(self, test) :
        try :
            if test["type"] == "string" :
                ex_url = test["url"]
                for ex_domain, test_domain in self._domains.items() :
                    if match(ex_domain, ex_url) :
                        ex_url = sub(ex_domain, test_domain, ex_url)
                r = get(ex_url, timeout=5)
                return test["string"] in r.text
        except :
            self._log("exception while running test of type " + test["type"] + " on URL " + test["url"] + "\n" + format_exc(), error=True)
        raise(Exception("unknow test type " + test["type"]))

    def _replace_in_file(self, path, old, new) :
        with open(path, "r") as f :
            content = f.read()
        content = sub(old, new, content, flags=MULTILINE)
        with open(path, "w") as f :
            f.write(content)

    def _replace_in_files(self, path, old, new) :
        for root, dirs, files in walk(path) :
            for name in files :
                self._replace_in_file(join(root, name), old, new)

    def _rename(self, path, old, new) :
        for root, dirs, files in walk(path) :
            for name in dirs + files :
                full_path = join(root, name)
                if old in full_path :
                    new_path = sub(old, new, full_path)
                    if full_path != new_path :
                        rename(full_path, new_path)