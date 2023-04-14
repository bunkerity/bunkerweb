from Test import Test
from os.path import isdir, join, isfile
from os import chown, walk, getenv, listdir, mkdir
from shutil import copytree, rmtree, copy
from traceback import format_exc
from subprocess import run
from time import sleep
from logger import log
from yaml import safe_load_all, dump_all


class KubernetesTest(Test):
    def __init__(self, name, timeout, tests, delay=0):
        super().__init__(name, "kubernetes", timeout, tests, delay=delay)
        self._domains = {
            r"www\.example\.com": f"{Test.random_string(6)}.{getenv('TEST_DOMAIN1_2')}",
            r"auth\.example\.com": f"{Test.random_string(1)}.{getenv('TEST_DOMAIN1_2')}",
            r"app1\.example\.com": f"{Test.random_string(6)}.{getenv('TEST_DOMAIN1')}",
            r"app2\.example\.com": f"{Test.random_string(6)}.{getenv('TEST_DOMAIN2')}",
            r"app3\.example\.com": f"{Test.random_string(6)}.{getenv('TEST_DOMAIN3')}",
        }

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
                "USE_REAL_IP": "yes",
                "USE_PROXY_PROTOCOL": "yes",
                "REAL_IP_FROM": "100.64.0.0/16",
                "REAL_IP_HEADER": "proxy_protocol",
            }
            replace_env = {"API_WHITELIST_IP": "127.0.0.1/8 100.64.0.0/10"}
            for yaml in data:
                if yaml["metadata"]["name"] == "bunkerweb":
                    for k, v in append_env.items():
                        yaml["spec"]["template"]["spec"]["containers"][0]["env"].append(
                            {"name": k, "value": v}
                        )
                    for ele in yaml["spec"]["template"]["spec"]["containers"][0]["env"]:
                        if ele["name"] in replace_env:
                            ele["value"] = replace_env[ele["name"]]
                if yaml["metadata"]["name"] in [
                    "bunkerweb",
                    "bunkerweb-controller",
                    "bunkerweb-scheduler",
                ]:
                    yaml["spec"]["template"]["spec"]["imagePullSecrets"] = [
                        {"name": "secret-registry"}
                    ]
                yamls.append(yaml)
            with open(deploy, "w") as f:
                f.write(dump_all(yamls))
            Test.replace_in_file(
                deploy,
                r"bunkerity/bunkerweb:.*$",
                f"{getenv('PRIVATE_REGISTRY')}/infra/bunkerweb-tests:{getenv('IMAGE_TAG')}",
            )
            Test.replace_in_file(
                deploy,
                r"bunkerity/bunkerweb-autoconf:.*$",
                f"{getenv('PRIVATE_REGISTRY')}/infra/autoconf-tests:{getenv('IMAGE_TAG')}",
            )
            Test.replace_in_file(
                deploy,
                r"bunkerity/bunkerweb-scheduler:.*$",
                f"{getenv('PRIVATE_REGISTRY')}/infra/scheduler-tests:{getenv('IMAGE_TAG')}",
            )
            proc = run(
                "kubectl apply -f bunkerweb.yml", cwd="/tmp/kubernetes", shell=True
            )
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

    def end():
        ret = True
        try:
            if not Test.end():
                return False
            proc = run(
                "kubectl delete -f bunkerweb.yml", cwd="/tmp/kubernetes", shell=True
            )
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
            deploy = f"/tmp/tests/{self._name}/kubernetes.yml"
            example_data = f"./examples/{self._name}/bw-data"
            for ex_domain, test_domain in self._domains.items():
                Test.replace_in_files(test, ex_domain, test_domain)
                Test.rename(test, ex_domain, test_domain)
            Test.replace_in_files(test, "example.com", getenv("ROOT_DOMAIN"))
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
