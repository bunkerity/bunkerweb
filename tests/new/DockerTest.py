from Test import Test
from os.path import isdir, join, isfile
from os import chown, walk, getenv
from traceback import format_exc
from subprocess import run

class DockerTest(Test) :

	def __init__(self, name, timeout, tests) :
		super().__init__(name, "docker", timeout, tests)
        self.__domains = {
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
            for root, dirs, files in walk("/tmp/bw-data") :
                for name in dirs + files :
                    chown(join(root, name), 101, 101)
        except :
            self._log("exception while running DockerTest.init()\n" + format_exc(), error=True)
            return False
        return True

    def _setup_test(self) :
        try :
            super()._setup_test()
            test = "/tmp/tests/" + self._name
            compose = "/tmp/tests/" + self._name + "/docker-compose.yml"
            self._replace_in_file(compose, r"bunkerity/bunkerweb:.*$", "10.20.1.1:5000/bw-tests:latest")
            self._replace_in_file(compose, r"\./bw\-data:/", "/tmp/bw-data:/")
            self._replace_in_file(compose, r"\- bw_data:/", "/tmp/bw-data:/")
            for ex_domain, test_domain in self.__domains.items() :
                self._replace_in_files(test, ex_domain, test_domain)
                self._rename(test, ex_domain, test_domain)
            setup = test + "/setup-docker.sh"
            if isfile(setup) :
                run("./docker-setup.sh", cwd=test, shell=True, check=True)
            
        except :
            self._log("exception while running DockerTest._setup_test()\n" + format_exc(), error=True)
            return False
        return True
        

    def _cleanup_test(self) :
        pass