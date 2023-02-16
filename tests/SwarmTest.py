from Test import Test
from os.path import isdir, isfile
from os import getenv
from shutil import copytree, rmtree
from traceback import format_exc
from subprocess import run
from time import sleep
from logger import setup_logger


class SwarmTest(Test):
    def __init__(self, name, timeout, tests, delay=0):
        super().__init__(name, "swarm", timeout, tests, delay=delay)
        self._domains = {
            r"www\.example\.com": getenv("TEST_DOMAIN1_1"),
            r"auth\.example\.com": getenv("TEST_DOMAIN1_2"),
            r"app1\.example\.com": getenv("TEST_DOMAIN1"),
            r"app2\.example\.com": getenv("TEST_DOMAIN2"),
            r"app3\.example\.com": getenv("TEST_DOMAIN3"),
        }
        self.__logger = setup_logger("Swarm_test", getenv("LOGLEVEL", "INFO"))

    @staticmethod
    def init():
        try:
            if not Test.init():
                return False
            proc = run("sudo chown -R root:root /tmp/bw-data", shell=True)
            if proc.returncode != 0:
                raise (Exception("chown failed (swarm stack)"))
            if isdir("/tmp/swarm"):
                rmtree("/tmp/swarm")
            copytree("./integrations/swarm", "/tmp/swarm")
            compose = "/tmp/swarm/stack.yml"
            Test.replace_in_file(
                compose,
                r"bunkerity/bunkerweb:.*$",
                "192.168.42.100:5000/bw-tests:latest",
            )
            Test.replace_in_file(
                compose,
                r"bunkerity/bunkerweb-autoconf:.*$",
                "192.168.42.100:5000/bw-autoconf-tests:latest",
            )
            Test.replace_in_file(compose, r"bw\-data:/", "/tmp/bw-data:/")
            proc = run(
                "docker stack deploy -c stack.yml bunkerweb",
                cwd="/tmp/swarm",
                shell=True,
            )
            if proc.returncode != 0:
                raise (Exception("docker stack deploy failed (swarm stack)"))
            i = 0
            healthy = False
            while i < 90:
                proc = run(
                    'docker stack ps --no-trunc --format "{{ .CurrentState }}" bunkerweb | grep -v "Running"',
                    cwd="/tmp/swarm",
                    shell=True,
                    capture_output=True,
                )
                if not proc.stdout.decode():
                    healthy = True
                    break
                sleep(1)
                i += 1
            if not healthy:
                proc = run(
                    "docker service logs bunkerweb_mybunker ; docker service logs bunkerweb_myautoconf",
                    cwd="/tmp/swarm",
                    shell=True,
                    capture_output=True,
                )
                logger = setup_logger("Swarm_test", getenv("LOGLEVEL", "INFO"))
                logger.error(f"stdout logs = {proc.stdout.decode()}")
                logger.error(f"stderr logs = {proc.stderr.decode()}")
                raise (Exception("swarm stack is not healthy"))
            sleep(60)
        except:
            setup_logger("Swarm_test", getenv("LOGLEVEL", "INFO")).error(
                f"exception while running SwarmTest.init()\n{format_exc()}",
            )
            return False
        return True

    @staticmethod
    def end():
        ret = True
        try:
            if not Test.end():
                return False
            proc = run("docker stack rm bunkerweb", shell=True)
            if proc.returncode != 0:
                ret = False
            rmtree("/tmp/swarm")
        except:
            setup_logger("Swarm_test", getenv("LOGLEVEL", "INFO")).error(
                f"exception while running SwarmTest.end()\n{format_exc()}"
            )
            return False
        return ret

    def _setup_test(self):
        try:
            super()._setup_test()
            test = f"/tmp/tests/{self._name}"
            for ex_domain, test_domain in self._domains.items():
                Test.replace_in_files(test, ex_domain, test_domain)
                Test.rename(test, ex_domain, test_domain)
            Test.replace_in_files(test, "example.com", getenv("ROOT_DOMAIN"))
            setup = f"{test}/setup-swarm.sh"
            if isfile(setup):
                proc = run("sudo ./setup-swarm.sh", cwd=test, shell=True)
                if proc.returncode != 0:
                    raise (Exception("setup-swarm failed"))
            proc = run(
                f'docker stack deploy -c swarm.yml "{self._name}"',
                shell=True,
                cwd=test,
            )
            if proc.returncode != 0:
                raise (Exception("docker stack deploy failed"))
            i = 0
            healthy = False
            while i < self._timeout:
                proc = run(
                    'docker stack services --format "{{ .Name }}" ' + self._name,
                    cwd="/tmp/swarm",
                    shell=True,
                    capture_output=True,
                )
                if proc.returncode != 0:
                    raise (Exception("swarm stack is not healthy (cmd1 failed)"))
                all_healthy = True
                for service in proc.stdout.decode().splitlines():
                    proc2 = run(
                        'docker service ps --format "{{ .CurrentState }}" ' + service,
                        cwd="/tmp/swarm",
                        shell=True,
                        capture_output=True,
                    )
                    if proc2.returncode != 0:
                        raise (Exception("swarm stack is not healthy (cmd2 failed)"))
                    if not "Running" in proc2.stdout.decode():
                        all_healthy = False
                        break
                if all_healthy:
                    healthy = True
                    break
                sleep(1)
                i += 1
            if not healthy:
                raise (Exception("swarm stack is not healthy"))
        except:
            self.__logger.error(
                f"exception while running SwarmTest._setup_test()\n{format_exc()}",
            )
            self._cleanup_test()
            return False
        return True

    def _cleanup_test(self):
        try:
            proc = run(f'docker stack rm "{self._name}"', shell=True)
            if proc.returncode != 0:
                raise (Exception("docker stack rm failed"))
            proc = run(
                'docker config ls --format "{{ .ID }}"', shell=True, capture_output=True
            )
            if proc.returncode != 0:
                raise (Exception("docker config ls failed"))
            for config in proc.stdout.decode().splitlines():
                proc = run(f'docker config rm "{config}"', shell=True)
                if proc.returncode != 0:
                    raise (Exception("docker config rm failed"))
            proc = run(
                "docker service create --mode global --mount type=bind,src=/var/run/docker.sock,dst=/var/run/docker.sock --restart-condition none --name pruner -d docker docker volume prune -f",
                shell=True,
            )
            if proc.returncode != 0:
                raise (Exception("docker pruner create failed"))
            sleep(10)
            proc = run("docker service rm pruner", shell=True)
            if proc.returncode != 0:
                raise (Exception("docker pruner rm failed"))
            super()._cleanup_test()
        except:
            self.__logger.error(
                f"exception while running SwarmTest._cleanup_test()\n{format_exc()}",
            )
            return False
        return True

    def _debug_fail(self):
        run("docker service logs bunkerweb_mybunker", shell=True)
        run("docker service logs bunkerweb_myautoconf", shell=True)
        proc = run(
            'docker stack services --format "{{ .Name }}" "' + self._name + '"',
            shell=True,
            capture_output=True,
        )
        for service in proc.stdout.decode().splitlines():
            run(f'docker service logs "{service}"', shell=True)
