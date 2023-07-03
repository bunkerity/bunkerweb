from Test import Test
from os.path import isfile
from os import getenv
from traceback import format_exc
from subprocess import run
from time import sleep
from logger import log


class LinuxTest(Test):
    def __init__(self, name, timeout, tests, distro):
        super().__init__(name, "linux", timeout, tests)
        self._domains = {
            r"www\.example\.com": f"{Test.random_string(6)}.{getenv('TEST_DOMAIN1')}",
            r"auth\.example\.com": f"{Test.random_string(6)}.{getenv('TEST_DOMAIN1')}",
            r"app1\.example\.com": f"{Test.random_string(6)}.{getenv('TEST_DOMAIN1_1')}",
            r"app2\.example\.com": f"{Test.random_string(6)}.{getenv('TEST_DOMAIN1_2')}",
            r"app3\.example\.com": f"{Test.random_string(6)}.{getenv('TEST_DOMAIN1_3')}",
        }
        if not distro in ("ubuntu", "debian", "fedora", "centos", "rhel"):
            raise Exception(f"unknown distro {distro}")
        self.__distro = distro

    @staticmethod
    def init(distro):
        try:
            if not Test.init():
                return False
            cmd = f"docker run -p 80:80 -p 443:443 --rm --name linux-{distro} -d --tmpfs /tmp --tmpfs /run --tmpfs /run/lock -v /sys/fs/cgroup:/sys/fs/cgroup:rw --cgroupns=host --tty local/{distro}:latest"
            proc = run(cmd, shell=True)
            if proc.returncode != 0:
                raise Exception("docker run failed (linux stack)")
            if distro in ("ubuntu", "debian"):
                cmd = "apt install -y /opt/\$(ls /opt | grep deb)"
            elif distro in ("centos", "fedora", "rhel"):
                cmd = "dnf install -y /opt/\$(ls /opt | grep rpm)"
            proc = LinuxTest.docker_exec(distro, cmd)
            if proc.returncode != 0:
                raise Exception("docker exec apt install failed (linux stack)")
            proc = LinuxTest.docker_exec(distro, "systemctl start bunkerweb")
            if proc.returncode != 0:
                raise Exception("docker exec systemctl start failed (linux stack)")
            if distro in ("ubuntu", "debian"):
                LinuxTest.docker_exec(
                    distro,
                    "DEBIAN_FRONTEND=noninteractive apt-get install -y php-fpm unzip",
                )
                if distro == "ubuntu":
                    LinuxTest.docker_cp(
                        distro,
                        "./tests/www-deb.conf",
                        "/etc/php/8.1/fpm/pool.d/www.conf",
                    )
                    LinuxTest.docker_exec(
                        distro, "systemctl stop php8.1-fpm ; systemctl start php8.1-fpm"
                    )
                elif distro == "debian":
                    LinuxTest.docker_cp(
                        distro,
                        "./tests/www-deb.conf",
                        "/etc/php/7.4/fpm/pool.d/www.conf",
                    )
                    LinuxTest.docker_exec(
                        distro, "systemctl stop php7.4-fpm ; systemctl start php7.4-fpm"
                    )
            elif distro in ("centos", "fedora", "rhel"):
                LinuxTest.docker_exec(distro, "dnf install -y php-fpm unzip")
                LinuxTest.docker_cp(
                    distro, "./tests/www-rpm.conf", "/etc/php-fpm.d/www.conf"
                )
                LinuxTest.docker_exec(
                    distro,
                    "mkdir /run/php ; chmod 777 /run/php ; systemctl stop php-fpm ; systemctl start php-fpm",
                )
            sleep(60)
        except:
            log(
                "LINUX",
                "❌",
                f"exception while running LinuxTest.init()\n{format_exc()}",
            )
            return False
        return True

    @staticmethod
    def end(distro):
        ret = True
        try:
            if not Test.end():
                return False
            proc = run(f"docker kill linux-{distro}", shell=True)
            if proc.returncode != 0:
                ret = False
        except:
            log(
                "LINUX", "❌", f"exception while running LinuxTest.end()\n{format_exc()}"
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
            proc = self.docker_cp(self.__distro, test, f"/opt/{self._name}")
            if proc.returncode != 0:
                raise Exception("docker cp failed (test)")
            setup = f"{test}/setup-linux.sh"
            if isfile(setup):
                proc = self.docker_exec(
                    self.__distro, f"cd /opt/{self._name} && ./setup-linux.sh"
                )
                if proc.returncode != 0:
                    raise Exception("docker exec setup failed (test)")
            proc = self.docker_exec(
                self.__distro, f"cp /opt/{self._name}/variables.env /etc/bunkerweb/"
            )
            if proc.returncode != 0:
                raise Exception("docker exec cp variables.env failed (test)")
            proc = self.docker_exec(
                self.__distro,
                "echo '' >> /etc/bunkerweb/variables.env ; echo 'USE_LETS_ENCRYPT_STAGING=yes' >> /etc/bunkerweb/variables.env",
            )
            if proc.returncode != 0:
                raise (Exception("docker exec append variables.env failed (test)"))
            proc = self.docker_exec(
                self.__distro, "systemctl stop bunkerweb ; systemctl start bunkerweb"
            )
            if proc.returncode != 0:
                raise Exception("docker exec systemctl restart failed (linux stack)")
        except:
            log(
                "LINUX",
                "❌",
                f"exception while running LinuxTest._setup_test()\n{format_exc()}",
            )
            self._debug_fail()
            self._cleanup_test()
            return False
        return True

    def _cleanup_test(self):
        try:
            proc = self.docker_exec(
                self.__distro,
                f"cd /opt/{self._name} ; ./cleanup-linux.sh ; rm -rf /etc/bunkerweb/configs/* ; rm -rf /etc/bunkerweb/plugins/* ; rm -rf /var/www/html/*",
            )
            if proc.returncode != 0:
                raise Exception("docker exec rm failed (cleanup)")
            super()._cleanup_test()
        except:
            log(
                "DOCKER",
                "❌",
                f"exception while running LinuxTest._cleanup_test()\n{format_exc()}",
            )
            return False
        return True

    def _debug_fail(self):
        self.docker_exec(
            self.__distro,
            "cat /var/log/nginx/access.log ; cat /var/log/nginx/error.log ; journalctl -u bunkerweb --no-pager",
        )

    @staticmethod
    def docker_exec(distro, cmd_linux):
        return run(
            f'docker exec linux-{distro} /bin/bash -c "{cmd_linux}"',
            shell=True,
        )

    @staticmethod
    def docker_cp(distro, src, dst):
        return run(f"sudo docker cp {src} linux-{distro}:{dst}", shell=True)
