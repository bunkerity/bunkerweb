from Test import Test
from os.path import isdir, isfile
from os import environ, getenv
from traceback import format_exc
from subprocess import run
from logger import setup_logger


class DockerTest(Test):
    def __init__(self, name, timeout, tests, no_copy_container=False, delay=0):
        super().__init__(
            name,
            "docker",
            timeout,
            tests,
            no_copy_container=no_copy_container,
            delay=delay,
        )
        self._domains = {
            r"www\.example\.com": getenv("TEST_DOMAIN1"),
            r"auth\.example\.com": getenv("TEST_DOMAIN1"),
            r"app1\.example\.com": getenv("TEST_DOMAIN1_1"),
            r"app2\.example\.com": getenv("TEST_DOMAIN1_2"),
            r"app3\.example\.com": getenv("TEST_DOMAIN1_3"),
        }
        self.__logger = setup_logger("Docker_test", environ.get("LOGLEVEL", "INFO"))

    @staticmethod
    def init():
        try:
            if not Test.init():
                return False
            proc = run("sudo chown -R 101:101 /tmp/bw-data", shell=True)
            if proc.returncode != 0:
                raise (Exception("chown failed (autoconf stack)"))
        except:
            setup_logger("Docker_test", environ.get("LOG_LEVEL", "INFO")).error(
                f"exception while running DockerTest.init()\n{format_exc()}",
            )
            return False
        return True

    def _setup_test(self):
        try:
            super()._setup_test()
            test = f"/tmp/tests/{self._name}"
            compose = f"/tmp/tests/{self._name}/docker-compose.yml"
            example_data = f"/tmp/tests/{self._name}/bw-data"
            Test.replace_in_file(
                compose, r"bunkerity/bunkerweb:.*$", "10.20.1.1:5000/bw-tests:latest"
            )
            Test.replace_in_file(compose, r"\./bw\-data:/", "/tmp/bw-data:/")
            Test.replace_in_file(compose, r"\- bw_data:/", "- /tmp/bw-data:/")
            for ex_domain, test_domain in self._domains.items():
                Test.replace_in_files(test, ex_domain, test_domain)
                Test.rename(test, ex_domain, test_domain)
            Test.replace_in_files(test, "example.com", getenv("ROOT_DOMAIN"))
            setup = f"{test}/setup-docker.sh"
            if isfile(setup):
                proc = run("sudo ./setup-docker.sh", cwd=test, shell=True)
                if proc.returncode != 0:
                    raise (Exception("setup-docker failed"))
            if isdir(example_data) and not self._no_copy_container:
                proc = run(
                    f"sudo bash -c 'cp -rp {example_data}/* /tmp/bw-data'",
                    shell=True,
                )
                if proc.returncode != 0:
                    raise (Exception("cp bw-data failed"))
            proc = run("docker-compose pull", shell=True, cwd=test)
            if proc.returncode != 0:
                raise (Exception("docker-compose pull failed"))
            proc = run("docker-compose up -d", shell=True, cwd=test)
            if proc.returncode != 0:
                raise (Exception("docker-compose up failed"))
        except:
            self.__logger.error(
                f"exception while running DockerTest._setup_test()\n{format_exc()}",
            )
            self._cleanup_test()
            return False
        return True

    def _cleanup_test(self):
        try:
            test = "/tmp/tests/" + self._name
            proc = run("docker-compose down -v", shell=True, cwd=test)
            if proc.returncode != 0:
                raise (Exception("docker-compose down failed"))
            super()._cleanup_test()
        except:
            self.__logger.error(
                f"exception while running DockerTest._cleanup_test()\n{format_exc()}",
            )
            return False
        return True

    def _debug_fail(self):
        test = f"/tmp/tests/{self._name}"
        run("docker-compose logs", shell=True, cwd=test)
