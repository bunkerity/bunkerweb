from Test import Test
from os.path import isdir, join, isfile
from os import chown, walk, getenv, listdir
from shutil import copytree
from traceback import format_exc
from subprocess import run
from logger import log

class DockerTest(Test) :

    def __init__(self, name, timeout, tests) :
        super().__init__(name, "docker", timeout, tests)
        self._domains = {
            r"www\.example\.com": getenv("TEST_DOMAIN1"),
            r"auth\.example\.com": getenv("TEST_DOMAIN1"),
            r"app1\.example\.com": getenv("TEST_DOMAIN1_1"),
            r"app2\.example\.com": getenv("TEST_DOMAIN1_2"),
            r"app3\.example\.com": getenv("TEST_DOMAIN1_3")
        }

    def init() :
        try :
            if not Test.init() :
                return False
            proc = run("sudo chown -R 101:101 /tmp/bw-data", shell=True)
            if proc.returncode != 0 :
                raise(Exception("chown failed (autoconf stack)"))
        except :
            log("DOCKER", "❌", "exception while running DockerTest.init()\n" + format_exc())
            return False
        return True

    def _setup_test(self) :
        try :
            super()._setup_test()
            test = "/tmp/tests/" + self._name
            compose = "/tmp/tests/" + self._name + "/docker-compose.yml"
            example_data = "./examples/" + self._name + "/bw-data"
            self._replace_in_file(compose, r"bunkerity/bunkerweb:.*$", "10.20.1.1:5000/bw-tests:latest")
            self._replace_in_file(compose, r"\./bw\-data:/", "/tmp/bw-data:/")
            self._replace_in_file(compose, r"\- bw_data:/", "- /tmp/bw-data:/")
            for ex_domain, test_domain in self._domains.items() :
                self._replace_in_files(test, ex_domain, test_domain)
                self._rename(test, ex_domain, test_domain)
            setup = test + "/setup-docker.sh"
            if isfile(setup) :
                proc = run("sudo ./setup-docker.sh", cwd=test, shell=True)
                if proc.returncode != 0 :
                    raise(Exception("setup-docker failed"))
            if isdir(example_data) :
                for cp_dir in listdir(example_data) :
                    if isdir(join(example_data, cp_dir)) :
                        copytree(join(example_data, cp_dir), join("/tmp/bw-data", cp_dir))
            proc = run("docker-compose pull", shell=True, cwd=test)
            if proc.returncode != 0 :
                raise(Exception("docker-compose pull failed"))
            proc = run("docker-compose up -d", shell=True, cwd=test)
            if proc.returncode != 0 :
                raise(Exception("docker-compose up failed"))
        except :
            log("DOCKER", "❌", "exception while running DockerTest._setup_test()\n" + format_exc())
            self._cleanup_test()
            return False
        self._cleanup_test()
        return True

    def _cleanup_test(self) :
        try :
            test = "/tmp/tests/" + self._name
            proc = run("docker-compose down -v", shell=True, cwd=test)
            if proc.returncode != 0 :
                raise(Exception("docker-compose down failed"))
            super()._cleanup_test()
        except :
            log("DOCKER", "❌", "exception while running DockerTest._cleanup_test()\n" + format_exc())
            return False
        return True
        