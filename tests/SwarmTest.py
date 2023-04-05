from Test import Test
from os.path import isdir, join, isfile
from os import chown, walk, getenv, listdir
from shutil import copytree, rmtree
from traceback import format_exc
from subprocess import run
from time import sleep
from logger import log

class SwarmTest(Test) :

    def __init__(self, name, timeout, tests, delay=0) :
        super().__init__(name, "swarm", timeout, tests, delay=delay)
        self._domains = {
            r"www\.example\.com": Test.random_string(6) + "." + getenv("TEST_DOMAIN1_1"),
            r"auth\.example\.com": Test.random_string(6) + "." + getenv("TEST_DOMAIN1_2"),
            r"app1\.example\.com": Test.random_string(6) + "." + getenv("TEST_DOMAIN1"),
            r"app2\.example\.com": Test.random_string(6) + "." + getenv("TEST_DOMAIN2"),
            r"app3\.example\.com": Test.random_string(6) + "." + getenv("TEST_DOMAIN3")
        }

    def init() :
        try :
            if not Test.init() :
                return False
            proc = run("sudo chown -R root:root /tmp/bw-data", shell=True)
            if proc.returncode != 0 :
                raise(Exception("chown failed (swarm stack)"))
            if isdir("/tmp/swarm") :
                rmtree("/tmp/swarm")
            copytree("./integrations/swarm", "/tmp/swarm")
            compose = "/tmp/swarm/stack.yml"
            Test.replace_in_file(compose, r"bunkerity/bunkerweb:.*$", "192.168.42.100:5000/bw-tests:latest")
            Test.replace_in_file(compose, r"bunkerity/bunkerweb-autoconf:.*$", "192.168.42.100:5000/bw-autoconf-tests:latest")
            Test.replace_in_file(compose, r"bw\-data:/", "/tmp/bw-data:/")
            proc = run("docker stack deploy -c stack.yml bunkerweb", cwd="/tmp/swarm", shell=True)
            if proc.returncode != 0 :
                raise(Exception("docker stack deploy failed (swarm stack)"))
            i = 0
            healthy = False
            while i < 90 :
                proc = run('docker stack ps --no-trunc --format "{{ .CurrentState }}" bunkerweb | grep -v "Running"', cwd="/tmp/swarm", shell=True, capture_output=True)
                if "" == proc.stdout.decode() :
                    healthy = True
                    break
                sleep(1)
                i += 1
            if not healthy :
                proc = run('docker service logs bunkerweb_mybunker ; docker service logs bunkerweb_myautoconf', cwd="/tmp/swarm", shell=True, capture_output=True)
                log("SWARM", "❌", "stdout logs = " + proc.stdout.decode())
                log("SWARM", "❌", "stderr logs = " + proc.stderr.decode())
                raise(Exception("swarm stack is not healthy"))
            sleep(60)
        except :
            log("SWARM", "❌", "exception while running SwarmTest.init()\n" + format_exc())
            return False
        return True

    def end() :
        ret = True
        try :
            if not Test.end() :
                return False
            proc = run("docker stack rm bunkerweb", shell=True)
            if proc.returncode != 0 :
                ret = False
            rmtree("/tmp/swarm")
        except :
            log("SWARM", "❌", "exception while running SwarmTest.end()\n" + format_exc())
            return False
        return ret

    def _setup_test(self) :
        try :
            super()._setup_test()
            test = "/tmp/tests/" + self._name
            compose = "/tmp/tests/" + self._name + "/swarm.yml"
            example_data = "./examples/" + self._name + "/bw-data"
            for ex_domain, test_domain in self._domains.items() :
                Test.replace_in_files(test, ex_domain, test_domain)
                Test.rename(test, ex_domain, test_domain)
            Test.replace_in_files(test, "example.com", getenv("ROOT_DOMAIN"))
            setup = test + "/setup-swarm.sh"
            if isfile(setup) :
                proc = run("sudo ./setup-swarm.sh", cwd=test, shell=True)
                if proc.returncode != 0 :
                    raise(Exception("setup-swarm failed"))
            # if isdir(example_data) :
                # for cp_dir in listdir(example_data) :
                    # if isdir(join(example_data, cp_dir)) :
                        # if isdir(join("/tmp/bw-data", cp_dir)) :
                            # run("sudo rm -rf " + join("/tmp/bw-data", cp_dir), shell=True)
                        # copytree(join(example_data, cp_dir), join("/tmp/bw-data", cp_dir))
            proc = run('docker stack deploy -c swarm.yml "' + self._name + '"', shell=True, cwd=test)
            if proc.returncode != 0 :
                raise(Exception("docker stack deploy failed"))
            i = 0
            healthy = False
            while i < self._timeout :
                proc = run('docker stack services --format "{{ .Name }}" ' + self._name, cwd="/tmp/swarm", shell=True, capture_output=True)
                if proc.returncode != 0 :
                    raise(Exception("swarm stack is not healthy (cmd1 failed)"))
                all_healthy = True
                for service in proc.stdout.decode().splitlines() :
                    proc2 = run('docker service ps --format "{{ .CurrentState }}" ' + service, cwd="/tmp/swarm", shell=True, capture_output=True)
                    if proc2.returncode != 0 :
                        raise(Exception("swarm stack is not healthy (cmd2 failed)"))
                    if not "Running" in proc2.stdout.decode() :
                        all_healthy = False
                        break
                if all_healthy :
                    healthy = True
                    break
                sleep(1)
                i += 1
            if not healthy :
                raise(Exception("swarm stack is not healthy"))
        except :
            log("SWARM", "❌", "exception while running SwarmTest._setup_test()\n" + format_exc())
            self._cleanup_test()
            return False
        return True

    def _cleanup_test(self) :
        try :
            proc = run('docker stack rm "' + self._name + '"', shell=True)
            if proc.returncode != 0 :
                raise(Exception("docker stack rm failed"))
            proc = run('docker config ls --format "{{ .ID }}"', shell=True, capture_output=True)
            if proc.returncode != 0 :
                raise(Exception("docker config ls failed"))
            for config in proc.stdout.decode().splitlines() :
                proc = run('docker config rm "' + config + '"', shell=True)
                if proc.returncode != 0 :
                    raise(Exception("docker config rm failed"))
            proc = run("docker service create --mode global --mount type=bind,src=/var/run/docker.sock,dst=/var/run/docker.sock --restart-condition none --name pruner -d docker docker volume prune -f", shell=True)
            if proc.returncode != 0 :
                raise(Exception("docker pruner create failed"))
            sleep(10)
            proc = run("docker service rm pruner", shell=True)
            if proc.returncode != 0 :
                raise(Exception("docker pruner rm failed"))
            super()._cleanup_test()
        except :
            log("SWARM", "❌", "exception while running SwarmTest._cleanup_test()\n" + format_exc())
            return False
        return True

    def _debug_fail(self) :
        run("docker service logs bunkerweb_mybunker", shell=True)
        run("docker service logs bunkerweb_myautoconf", shell=True)
        proc = run('docker stack services --format "{{ .Name }}" "' + self._name + '"', shell=True, capture_output=True)
        for service in proc.stdout.decode().splitlines() :
            run('docker service logs "' + service + '"', shell=True)
