from re import escape
from yaml import safe_load, dump
from Test import Test
from os.path import isdir, isfile
from os import getenv
from traceback import format_exc
from subprocess import run
from logger import log


class DockerTest(Test):
    def __init__(self, name, timeout, tests, no_copy_container=False, delay=0, domains={}):
        super().__init__(
            name,
            "docker",
            timeout,
            tests,
            no_copy_container=no_copy_container,
            delay=delay,
        )
        self._domains = domains
        self._check_domains()

    @staticmethod
    def init():
        try:
            if not Test.init():
                return False
        except:
            log(
                "DOCKER",
                "❌",
                "exception while running DockerTest.init()\n" + format_exc(),
            )
            return False
        return True

    def _setup_test(self):
        try:
            super()._setup_test()
            test = "/tmp/tests/" + self._name
            compose = "/tmp/tests/" + self._name + "/docker-compose.yml"
            example_data = "/tmp/tests/" + self._name + "/bw-data"
            Test.replace_in_file(compose, r"bunkerity/bunkerweb:.*$", "local/bunkerweb-tests:latest")
            Test.replace_in_file(
                compose,
                r"bunkerity/bunkerweb-scheduler:.*$",
                "local/scheduler-tests:latest",
            )
            Test.replace_in_file(compose, r"\./bw\-data:/", "/tmp/bw-data:/")
            Test.replace_in_file(compose, r"\- bw_data:/", "- /tmp/bw-data:/")
            Test.replace_in_file(compose, r"\- bw\-data:/", "- /tmp/bw-data:/")
            with open(compose, "r") as f:
                data = safe_load(f.read())
            if data["services"]["bw-scheduler"]["environment"].get("AUTO_LETS_ENCRYPT", "no") == "yes":
                data["services"]["bw-scheduler"]["environment"]["USE_LETS_ENCRYPT_STAGING"] = "yes"
                data["services"]["bw-scheduler"]["environment"]["LETS_ENCRYPT_MAX_RETRIES"] = "3"
                data["services"]["bw-scheduler"]["environment"]["LETS_ENCRYPT_PROFILE"] = "shortlived"
            data["services"]["bw-scheduler"]["environment"]["CUSTOM_LOG_LEVEL"] = "debug"
            data["services"]["bw-scheduler"]["environment"]["LOG_LEVEL"] = "info"
            data["services"]["bw-scheduler"]["environment"]["USE_BUNKERNET"] = "no"
            data["services"]["bw-scheduler"]["environment"]["SEND_ANONYMOUS_REPORT"] = "no"
            data["services"]["bw-scheduler"]["environment"]["USE_DNSBL"] = "no"
            data["services"]["bw-scheduler"]["environment"]["DISABLE_DEFAULT_SERVER"] = "no"
            with open(compose, "w") as f:
                f.write(dump(data))
            for ex_domain, test_domain in self._domains.items():
                Test.replace_in_files(test, escape(ex_domain), test_domain)
                Test.rename(test, ex_domain, test_domain)
            Test.replace_in_files(test, escape("example.com"), getenv("ROOT_DOMAIN"))
            setup = test + "/setup-docker.sh"
            if isfile(setup):
                proc = run("sudo ./setup-docker.sh", cwd=test, shell=True)
                if proc.returncode != 0:
                    raise (Exception("setup-docker failed"))
            if isdir("/tmp/bw-data"):
                proc = run("sudo rm -rf /tmp/bw-data", shell=True)
                if proc.returncode != 0:
                    raise (Exception("rm bw-data failed"))
                proc = run("sudo mkdir /tmp/bw-data", shell=True)
                if proc.returncode != 0:
                    raise (Exception("mkdir bw-data failed"))
            if isdir(example_data) and not self._no_copy_container:
                proc = run(
                    f"sudo bash -c 'cp -rp {example_data}/* /tmp/bw-data'",
                    shell=True,
                )
                if proc.returncode != 0:
                    raise (Exception("cp bw-data failed"))
            proc = run("sudo chown -R root:101 /tmp/bw-data", shell=True)
            if proc.returncode != 0:
                raise (Exception("chown failed (docker stack)"))
            proc = run("sudo chmod -R 770 /tmp/bw-data", shell=True)
            if proc.returncode != 0:
                raise (Exception("chmod failed (docker stack)"))
            proc = run("docker compose pull --ignore-pull-failures", shell=True, cwd=test)
            if proc.returncode != 0:
                raise (Exception("docker compose pull failed"))
            proc = run("docker compose up -d", shell=True, cwd=test)
            if proc.returncode != 0:
                raise (Exception("docker compose up failed"))
        except:
            log(
                "DOCKER",
                "❌",
                "exception while running DockerTest._setup_test()\n" + format_exc(),
            )
            self._cleanup_test()
            return False
        return True

    def _cleanup_test(self):
        try:
            test = "/tmp/tests/" + self._name
            proc = run("docker compose down -v --remove-orphans", shell=True, cwd=test)
            if proc.returncode != 0:
                raise (Exception("docker compose down failed"))
            super()._cleanup_test()
        except:
            log(
                "DOCKER",
                "❌",
                "exception while running DockerTest._cleanup_test()\n" + format_exc(),
            )
            return False
        return True

    def _debug_fail(self):
        test = "/tmp/tests/" + self._name
        run("docker compose logs", shell=True, cwd=test)
