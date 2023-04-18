from abc import ABC, abstractmethod
from sys import stderr
from time import time, sleep
from requests import get
from traceback import format_exc
from shutil import copytree
from os.path import isdir, join
from os import mkdir, makedirs, walk, chmod, rename
from re import sub, search, MULTILINE
from datetime import datetime
from subprocess import run
from logger import log
from string import ascii_lowercase, digits
from random import choice


class Test(ABC):
    def __init__(self, name, kind, timeout, tests, no_copy_container=False, delay=0):
        self._name = name
        self.__kind = kind
        self._timeout = timeout
        self.__tests = tests
        self._no_copy_container = no_copy_container
        self.__delay = delay
        log(
            "TEST",
            "ℹ️",
            f"instiantiated with {len(tests)} tests and timeout of {timeout}s for {self._name}",
        )

    # Class method
    # called once before running all the different tests for a given integration
    def init():
        try:
            if not isdir("/tmp/bw-data"):
                mkdir("/tmp/bw-data")
            run("sudo chmod 777 /tmp/bw-data", shell=True)
            rm_dirs = ["configs", "plugins", "www"]
            for rm_dir in rm_dirs:
                if isdir(rm_dir):
                    run(f"sudo rm -rf /tmp/bw-data/{rm_dir}", shell=True)
            if not isdir("/tmp/tests"):
                mkdir("/tmp/tests")
        except:
            log("TEST", "❌", f"exception while running Test.init()\n{format_exc()}")
            return False
        return True

    # Class method
    # called once all tests ended
    def end():
        return True

    # helper to check domains
    def _check_domains(self):
        for k, v in self._domains.items():
            if v is None:
                log("TEST", "⚠️", f"env {k} is None")

    # called before starting the tests
    # must be override if specific actions needs to be done
    def _setup_test(self):
        try:
            rm_dirs = ["configs", "plugins", "www"]
            for rm_dir in rm_dirs:
                if isdir(f"/tmp/bw-data/{rm_dir}"):
                    run(
                        f"sudo bash -c 'rm -rf /tmp/bw-data/{rm_dir}/*'",
                        shell=True,
                    )
            if isdir(f"/tmp/tests/{self._name}"):
                run(f"sudo rm -rf /tmp/tests/{self._name}", shell=True)
            copytree(f"./examples/{self._name}/tmp/tests/{self._name}")
        except:
            log(
                "TEST",
                "❌",
                f"exception while running Test._setup_test()\n{format_exc()}",
            )
            return False
        return True

    # called after running the tests
    def _cleanup_test(self):
        try:
            run(f"sudo rm -rf /tmp/tests/{self._name}", shell=True)
        except:
            log(
                "TEST",
                "❌",
                f"exception while running Test._cleanup_test()\n{format_exc()}",
            )
            return False
        return True

    # run all the tests
    def run_tests(self):
        if not self._setup_test():
            self._debug_fail()
            return False
        if self.__delay != 0:
            log("TEST", "ℹ️", f"delay is set, sleeping {self.__delay}s")
            sleep(self.__delay)
        start = time()
        while time() < start + self._timeout:
            all_ok = True
            for test in self.__tests:
                ok = self.__run_test(test)
                sleep(1)
                if not ok:
                    all_ok = False
                    break
            if all_ok:
                elapsed = str(int(time() - start))
                log(
                    "TEST",
                    "ℹ️",
                    f"success ({elapsed}/{self._timeout}s)",
                )
                return self._cleanup_test()
            log("TEST", "⚠️", "tests not ok, retrying in 1s ...")
        self._debug_fail()
        self._cleanup_test()
        log("TEST", "❌", f"failed (timeout = {self._timeout}s)")
        return False

    # run a single test
    def __run_test(self, test):
        try:
            ex_url = test["url"]
            for ex_domain, test_domain in self._domains.items():
                if search(ex_domain, ex_url):
                    ex_url = sub(ex_domain, test_domain, ex_url)
                    break
            if test["type"] == "string":
                r = get(ex_url, timeout=10, verify=False)
                return test["string"].casefold() in r.text.casefold()
            elif test["type"] == "status":
                r = get(ex_url, timeout=10, verify=False)
                return test["status"] == r.status_code
        except:
            return False
        raise (Exception(f"unknown test type {test['type']}"))

    # called when tests fail : typical case is to show logs
    def _debug_fail(self):
        pass

    def replace_in_file(path, old, new):
        try:
            with open(path, "r") as f:
                content = f.read()
            content = sub(old, new, content, flags=MULTILINE)
            with open(path, "w") as f:
                f.write(content)
        except:
            log("TEST", "⚠️", f"can't replace file {path} : {format_exc()}")

    def replace_in_files(path, old, new):
        for root, dirs, files in walk(path):
            for name in files:
                Test.replace_in_file(join(root, name), old, new)

    def rename(path, old, new):
        for root, dirs, files in walk(path):
            for name in dirs + files:
                full_path = join(root, name)
                new_path = sub(old, new, full_path)
                if full_path != new_path:
                    rename(full_path, new_path)

    def random_string(length):
        charset = ascii_lowercase + digits
        return "".join(choice(charset) for i in range(length))
