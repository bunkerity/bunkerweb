from Test import Test
from os.path import isdir, isfile
from os import getenv, mkdir
from shutil import rmtree, copy
from traceback import format_exc
from subprocess import run
from time import sleep
from logger import log
from yaml import safe_load, dump


class SwarmTest(Test):
    def __init__(self, name, timeout, tests, delay=0):
        super().__init__(name, "swarm", timeout, tests, delay=delay)
        self._domains = {
            r"www\.example\.com": f"{Test.random_string(6)}.{getenv('TEST_DOMAIN1_1')}",
            r"auth\.example\.com": f"{Test.random_string(6)}.{getenv('TEST_DOMAIN1_2')}",
            r"app1\.example\.com": f"{Test.random_string(6)}.{getenv('TEST_DOMAIN1_1')}",
            r"app2\.example\.com": f"{Test.random_string(6)}.{getenv('TEST_DOMAIN1_2')}",
            r"app3\.example\.com": f"{Test.random_string(6)}.{getenv('TEST_DOMAIN1_3')}",
        }

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
            mkdir("/tmp/swarm")
            copy("./misc/integrations/swarm.mariadb.yml", "/tmp/swarm/stack.yml")
            compose = "/tmp/swarm/stack.yml"
            with open(compose, "r") as f:
                data = safe_load(f.read())
            if (
                not "AUTO_LETS_ENCRYPT=yes"
                in data["services"]["bunkerweb"]["environment"]
            ):
                data["services"]["bunkerweb"]["environment"].append(
                    "AUTO_LETS_ENCRYPT=yes"
                )
            data["services"]["bunkerweb"]["environment"].append(
                "USE_LETS_ENCRYPT_STAGING=yes"
            )
            del data["services"]["bunkerweb"]["deploy"]["placement"]
            with open(compose, "w") as f:
                f.write(dump(data))
            Test.replace_in_file(
                compose,
                r"bunkerity/bunkerweb:.*$",
                "192.168.42.100:5000/bunkerweb-tests:latest",
            )
            Test.replace_in_file(
                compose,
                r"bunkerity/bunkerweb-autoconf:.*$",
                "192.168.42.100:5000/autoconf-tests:latest",
            )
            Test.replace_in_file(
                compose,
                r"bunkerity/bunkerweb-scheduler:.*$",
                "192.168.42.100:5000/scheduler-tests:latest",
            )
            # Test.replace_in_file(compose, r"bw\-data:/", "/tmp/bw-data:/")
            proc = run(
                "docker stack deploy -c stack.yml bunkerweb",
                cwd="/tmp/swarm",
                shell=True,
            )
            if proc.returncode != 0:
                raise (Exception("docker stack deploy failed (swarm stack)"))
            i = 0
            healthy = False
            while i < 120:
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
                    "docker service logs bunkerweb_bunkerweb ; docker service logs bunkerweb_bw-autoconf ; docker service logs bunkerweb_bw-scheduler ; docker service logs bunkerweb_bw-db ; docker service logs bunkerweb_bw-redis ; docker stack ps --no-trunc bunkerweb",
                    cwd="/tmp/swarm",
                    shell=True,
                    capture_output=True,
                )
                log("SWARM", "❌", f"stdout logs = {proc.stdout.decode()}")
                log("SWARM", "❌", f"stderr logs = {proc.stderr.decode()}")
                raise (Exception("swarm stack is not healthy"))
            sleep(60)
        except:
            log(
                "SWARM",
                "❌",
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
            log(
                "SWARM", "❌", f"exception while running SwarmTest.end()\n{format_exc()}"
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
            log(
                "SWARM",
                "❌",
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
            log(
                "SWARM",
                "❌",
                f"exception while running SwarmTest._cleanup_test()\n{format_exc()}",
            )
            return False
        return True

    def _debug_fail(self):
        run("docker service logs bunkerweb_bunkerweb", shell=True)
        run("docker service logs bunkerweb_bw-autoconf", shell=True)
        run("docker service logs bunkerweb_bw-scheduler", shell=True)
        proc = run(
            'docker stack services --format "{{ .Name }}" "' + self._name + '"',
            shell=True,
            capture_output=True,
        )
        for service in proc.stdout.decode().splitlines():
            run(f'docker service logs "{service}"', shell=True)
