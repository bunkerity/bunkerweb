from re import escape
from Test import Test
from os.path import isfile
from os import getenv, mkdir
from shutil import rmtree, copy
from traceback import format_exc
from subprocess import run
from time import sleep
from logger import log
from yaml import safe_load_all, dump_all


class KubernetesTest(Test):
    def __init__(self, name, timeout, tests, delay=0, domains={}):
        super().__init__(name, "kubernetes", timeout, tests, delay=delay)
        self._domains = domains

    @staticmethod
    def init():
        try:
            if not Test.init():
                return False
            mkdir("/tmp/kubernetes")
            copy("./misc/integrations/k8s.mariadb.yml", "/tmp/kubernetes/bunkerweb.yml")
            deploy = "/tmp/kubernetes/bunkerweb.yml"
            yamls = []
            with open(deploy, "r") as f:
                data = safe_load_all(f.read())
            append_env = {
                "AUTO_LETS_ENCRYPT": "yes",
                "USE_LETS_ENCRYPT_STAGING": "yes",
                "LETS_ENCRYPT_MAX_RETRIES": "3",
                "LETS_ENCRYPT_PROFILE": "shortlived",
                "USE_REAL_IP": "yes",
                "USE_PROXY_PROTOCOL": "yes",
                "REAL_IP_FROM": "100.64.0.0/10 192.168.0.0/16 172.16.0.0/12 10.0.0.0/8",
                "REAL_IP_HEADER": "proxy_protocol",
                "LOG_LEVEL": "info",
                "CUSTOM_LOG_LEVEL": "debug",
                "USE_BUNKERNET": "no",
                "SEND_ANONYMOUS_REPORT": "no",
                "USE_DNSBL": "no",
            }
            replace_env = {"API_WHITELIST_IP": "127.0.0.1/8 100.64.0.0/10 192.168.0.0/16 172.16.0.0/12 10.0.0.0/8"}
            for yaml in data:
                if yaml["metadata"]["name"] == "bunkerweb" and yaml["kind"] == "DaemonSet":
                    for ele in yaml["spec"]["template"]["spec"]["containers"][0]["env"]:
                        if ele["name"] in replace_env:
                            ele["value"] = replace_env[ele["name"]]
                if yaml["metadata"]["name"] == "bunkerweb-scheduler":
                    for k, v in append_env.items():
                        yaml["spec"]["template"]["spec"]["containers"][0]["env"].append({"name": k, "value": v})
                    for ele in yaml["spec"]["template"]["spec"]["containers"][0]["env"]:
                        if ele["name"] in replace_env:
                            ele["value"] = replace_env[ele["name"]]
                if yaml["metadata"]["name"] == "bunkerweb-controller":
                    yaml["spec"]["template"]["spec"]["containers"][0]["env"].append({"name": "CUSTOM_LOG_LEVEL", "value": "debug"})
                if (
                    yaml["metadata"]["name"]
                    in [
                        "bunkerweb",
                        "bunkerweb-controller",
                        "bunkerweb-scheduler",
                    ]
                    and yaml["kind"] != "IngressClass"
                ):
                    yaml["spec"]["template"]["spec"]["imagePullSecrets"] = [{"name": "secret-registry"}]
                yamls.append(yaml)
            with open(deploy, "w") as f:
                f.write(dump_all(yamls))
            Test.replace_in_file(
                deploy,
                r"bunkerity/bunkerweb:.*$",
                f"ghcr.io/bunkerity/bunkerweb-tests:{getenv('IMAGE_TAG')}",
            )
            Test.replace_in_file(
                deploy,
                r"bunkerity/bunkerweb-autoconf:.*$",
                f"ghcr.io/bunkerity/autoconf-tests:{getenv('IMAGE_TAG')}",
            )
            Test.replace_in_file(
                deploy,
                r"bunkerity/bunkerweb-scheduler:.*$",
                f"ghcr.io/bunkerity/scheduler-tests:{getenv('IMAGE_TAG')}",
            )
            proc = run("kubectl apply -f bunkerweb.yml", cwd="/tmp/kubernetes", shell=True)
            if proc.returncode != 0:
                raise (Exception("kubectl apply bunkerweb failed (k8s stack)"))
            healthy = False
            i = 0
            while i < 120:
                proc = run(
                    "kubectl get pods | grep bunkerweb | grep -v Running",
                    shell=True,
                    capture_output=True,
                )
                if "" == proc.stdout.decode():
                    healthy = True
                    break
                sleep(1)
                i += 1
            if not healthy:
                run(
                    "kubectl describe daemonset/bunkerweb",
                    cwd="/tmp/kubernetes",
                    shell=True,
                )
                run(
                    "kubectl logs daemonset/bunkerweb",
                    cwd="/tmp/kubernetes",
                    shell=True,
                )
                run(
                    "kubectl describe deployment/bunkerweb-controller",
                    cwd="/tmp/kubernetes",
                    shell=True,
                )
                run(
                    "kubectl logs deployment/bunkerweb-controller",
                    cwd="/tmp/kubernetes",
                    shell=True,
                )
                run(
                    "kubectl describe deployment/bunkerweb-scheduler",
                    cwd="/tmp/kubernetes",
                    shell=True,
                )
                run(
                    "kubectl logs deployment/bunkerweb-scheduler",
                    cwd="/tmp/kubernetes",
                    shell=True,
                )
                run(
                    "kubectl describe deployment/bunkerweb-db",
                    cwd="/tmp/kubernetes",
                    shell=True,
                )
                run(
                    "kubectl logs deployment/bunkerweb-db",
                    cwd="/tmp/kubernetes",
                    shell=True,
                )
                run(
                    "kubectl logs deployment/bunkerweb-redis",
                    cwd="/tmp/kubernetes",
                    shell=True,
                )
                run(
                    "kubectl describe pods",
                    cwd="/tmp/kubernetes",
                    shell=True,
                )
                run(
                    "kubectl describe pvc",
                    cwd="/tmp/kubernetes",
                    shell=True,
                )
                run(
                    "kubectl describe pv",
                    cwd="/tmp/kubernetes",
                    shell=True,
                )
                raise (Exception("k8s stack is not healthy"))
            sleep(60)
        except:
            log(
                "KUBERNETES",
                "❌",
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
            proc = run("kubectl delete -f bunkerweb.yml", cwd="/tmp/kubernetes", shell=True)
            if proc.returncode != 0:
                ret = False
            rmtree("/tmp/kubernetes")
        except:
            log(
                "KUBERNETES",
                "❌",
                f"exception while running KubernetesTest.end()\n{format_exc()}",
            )
            return False
        return ret

    def _setup_test(self):
        try:
            super()._setup_test()
            test = f"/tmp/tests/{self._name}"
            for ex_domain, test_domain in self._domains.items():
                Test.replace_in_files(test, escape(ex_domain), test_domain)
                Test.rename(test, ex_domain, test_domain)
            Test.replace_in_files(test, escape("example.com"), getenv("ROOT_DOMAIN"))
            setup = f"{test}/setup-kubernetes.sh"
            if isfile(setup):
                proc = run("./setup-kubernetes.sh", cwd=test, shell=True)
                if proc.returncode != 0:
                    raise (Exception("setup-kubernetes failed"))
            proc = run("kubectl apply -f kubernetes.yml", shell=True, cwd=test)
            if proc.returncode != 0:
                raise (Exception("kubectl apply failed"))
        except:
            log(
                "KUBERNETES",
                "❌",
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
                proc = run("./cleanup-kubernetes.sh", cwd=test, shell=True)
                if proc.returncode != 0:
                    raise (Exception("cleanup-kubernetes failed"))
            proc = run("kubectl delete -f kubernetes.yml", shell=True, cwd=test)
            if proc.returncode != 0:
                raise (Exception("kubectl delete failed"))
            super()._cleanup_test()
        except:
            log(
                "KUBERNETES",
                "❌",
                f"exception while running KubernetesTest._cleanup_test()\n{format_exc()}",
            )
            return False
        return True

    def _debug_fail(self):
        proc = run(
            'kubectl get pods --no-headers -o custom-columns=":metadata.name"',
            shell=True,
            capture_output=True,
        )
        for pod in proc.stdout.decode().splitlines():
            run(f"kubectl logs {pod}", shell=True)
