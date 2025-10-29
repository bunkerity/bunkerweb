from abc import ABC
from time import time, sleep
from requests import get
from traceback import format_exc
from shutil import copytree
from os.path import isdir, join
from os import mkdir, walk, rename
from re import compile as re_compile, escape, sub, search, MULTILINE
from subprocess import run
from logger import log
from string import ascii_lowercase, digits
from random import choice
from ssl import create_default_context, create_connection
import OpenSSL.crypto as crypto
from urllib.parse import urlparse


class Test(ABC):
    def __init__(self, name, kind, timeout, tests, no_copy_container=False, delay=0):
        self._name = name
        self.__kind = kind
        self._timeout = timeout
        self.__tests = tests
        self._no_copy_container = no_copy_container
        self.__delay = delay
        self._domains = {}
        log(
            "TEST",
            "ℹ️",
            f"instiantiated with {len(tests)} tests and timeout of {timeout}s for {self._name}",
        )

    # called once before running all the different tests for a given integration
    @staticmethod
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
    @staticmethod
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
            copytree(f"./examples/{self._name}", f"/tmp/tests/{self._name}")
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
            ok = False
            ex_url = test["url"]
            for ex_domain, test_domain in self._domains.items():
                escaped_domain = escape(ex_domain)
                if search(escaped_domain, ex_url):
                    ex_url = sub(escaped_domain, test_domain, ex_url)
                    break
            if test["type"] == "string":
                r = get(ex_url, timeout=10, verify=False)
                ok = test["string"].casefold() in r.text.casefold()
                if not ok:
                    log("TEST", "⚠️", f"String not found : {test['string'].casefold()}")
            elif test["type"] == "status":
                r = get(ex_url, timeout=10, verify=False)
                ok = test["status"] == r.status_code
                if not ok:
                    log("TEST", "⚠️", f"Wrong status code : {str(r.status_code)}")

            if not ok:
                return False

            if "tls" in test:
                ex_tls = test["tls"]
                tls_edit = test.get("tls_edit", True)
                if tls_edit:
                    for ex_domain, test_domain in self._domains.items():
                        escaped_domain = escape(ex_domain)
                        if search(escaped_domain, ex_tls):
                            ex_tls = sub(escaped_domain, test_domain, ex_tls)
                            break

                parsed_url = urlparse(ex_url)
                hostname = parsed_url.netloc
                port = 443
                if ":" in hostname:
                    hostname, port = hostname.rsplit(":", 1)
                    port = int(port)

                connection = create_connection((hostname, port))
                context = create_default_context()
                context.check_hostname = False
                context.verify_mode = False
                sock = context.wrap_socket(connection, server_hostname=hostname)
                cert = sock.getpeercert(True)
                sock.close()
                x509 = crypto.load_certificate(crypto.FILETYPE_ASN1, cert)
                cert_cn = x509.get_subject().CN
                if cert_cn != ex_tls:
                    log("TEST", "⚠️", f"wrong cert CN : {cert_cn} != {ex_tls}")
                    return False

            return True
        except:
            log("TEST", "⚠️", f"Exception : {format_exc()}")
            return False
        raise (Exception(f"unknown test type {test['type']}"))

    # called when tests fail : typical case is to show logs
    def _debug_fail(self):
        pass

    @staticmethod
    def replace_in_file(path, old, new):
        try:
            with open(path, "r") as f:
                content = f.read()
            pattern = re_compile(old, flags=MULTILINE)
            content = pattern.sub(new, content)
            with open(path, "w") as f:
                f.write(content)
        except BaseException:
            log("TEST", "⚠️", f"can't replace file {path} : {format_exc()}")

    @staticmethod
    def replace_in_files(path, old, new):
        for root, dirs, files in walk(path):
            for name in files:
                Test.replace_in_file(join(root, name), old, new)

    @staticmethod
    def rename(path, old, new):
        for root, dirs, files in walk(path):
            for name in dirs + files:
                full_path = join(root, name)
                new_path = sub(old, new, full_path)
                if full_path != new_path:
                    rename(full_path, new_path)

    @staticmethod
    def random_string(length):
        charset = ascii_lowercase + digits
        return "".join(choice(charset) for _ in range(length))
