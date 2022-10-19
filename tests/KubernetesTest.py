from Test import Test
from os.path import isdir, isfile
from os import getenv
from shutil import copytree, rmtree, copy
from traceback import format_exc
from subprocess import run
from time import sleep
from logger import setup_logger


class KubernetesTest(Test):
    def __init__(self, name, timeout, tests, delay=0):
        super().__init__(name, "kubernetes", timeout, tests, delay=delay)
        self._domains = {
            r"www\.example\.com": getenv("TEST_DOMAIN1_1"),
            r"auth\.example\.com": getenv("TEST_DOMAIN1_2"),
            r"app1\.example\.com": getenv("TEST_DOMAIN1"),
            r"app2\.example\.com": getenv("TEST_DOMAIN2"),
            r"app3\.example\.com": getenv("TEST_DOMAIN3"),
        }
        self.__logger = setup_logger("Kubernetes_test", getenv("LOGLEVEL", "INFO"))

    @staticmethod
    def init():
        try:
            if not Test.init():
                return False
            proc = run("sudo chown -R root:root /tmp/bw-data", shell=True)
            if proc.returncode != 0:
                raise (Exception("chown failed (k8s stack)"))
            if isdir("/tmp/kubernetes"):
                rmtree("/tmp/kubernetes")
            copytree("./integrations/kubernetes", "/tmp/kubernetes")
            copy("./tests/utils/k8s.yml", "/tmp/kubernetes")
            deploy = "/tmp/kubernetes/bunkerweb.yml"
            Test.replace_in_file(
                deploy, r"bunkerity/bunkerweb:.*$", "10.20.1.1:5000/bw-tests:latest"
            )
            Test.replace_in_file(
                deploy,
                r"bunkerity/bunkerweb-autoconf:.*$",
                "10.20.1.1:5000/bw-autoconf-tests:latest",
            )
            Test.replace_in_file(deploy, r"ifNotPresent", "Always")
            proc = run(
                "sudo kubectl apply -f k8s.yml", cwd="/tmp/kubernetes", shell=True
            )
            if proc.returncode != 0:
                raise (Exception("kubectl apply k8s failed (k8s stack)"))
            proc = run(
                "sudo kubectl apply -f rbac.yml", cwd="/tmp/kubernetes", shell=True
            )
            if proc.returncode != 0:
                raise (Exception("kubectl apply rbac failed (k8s stack)"))
            proc = run(
                "sudo kubectl apply -f bunkerweb.yml", cwd="/tmp/kubernetes", shell=True
            )
            if proc.returncode != 0:
                raise (Exception("kubectl apply bunkerweb failed (k8s stack)"))
            healthy = False
            i = 0
            while i < 30:
                proc = run(
                    "sudo kubectl get pods | grep bunkerweb | grep -v Running",
                    shell=True,
                    capture_output=True,
                )
                if "" == proc.stdout.decode():
                    healthy = True
                    break
                sleep(1)
                i += 1
            if not healthy:
                raise (Exception("k8s stack is not healthy"))
            sleep(60)
        except:
            setup_logger("Kubernetes_test", getenv("LOG_LEVEL", "INFO")).error(
                f"exception while running KubernetesTest.init()\n{format_exc()}",
            )
            return False
        return True

    @staticmethod
    def end():
        ret = True
        try:
            if not Test.end():
                return False
            proc = run(
                "sudo kubectl delete -f bunkerweb.yml",
                cwd="/tmp/kubernetes",
                shell=True,
            )
            if proc.returncode != 0:
                ret = False
            proc = run(
                "sudo kubectl delete -f rbac.yml", cwd="/tmp/kubernetes", shell=True
            )
            if proc.returncode != 0:
                ret = False
            proc = run(
                "sudo kubectl delete -f k8s.yml", cwd="/tmp/kubernetes", shell=True
            )
            if proc.returncode != 0:
                ret = False
            rmtree("/tmp/kubernetes")
        except:
            setup_logger("Kubernetes_test", getenv("LOG_LEVEL", "INFO")).error(
                f"exception while running KubernetesTest.end()\n{format_exc()}",
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
            setup = f"{test}/setup-kubernetes.sh"
            if isfile(setup):
                proc = run("sudo ./setup-kubernetes.sh", cwd=test, shell=True)
                if proc.returncode != 0:
                    raise (Exception("setup-kubernetes failed"))
            proc = run("sudo kubectl apply -f kubernetes.yml", shell=True, cwd=test)
            if proc.returncode != 0:
                raise (Exception("kubectl apply failed"))
        except:
            self.__logger.error(
                f"exception while running KubernetesTest._setup_test()\n{format_exc()}",
            )
            self._cleanup_test()
            return False
        return True

    def _cleanup_test(self):
        try:
            test = f"/tmp/tests/{self._name}"
            cleanup = f"{test}/cleanup-kubernetes.sh"
            if isfile(cleanup):
                proc = run("sudo ./cleanup-kubernetes.sh", cwd=test, shell=True)
                if proc.returncode != 0:
                    raise (Exception("cleanup-kubernetes failed"))
            proc = run("sudo kubectl delete -f kubernetes.yml", shell=True, cwd=test)
            if proc.returncode != 0:
                raise (Exception("kubectl delete failed"))
            super()._cleanup_test()
        except:
            self.__logger.error(
                f"exception while running KubernetesTest._cleanup_test()\n{format_exc()}",
            )
            return False
        return True

    def _debug_fail(self):
        proc = run(
            'sudo kubectl get pods --no-headers -o custom-columns=":metadata.name"',
            shell=True,
            capture_output=True,
        )
        for pod in proc.stdout.decode().splitlines():
            run(f"sudo kubectl logs {pod}", shell=True)
