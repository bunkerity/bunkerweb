from re import escape
from Test import Test
from os.path import isfile
from os import getenv
from traceback import format_exc
from subprocess import run
from time import sleep
from logger import log


class LinuxTest(Test):
    def __init__(self, name, timeout, tests, distro, domains={}):
        super().__init__(name, "linux", timeout, tests, delay=20)
        self._domains = domains
        if distro not in (
            "ubuntu",
            "debian-bookworm",
            "debian-trixie",
            "fedora-41",
            "fedora-42",
            "fedora-43",
            "centos",
            "ubuntu-jammy",
        ) and not distro.startswith("rhel"):
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
            if distro in ("ubuntu", "debian-bookworm", "debian-trixie", "ubuntu-jammy"):
                cmd = "echo force-bad-version >> /etc/dpkg/dpkg.cfg ; apt install -y /opt/\\$(ls /opt | grep deb)"
            elif distro == "centos" or distro.startswith(("rhel", "fedora")):
                cmd = "dnf install -y /opt/\\$(ls /opt | grep rpm)"
            proc = LinuxTest.docker_exec(distro, cmd)
            if proc.returncode != 0:
                raise Exception("docker exec apt install failed (linux stack)")
            proc = LinuxTest.docker_exec(distro, "systemctl start bunkerweb")
            if proc.returncode != 0:
                raise Exception("docker exec systemctl start failed (linux stack)")
            proc = LinuxTest.docker_exec(distro, "systemctl start bunkerweb-scheduler")
            if proc.returncode != 0:
                raise Exception("docker exec systemctl start failed (linux stack)")
            if distro in ("ubuntu", "debian-bookworm", "debian-trixie", "ubuntu-jammy"):
                LinuxTest.docker_exec(
                    distro,
                    "DEBIAN_FRONTEND=noninteractive apt-get install -y php-fpm unzip",
                )
                php_versions = {
                    "debian-trixie": "8.4",
                    "ubuntu": "8.3",
                    "debian-bookworm": "8.2",
                    "ubuntu-jammy": "8.1",
                }
                php_ver = php_versions.get(distro)
                if php_ver:
                    LinuxTest.docker_cp(
                        distro,
                        "./tests/www-deb.conf",
                        f"/etc/php/{php_ver}/fpm/pool.d/www.conf",
                    )
                    LinuxTest.docker_exec(distro, f"systemctl restart php{php_ver}-fpm")
            elif distro == "centos" or distro.startswith(("rhel", "fedora")):
                if distro.startswith("rhel"):
                    if distro == "rhel-8":
                        LinuxTest.docker_exec(distro, "dnf install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-8.noarch.rpm")
                        LinuxTest.docker_exec(distro, "dnf install -y https://rpms.remirepo.net/enterprise/remi-release-8.rpm")
                    elif distro == "rhel-9":
                        LinuxTest.docker_exec(distro, "dnf install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-9.noarch.rpm")
                        LinuxTest.docker_exec(distro, "dnf install -y https://rpms.remirepo.net/enterprise/remi-release-9.rpm")
                        LinuxTest.docker_exec(distro, "dnf install -y python3.11")
                        LinuxTest.docker_exec(distro, "update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.9 1")
                        LinuxTest.docker_exec(distro, "update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 2")
                        LinuxTest.docker_exec(distro, "update-alternatives --set python3 /usr/bin/python3.11")
                    elif distro == "rhel-10":
                        LinuxTest.docker_exec(distro, "dnf install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-10.noarch.rpm")
                        LinuxTest.docker_exec(distro, "dnf install -y https://rpms.remirepo.net/enterprise/remi-release-10.rpm")
                    LinuxTest.docker_exec(distro, "dnf module reset php -y")
                    LinuxTest.docker_exec(distro, "dnf module enable php:remi-8.3 -y")

                LinuxTest.docker_exec(distro, "dnf install -y php-fpm unzip")
                LinuxTest.docker_cp(distro, "./tests/www-rpm.conf", "/etc/php-fpm.d/www.conf")
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
            log("LINUX", "❌", f"exception while running LinuxTest.end()\n{format_exc()}")
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
            proc = self.docker_cp(self.__distro, test, f"/opt/{self._name}")
            if proc.returncode != 0:
                raise Exception("docker cp failed (test)")
            setup = f"{test}/setup-linux.sh"
            if isfile(setup):
                proc = self.docker_exec(
                    self.__distro,
                    f"cd /opt/{self._name} && ./setup-linux.sh && chown -R nginx:nginx /etc/bunkerweb/configs",
                )
                if proc.returncode != 0:
                    raise Exception("docker exec setup failed (test)")
            proc = self.docker_exec(self.__distro, f"cp /opt/{self._name}/variables.env /etc/bunkerweb/")
            if proc.returncode != 0:
                raise Exception("docker exec cp variables.env failed (test)")
            proc = self.docker_exec(
                self.__distro,
                "echo '' >> /etc/bunkerweb/variables.env ; echo 'USE_LETS_ENCRYPT_STAGING=yes' >> /etc/bunkerweb/variables.env ; echo 'LETS_ENCRYPT_MAX_RETRIES=3' >> /etc/bunkerweb/variables.env ; echo 'LOG_LEVEL=info' >> /etc/bunkerweb/variables.env ; echo 'USE_BUNKERNET=no' >> /etc/bunkerweb/variables.env ; echo 'SEND_ANONYMOUS_REPORT=no' >> /etc/bunkerweb/variables.env ; echo 'USE_DNSBL=no' >> /etc/bunkerweb/variables.env",
            )
            if proc.returncode != 0:
                raise (Exception("docker exec append variables.env failed (test)"))
            proc = self.docker_exec(self.__distro, "systemctl restart bunkerweb")
            if proc.returncode != 0:
                raise Exception("docker exec systemctl restart failed (linux stack)")
            proc = self.docker_exec(self.__distro, "systemctl restart bunkerweb-scheduler")
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
                f"cd /opt/{self._name} ; ./cleanup-linux.sh ; rm -rf /etc/bunkerweb/configs/* ; rm -rf /etc/bunkerweb/plugins/* ; rm -rf /var/www/html/* ; journalctl --rotate --vacuum-time=1s ; truncate -s 0 /var/log/bunkerweb/error.log ; truncate -s 0 /var/log/bunkerweb/access.log ; truncate -s 0 /var/log/bunkerweb/scheduler.log ; truncate -s 0 /var/log/bunkerweb/scheduler.log",
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
            "cat /var/log/bunkerweb/access.log ; cat /var/log/bunkerweb/error.log ; cat /var/log/bunkerweb/scheduler.log ; journalctl -u bunkerweb --no-pager ; journalctl -u bunkerweb-scheduler --no-pager",
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
