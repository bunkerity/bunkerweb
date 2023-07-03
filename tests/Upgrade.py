import subprocess
import sys
import tempfile
import os
import time
import pathlib

NGINX_VERSION = "1.24.0"

distro = sys.argv[1]
if distro == "ubuntu":
    test_results = {
        "Installation test": None,
        "Reloading test": None,
        "Removing test": None,
        "Purging test": None,
        "Upgrading test": None,
    }
    subprocess.run(
        [
            "sudo",
            "docker",
            "build",
            "-t",
            "ubuntu-image",
            "-f",
            "src/linux/Dockerfile-ubuntu",
            ".",
        ]
    )
    subprocess.run(
        [
            "docker",
            "run",
            "-it",
            "--name",
            "ubuntu-container",
            "-v",
            "deb:/data",
            "ubuntu-image",
        ]
    )
    subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            "systemd-{}".format(distro),
            "--privileged",
            "-v",
            "/sys/fs/cgroup:/sys/fs/cgroup",
            "-v",
            "deb:/data",
            "jrei/systemd-ubuntu:22.04",
        ]
    )

    # Installing test
    print("Installing bunkerweb...")
    bash_script = """
    apt update && apt install -y sudo && \
    sudo apt install -y curl gnupg2 ca-certificates lsb-release ubuntu-keyring && \
    curl https://nginx.org/keys/nginx_signing.key | gpg --dearmor \
    | sudo tee /usr/share/keyrings/nginx-archive-keyring.gpg >/dev/null && \
    echo "deb [signed-by=/usr/share/keyrings/nginx-archive-keyring.gpg] \
    http://nginx.org/packages/ubuntu `lsb_release -cs` nginx" \
    | sudo tee /etc/apt/sources.list.d/nginx.list
    sudo apt update && \
    sudo apt install -y nginx=1.22.1-1~jammy
    sudo apt install /data/bunkerweb.deb -y
    """

    with tempfile.NamedTemporaryFile(mode="w") as f:
        f.write(bash_script)
        f.flush()
        subprocess.run(
            ["docker", "cp", f.name, "systemd-ubuntu:/data/install_nginx.sh"]
        )
        result = subprocess.run(
            [
                "docker",
                "exec",
                "-it",
                "systemd-ubuntu",
                "bash",
                "/data/install_nginx.sh",
            ]
        )
    if result.returncode != 0:
        bunkerweb_logs = subprocess.run(
            [
                "docker",
                "exec",
                "-it",
                "systemd-ubuntu",
                "bash",
                "-c",
                "systemctl status bunkerweb.service",
            ],
            capture_output=True,
        )
        print("Logs from bunkerweb:", bunkerweb_logs.stdout.decode())

        bunkerweb_ui_logs = subprocess.run(
            [
                "docker",
                "exec",
                "-it",
                "systemd-ubuntu",
                "bash",
                "-c",
                "systemctl status bunkerweb-ui.service",
            ],
            capture_output=True,
        )
        print("Logs from bunkerweb-ui:", bunkerweb_ui_logs.stdout.decode())
        sys.exit(result.returncode)
        exit(result.returncode)
    else:
        print("✔️ Installation successful ✔️")
    # Checking Installation test
    try:
        if result.returncode == 0:
            test_results["Installation test"] = "OK"
        else:
            test_results["Installation test"] = "KO"
            sys.exit(1)
    except:
        test_results["Installation test"] = "KO"
        sys.exit(1)

    # Reloading test
    print("Reloading bunkerweb...")
    subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-ubuntu",
            "bash",
            "-c",
            "echo 'HTTPS_PORT=8443' >> /etc/bunkerweb/variables.env",
        ]
    )
    subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-ubuntu",
            "bash",
            "-c",
            "echo 'new_value=1' >> /etc/bunkerweb/ui.env",
        ]
    )
    subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-ubuntu",
            "bash",
            "-c",
            "systemctl reload bunkerweb",
        ]
    )
    subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-ubuntu",
            "bash",
            "-c",
            "systemctl reload bunkerweb-ui",
        ]
    )

    bunkerweb_state = subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-ubuntu",
            "bash",
            "-c",
            "systemctl is-active bunkerweb.service",
        ],
        capture_output=True,
    )
    if bunkerweb_state.stdout.decode().strip() != "active":
        bunkerweb_logs = subprocess.run(
            [
                "docker",
                "exec",
                "-it",
                "systemd-ubuntu",
                "bash",
                "-c",
                "journalctl -u bunkerweb.service",
            ],
            capture_output=True,
        )
        print(
            "❌ bunkerweb.service is not running. Logs:", bunkerweb_logs.stdout.decode()
        )

    bunkerweb_ui_state = subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-ubuntu",
            "bash",
            "-c",
            "systemctl is-active bunkerweb-ui.service",
        ],
        capture_output=True,
    )
    if bunkerweb_ui_state.stdout.decode().strip() != "active":
        bunkerweb_ui_logs = subprocess.run(
            [
                "docker",
                "exec",
                "-it",
                "systemd-ubuntu",
                "bash",
                "-c",
                "journalctl -u bunkerweb-ui.service",
            ],
            capture_output=True,
        )
        print(
            "❌ bunkerweb-ui.service is not running. Logs:",
            bunkerweb_ui_logs.stdout.decode(),
        )
    else:
        print("✔️ bunkerweb.service and bunkerweb-ui.service are running ✔️")
    # Checking Reloading test
    try:
        if bunkerweb_state.stdout.decode().strip() == "active":
            test_results["Reloading test"] = "OK"
        else:
            test_results["Reloading test"] = "KO"
    except:
        test_results["Reloading test"] = "KO"

    # Removing test
    print("Removing bunkerweb...")
    subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-ubuntu",
            "bash",
            "-c",
            "sudo apt remove -y bunkerweb",
        ]
    )

    result = subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-ubuntu",
            "bash",
            "-c",
            "[ -d /usr/share/bunkerweb ]",
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        print("✔️ /usr/share/bunkerweb not found.")
    else:
        print("❌ /usr/share/bunkerweb found.")

    result = subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-ubuntu",
            "bash",
            "-c",
            "[ -d /var/tmp/bunkerweb ]",
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        print("✔️ /var/tmp/bunkerweb not found.")
    else:
        print("❌ /var/tmp/bunkerweb found.")

    result = subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-ubuntu",
            "bash",
            "-c",
            "[ -d /var/cache/bunkerweb ]",
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        print("✔️ /var/cache/bunkerweb not found.")
    else:
        print("❌ /var/cache/bunkerweb found.")

    result = subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-ubuntu",
            "bash",
            "-c",
            "[ -f /usr/bin/bwcli ]",
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        print("✔️ /usr/bin/bwcli not found.")
    else:
        print("❌ /usr/bin/bwcli found.")
    # Checking Removing test
    try:
        if (
            pathlib.Path("/usr/share/bunkerweb").is_dir()
            or pathlib.Path("/var/tmp/bunkerweb").is_dir()
            or pathlib.Path("/var/cache/bunkerweb").is_dir()
            or pathlib.Path("/usr/bin/bwcli").is_file()
        ):
            test_results["Removing test"] = "KO"
        else:
            test_results["Removing test"] = "OK"
    except:
        test_results["Removing test"] = "KO"

    # Purging test
    print("Purging bunkerweb...")
    subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-ubuntu",
            "bash",
            "-c",
            "sudo apt purge -y bunkerweb",
        ]
    )

    result = subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-ubuntu",
            "bash",
            "-c",
            "[ -d /var/lib/bunkerweb ]",
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        print("✔️ /var/lib/bunkerweb not found.")
    else:
        print("❌ /var/lib/bunkerweb found.")

    result = subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-ubuntu",
            "bash",
            "-c",
            "[ -d /etc/bunkerweb ]",
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        print("✔️ /etc/bunkerweb not found.")
    else:
        print("❌ /etc/bunkerweb found.")
    # Checking Purging test
    try:
        if (
            pathlib.Path("/var/lib/bunkerweb").is_dir()
            or pathlib.Path("/etc/bunkerweb").is_dir()
        ):
            test_results["Purging test"] = "KO"
        else:
            test_results["Purging test"] = "OK"
    except:
        test_results["Purging test"] = "KO"

    # Upgrading test
    print("Upgrading bunkerweb...")
    # Installing official package
    subprocess.run(
        [
            "docker",
            "rm",
            "-f",
            "systemd-ubuntu",
        ]
    )
    subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            "systemd-{}".format(distro),
            "--privileged",
            "-v",
            "/sys/fs/cgroup:/sys/fs/cgroup",
            "-v",
            "deb:/data",
            "jrei/systemd-ubuntu:22.04",
        ]
    )
    print("Installing bunkerweb...")
    bash_script = """
    apt update && apt install -y sudo && \
    sudo apt install -y curl gnupg2 ca-certificates lsb-release ubuntu-keyring && \
    curl https://nginx.org/keys/nginx_signing.key | gpg --dearmor \
    | sudo tee /usr/share/keyrings/nginx-archive-keyring.gpg >/dev/null && \
    echo "deb [signed-by=/usr/share/keyrings/nginx-archive-keyring.gpg] \
    http://nginx.org/packages/ubuntu `lsb_release -cs` nginx" \
    | sudo tee /etc/apt/sources.list.d/nginx.list
    sudo apt update && sudo apt install -y nginx=1.20.2-1~jammy
    curl -s https://packagecloud.io/install/repositories/bunkerity/bunkerweb/script.deb.sh | sudo bash && \
    sudo apt update && \
    sudo apt install -y bunkerweb=1.4.5
    """

    with tempfile.NamedTemporaryFile(mode="w") as f:
        f.write(bash_script)
        f.flush()
        subprocess.run(
            ["docker", "cp", f.name, "systemd-ubuntu:/data/install_nginx.sh"]
        )
        result = subprocess.run(
            [
                "docker",
                "exec",
                "-it",
                "systemd-ubuntu",
                "bash",
                "/data/install_nginx.sh",
            ]
        )

    # Checking version
    old_version = subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-ubuntu",
            "bash",
            "-c",
            "cat /opt/bunkerweb/VERSION",
        ],
        capture_output=True,
    )
    print("Old version:", old_version.stdout.decode().strip())

    # Upgrading package
    subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-ubuntu",
            "bash",
            "-c",
            "sudo apt remove -y nginx",
        ]
    )
    subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-ubuntu",
            "bash",
            "-c",
            "sudo apt purge -y nginx",
        ]
    )
    subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-ubuntu",
            "bash",
            "-c",
            "sudo apt autoremove -y",
        ]
    )
    subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-ubuntu",
            "bash",
            "-c",
            "sudo apt upgrade -y /data/bunkerweb.deb",
        ]
    )

    # Checking version
    new_version = subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-ubuntu",
            "bash",
            "-c",
            "cat /usr/share/bunkerweb/VERSION",
        ],
        capture_output=True,
    )
    print("New version:", new_version.stdout.decode().strip())
    try:
        if old_version.stdout.decode().strip() != new_version.stdout.decode().strip():
            test_results["Upgrading test"] = "OK"
        else:
            test_results["Upgrading test"] = "KO"
    except:
        test_results["Upgrading test"] = "KO"

    # Print summary
    for key, value in test_results.items():
        print(f"{key}: {value}")
    if "KO" in test_results.values():
        print("❌ Some tests failed.")
        sys.exit(1)

elif distro == "debian":
    test_results = {
        "Installation test": None,
        "Reloading test": None,
        "Removing test": None,
        "Purging test": None,
        "Upgrading test": None,
    }
    subprocess.run(
        [
            "sudo",
            "docker",
            "build",
            "-t",
            "debian-image",
            "-f",
            "src/linux/Dockerfile-debian",
            ".",
        ]
    )
    subprocess.run(
        [
            "docker",
            "run",
            "-it",
            "--name",
            "debian-container",
            "-v",
            "deb:/data",
            "debian-image",
        ]
    )
    subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            "systemd-{}".format(distro),
            "--privileged",
            "-v",
            "/sys/fs/cgroup:/sys/fs/cgroup",
            "-v",
            "deb:/data",
            "jrei/systemd-debian:11",
        ]
    )

    # Installing test
    print("Installing bunkerweb...")
    bash_script = """
    apt update && apt install -y sudo && \
    apt-get install gnupg2 ca-certificates lsb-release wget curl -y && \
    echo "deb https://nginx.org/packages/debian/ bullseye nginx" > /etc/apt/sources.list.d/nginx.list && \
    echo "deb-src https://nginx.org/packages/debian/ bullseye nginx" >> /etc/apt/sources.list.d/nginx.list && \
    apt-key adv --keyserver keyserver.ubuntu.com --recv-keys ABF5BD827BD9BF62 && \
    apt-get update && \
    apt-get install -y --no-install-recommends nginx=1.22.1-1~bullseye
    apt install /data/bunkerweb.deb -y
    """

    with tempfile.NamedTemporaryFile(mode="w") as f:
        f.write(bash_script)
        f.flush()
        subprocess.run(["docker", "cp", f.name, "systemd-debian:/tmp/install_nginx.sh"])
        result = subprocess.run(
            ["docker", "exec", "-it", "systemd-debian", "bash", "/tmp/install_nginx.sh"]
        )
    if result.returncode != 0:
        bunkerweb_logs = subprocess.run(
            [
                "docker",
                "exec",
                "-it",
                "systemd-debian",
                "bash",
                "-c",
                "systemctl status bunkerweb.service",
            ],
            capture_output=True,
        )
        print("Logs from bunkerweb:", bunkerweb_logs.stdout.decode())

        bunkerweb_ui_logs = subprocess.run(
            [
                "docker",
                "exec",
                "-it",
                "systemd-debian",
                "bash",
                "-c",
                "systemctl status bunkerweb-ui.service",
            ],
            capture_output=True,
        )
        print("Logs from bunkerweb-ui:", bunkerweb_ui_logs.stdout.decode())
        sys.exit(result.returncode)
        exit(result.returncode)
    else:
        print("✔️ Installation successful ✔️")
    # Checking Installation test
    try:
        if result.returncode == 0:
            test_results["Installation test"] = "OK"
        else:
            test_results["Installation test"] = "KO"
            sys.exit(1)
    except:
        test_results["Installation test"] = "KO"
        sys.exit(1)

    # Reloading test
    print("Reloading bunkerweb...")
    subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-debian",
            "bash",
            "-c",
            "echo 'HTTPS_PORT=8443' >> /etc/bunkerweb/variables.env",
        ]
    )
    subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-debian",
            "bash",
            "-c",
            "echo 'new_value=1' >> /etc/bunkerweb/ui.env",
        ]
    )
    subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-debian",
            "bash",
            "-c",
            "systemctl reload bunkerweb",
        ]
    )
    subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-debian",
            "bash",
            "-c",
            "systemctl reload bunkerweb-ui",
        ]
    )

    bunkerweb_state = subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-debian",
            "bash",
            "-c",
            "systemctl is-active bunkerweb.service",
        ],
        capture_output=True,
    )
    if bunkerweb_state.stdout.decode().strip() != "active":
        bunkerweb_logs = subprocess.run(
            [
                "docker",
                "exec",
                "-it",
                "systemd-debian",
                "bash",
                "-c",
                "journalctl -u bunkerweb.service",
            ],
            capture_output=True,
        )
        print(
            "❌ bunkerweb.service is not running. Logs:", bunkerweb_logs.stdout.decode()
        )

    bunkerweb_ui_state = subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-debian",
            "bash",
            "-c",
            "systemctl is-active bunkerweb-ui.service",
        ],
        capture_output=True,
    )
    if bunkerweb_ui_state.stdout.decode().strip() != "active":
        bunkerweb_ui_logs = subprocess.run(
            [
                "docker",
                "exec",
                "-it",
                "systemd-debian",
                "bash",
                "-c",
                "journalctl -u bunkerweb-ui.service",
            ],
            capture_output=True,
        )
        print(
            "❌ bunkerweb-ui.service is not running. Logs:",
            bunkerweb_ui_logs.stdout.decode(),
        )
    else:
        print("✔️ bunkerweb.service and bunkerweb-ui.service are running ✔️")
    # Checking Reloading test
    try:
        if bunkerweb_state.stdout.decode().strip() == "active":
            test_results["Reloading test"] = "OK"
        else:
            test_results["Reloading test"] = "KO"
    except:
        test_results["Reloading test"] = "KO"

    # Removing test
    print("Removing bunkerweb...")
    subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-debian",
            "bash",
            "-c",
            "sudo apt remove -y bunkerweb",
        ]
    )

    result = subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-debian",
            "bash",
            "-c",
            "[ -d /usr/share/bunkerweb ]",
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        print("✔️ /usr/share/bunkerweb not found.")
    else:
        print("❌ /usr/share/bunkerweb found.")

    result = subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-debian",
            "bash",
            "-c",
            "[ -d /var/tmp/bunkerweb ]",
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        print("✔️ /var/tmp/bunkerweb not found.")
    else:
        print("❌ /var/tmp/bunkerweb found.")

    result = subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-debian",
            "bash",
            "-c",
            "[ -d /var/cache/bunkerweb ]",
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        print("✔️ /var/cache/bunkerweb not found.")
    else:
        print("❌ /var/cache/bunkerweb found.")

    result = subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-debian",
            "bash",
            "-c",
            "[ -f /usr/bin/bwcli ]",
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        print("✔️ /usr/bin/bwcli not found.")
    else:
        print("❌ /usr/bin/bwcli found.")
    # Checking Removing test
    try:
        if (
            pathlib.Path("/usr/share/bunkerweb").is_dir()
            or pathlib.Path("/var/tmp/bunkerweb").is_dir()
            or pathlib.Path("/var/cache/bunkerweb").is_dir()
            or pathlib.Path("/usr/bin/bwcli").is_file()
        ):
            test_results["Removing test"] = "KO"
        else:
            test_results["Removing test"] = "OK"
    except:
        test_results["Removing test"] = "KO"

    # Purging test
    print("Purging bunkerweb...")
    subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-debian",
            "bash",
            "-c",
            "sudo apt purge -y bunkerweb",
        ]
    )

    result = subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-debian",
            "bash",
            "-c",
            "[ -d /var/lib/bunkerweb ]",
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        print("✔️ /var/lib/bunkerweb not found.")
    else:
        print("❌ /var/lib/bunkerweb found.")

    result = subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-debian",
            "bash",
            "-c",
            "[ -d /etc/bunkerweb ]",
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        print("✔️ /etc/bunkerweb not found.")
    else:
        print("❌ /etc/bunkerweb found.")
    # Checking Purging test
    try:
        if (
            pathlib.Path("/var/lib/bunkerweb").is_dir()
            or pathlib.Path("/etc/bunkerweb").is_dir()
        ):
            test_results["Purging test"] = "KO"
        else:
            test_results["Purging test"] = "OK"
    except:
        test_results["Purging test"] = "KO"

    # Upgrading test
    print("Upgrading bunkerweb...")
    # Installing official package
    subprocess.run(
        [
            "docker",
            "rm",
            "-f",
            "systemd-debian",
        ]
    )
    subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            "systemd-{}".format(distro),
            "--privileged",
            "-v",
            "/sys/fs/cgroup:/sys/fs/cgroup",
            "-v",
            "deb:/data",
            "jrei/systemd-debian:11",
        ]
    )
    print("Installing bunkerweb...")
    bash_script = """
    apt update && apt install -y sudo && \
    sudo apt install -y curl gnupg2 ca-certificates lsb-release debian-archive-keyring && \
    curl https://nginx.org/keys/nginx_signing.key | gpg --dearmor \
    | sudo tee /usr/share/keyrings/nginx-archive-keyring.gpg >/dev/null && \
    echo "deb [signed-by=/usr/share/keyrings/nginx-archive-keyring.gpg] \
    http://nginx.org/packages/debian `lsb_release -cs` nginx" \
    | sudo tee /etc/apt/sources.list.d/nginx.list
    sudo apt update && sudo apt install -y nginx=1.20.2-1~bullseye
    curl -s https://packagecloud.io/install/repositories/bunkerity/bunkerweb/script.deb.sh | sudo bash && \
    sudo apt update && \
    sudo apt install -y bunkerweb=1.4.5
    """

    with tempfile.NamedTemporaryFile(mode="w") as f:
        f.write(bash_script)
        f.flush()
        subprocess.run(
            ["docker", "cp", f.name, "systemd-debian:/data/install_nginx.sh"]
        )
        result = subprocess.run(
            [
                "docker",
                "exec",
                "-it",
                "systemd-debian",
                "bash",
                "/data/install_nginx.sh",
            ]
        )

    # Checking version
    old_version = subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-debian",
            "bash",
            "-c",
            "cat /opt/bunkerweb/VERSION",
        ],
        capture_output=True,
    )
    print("Old version:", old_version.stdout.decode().strip())

    # Upgrading package
    subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-debian",
            "bash",
            "-c",
            "sudo apt remove -y nginx",
        ]
    )
    subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-debian",
            "bash",
            "-c",
            "sudo apt purge -y nginx",
        ]
    )
    subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-debian",
            "bash",
            "-c",
            "sudo apt autoremove -y",
        ]
    )
    subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-debian",
            "bash",
            "-c",
            "sudo apt install -y /data/bunkerweb.deb",
        ]
    )

    # Checking version
    new_version = subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-debian",
            "bash",
            "-c",
            "cat /usr/share/bunkerweb/VERSION",
        ],
        capture_output=True,
    )
    print("New version:", new_version.stdout.decode().strip())
    try:
        if old_version.stdout.decode().strip() != new_version.stdout.decode().strip():
            test_results["Upgrading test"] = "OK"
        else:
            test_results["Upgrading test"] = "KO"
    except:
        test_results["Upgrading test"] = "KO"

    # Print summary
    for key, value in test_results.items():
        print(f"{key}: {value}")
    if "KO" in test_results.values():
        print("❌ Some tests failed.")
        sys.exit(1)

elif distro == "fedora":
    test_results = {
        "Installation test": None,
        "Reloading test": None,
        "Removing test": None,
        "Upgrading test": None,
    }
    subprocess.run(
        [
            "sudo",
            "docker",
            "build",
            "-t",
            "fedora-image",
            "-f",
            "src/linux/Dockerfile-fedora",
            ".",
        ]
    )
    subprocess.run(
        [
            "sudo",
            "docker",
            "run",
            "-it",
            "--name",
            "fedora-container",
            "-v",
            "deb:/data",
            "fedora-image",
        ]
    )
    subprocess.run(
        [
            "sudo",
            "docker",
            "run",
            "-d",
            "--name",
            "systemd-{}".format(distro),
            "--privileged",
            "-v",
            "/sys/fs/cgroup:/sys/fs/cgroup",
            "-v",
            "deb:/data",
            "jrei/systemd-fedora",
        ]
    )

    # Installing test
    print("Installing bunkerweb...")
    bash_script = """
    dnf update -y
    dnf install -y curl gnupg2 ca-certificates redhat-lsb-core
    dnf install -y nginx-1.22.1-1.fc37
    dnf install /data/bunkerweb.rpm -y
    """

    with tempfile.NamedTemporaryFile(mode="w") as f:
        f.write(bash_script)
        f.flush()
        subprocess.run(
            ["docker", "cp", f.name, "systemd-fedora:/data/install_nginx.sh"]
        )
        result = subprocess.run(
            [
                "docker",
                "exec",
                "-it",
                "systemd-fedora",
                "bash",
                "/data/install_nginx.sh",
            ]
        )
    if result.returncode != 0:
        bunkerweb_logs = subprocess.run(
            [
                "docker",
                "exec",
                "-it",
                "systemd-fedora",
                "bash",
                "-c",
                "systemctl status bunkerweb.service",
            ],
            capture_output=True,
        )
        print("Logs from bunkerweb:", bunkerweb_logs.stdout.decode())

        bunkerweb_ui_logs = subprocess.run(
            [
                "docker",
                "exec",
                "-it",
                "systemd-fedora",
                "bash",
                "-c",
                "systemctl status bunkerweb-ui.service",
            ],
            capture_output=True,
        )
        print("Logs from bunkerweb-ui:", bunkerweb_ui_logs.stdout.decode())
        sys.exit(result.returncode)
    else:
        print("✔️ Installation successful ✔️")
    # Checking Installation test
    try:
        if result.returncode == 0:
            test_results["Installation test"] = "OK"
        else:
            test_results["Installation test"] = "KO"
            sys.exit(1)
    except:
        test_results["Installation test"] = "KO"
        sys.exit(1)

    # Reloading test
    print("Reloading bunkerweb...")
    subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-fedora",
            "bash",
            "-c",
            "echo 'HTTPS_PORT=8443' >> /etc/bunkerweb/variables.env",
        ]
    )
    subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-fedora",
            "bash",
            "-c",
            "echo 'new_value=1' >> /etc/bunkerweb/ui.env",
        ]
    )
    subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-fedora",
            "bash",
            "-c",
            "systemctl reload bunkerweb",
        ]
    )
    subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-fedora",
            "bash",
            "-c",
            "systemctl reload bunkerweb-ui",
        ]
    )

    bunkerweb_state = subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-fedora",
            "bash",
            "-c",
            "systemctl is-active bunkerweb.service",
        ],
        capture_output=True,
    )
    if bunkerweb_state.stdout.decode().strip() != "active":
        bunkerweb_logs = subprocess.run(
            [
                "docker",
                "exec",
                "-it",
                "systemd-fedora",
                "bash",
                "-c",
                "journalctl -u bunkerweb.service",
            ],
            capture_output=True,
        )
        print(
            "❌ bunkerweb.service is not running. Logs:", bunkerweb_logs.stdout.decode()
        )

    bunkerweb_ui_state = subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-fedora",
            "bash",
            "-c",
            "systemctl is-active bunkerweb-ui.service",
        ],
        capture_output=True,
    )
    if bunkerweb_ui_state.stdout.decode().strip() != "active":
        bunkerweb_ui_logs = subprocess.run(
            [
                "docker",
                "exec",
                "-it",
                "systemd-fedora",
                "bash",
                "-c",
                "journalctl -u bunkerweb-ui.service",
            ],
            capture_output=True,
        )
        print(
            "❌ bunkerweb-ui.service is not running. Logs:",
            bunkerweb_ui_logs.stdout.decode(),
        )
    else:
        print("✔️ bunkerweb.service and bunkerweb-ui.service are running ✔️")
    # Checking Reloading test
    try:
        if bunkerweb_state.stdout.decode().strip() == "active":
            test_results["Reloading test"] = "OK"
        else:
            test_results["Reloading test"] = "KO"
    except:
        test_results["Reloading test"] = "KO"

    # Removing test
    print("Removing bunkerweb...")
    subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-fedora",
            "bash",
            "-c",
            "dnf remove -y bunkerweb",
        ]
    )

    result = subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-fedora",
            "bash",
            "-c",
            "[ -d /usr/share/bunkerweb ]",
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        print("✔️ /usr/share/bunkerweb not found.")
    else:
        print("❌ /usr/share/bunkerweb found.")

    result = subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-fedora",
            "bash",
            "-c",
            "[ -d /var/tmp/bunkerweb ]",
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        print("✔️ /var/tmp/bunkerweb not found.")
    else:
        print("❌ /var/tmp/bunkerweb found.")

    result = subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-fedora",
            "bash",
            "-c",
            "[ -d /var/cache/bunkerweb ]",
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        print("✔️ /var/cache/bunkerweb not found.")
    else:
        print("❌ /var/cache/bunkerweb found.")

    result = subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-fedora",
            "bash",
            "-c",
            "[ -f /usr/bin/bwcli ]",
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        print("✔️ /usr/bin/bwcli not found.")
    else:
        print("❌ /usr/bin/bwcli found.")

    result = subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-fedora",
            "bash",
            "-c",
            "[ -d /var/lib/bunkerweb ]",
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        print("✔️ /var/lib/bunkerweb not found.")
    else:
        print("❌ /var/lib/bunkerweb found.")

    result = subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-fedora",
            "bash",
            "-c",
            "[ -d /etc/bunkerweb ]",
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        print("✔️ /etc/bunkerweb not found.")
    else:
        print("❌ /etc/bunkerweb found.")
    # Checking Removing test
    try:
        if (
            pathlib.Path("/usr/share/bunkerweb").is_dir()
            or pathlib.Path("/var/tmp/bunkerweb").is_dir()
            or pathlib.Path("/var/cache/bunkerweb").is_dir()
            or pathlib.Path("/usr/bin/bwcli").is_file()
            or pathlib.Path("/var/lib/bunkerweb").is_dir()
            or pathlib.Path("/etc/bunkerweb").is_dir()
        ):
            test_results["Removing test"] = "KO"
        else:
            test_results["Removing test"] = "OK"
    except:
        test_results["Removing test"] = "KO"

    # Upgrading test
    print("Upgrading bunkerweb...")
    # Installing official package
    subprocess.run(
        [
            "docker",
            "rm",
            "-f",
            "systemd-fedora",
        ]
    )
    subprocess.run(
        [
            "sudo",
            "docker",
            "build",
            "-t",
            "systemd-fedora",
            "-f",
            "tests/Dockerfile-fedora",
            ".",
        ]
    )
    subprocess.run(
        [
            "sudo",
            "docker",
            "run",
            "-d",
            "--name",
            "systemd-fedora",
            "--privileged",
            "-v",
            "/sys/fs/cgroup:/sys/fs/cgroup",
            "-v",
            "deb:/data",
            "systemd-fedora",
        ]
    )

    # Checking version
    old_version = subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-fedora",
            "bash",
            "-c",
            "cat /opt/bunkerweb/VERSION",
        ],
        capture_output=True,
    )
    print("Old version:", old_version.stdout.decode().strip())

    # Upgrading package
    subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-fedora",
            "bash",
            "-c",
            "sudo dnf upgrade --refresh -y",
        ]
    )
    subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-fedora",
            "bash",
            "-c",
            "sudo dnf install dnf-plugin-system-upgrade -y",
        ]
    )
    subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-fedora",
            "bash",
            "-c",
            "sudo dnf system-upgrade download --releasever=37 -y",
        ]
    )
    subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-fedora",
            "bash",
            "-c",
            "sudo dnf system-upgrade reboot",
        ]
    )

    # Checking container is running
    def start_container():
        subprocess.run(["docker", "start", "systemd-fedora"])

    def check_container_status():
        result = subprocess.run(
            ["docker", "inspect", "systemd-fedora"], stdout=subprocess.PIPE
        )
        return "running" in str(result.stdout)

    while True:
        start_container()
        time.sleep(30)
        if not check_container_status():
            continue
        break

    subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-fedora",
            "bash",
            "-c",
            "sudo dnf install -y curl gnupg2 ca-certificates redhat-lsb-core",
        ]
    )
    subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-fedora",
            "bash",
            "-c",
            "sudo dnf install nginx-1.22.1-1.fc37 -y",
        ]
    )
    subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-fedora",
            "bash",
            "-c",
            "sudo dnf install -y /data/bunkerweb.rpm",
        ]
    )
    # Checking version
    new_version = subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-fedora",
            "bash",
            "-c",
            "cat /usr/share/bunkerweb/VERSION",
        ],
        capture_output=True,
    )
    print("New version:", new_version.stdout.decode().strip())
    try:
        if old_version.stdout.decode().strip() != new_version.stdout.decode().strip():
            test_results["Upgrading test"] = "OK"
        else:
            test_results["Upgrading test"] = "KO"
    except:
        test_results["Upgrading test"] = "KO"

    # Print summary
    for key, value in test_results.items():
        print(f"{key}: {value}")
    if "KO" in test_results.values():
        sys.exit(1)

elif distro == "rhel":
    test_results = {
        "Installation test": None,
        "Reloading test": None,
        "Removing test": None,
        "Upgrading test": None,
    }
    subprocess.run(
        [
            "sudo",
            "docker",
            "build",
            "-t",
            "rhel-image",
            "-f",
            "src/linux/Dockerfile-rhel",
            ".",
        ]
    )
    subprocess.run(
        [
            "sudo",
            "docker",
            "run",
            "-it",
            "--name",
            "rhel-container",
            "-v",
            "deb:/data",
            "rhel-image",
        ]
    )
    subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            "systemd-rhel",
            "-v",
            "deb:/data",
            "--privileged",
            "-v",
            "/sys/fs/cgroup:/sys/fs/cgroup",
            "registry.access.redhat.com/ubi8/ubi-init:8.7-10",
        ]
    )

    # Installing test
    print("Installing bunkerweb...")
    bash_script = """
    dnf install yum-utils wget sudo -y
    wget https://nginx.org/packages/rhel/8/x86_64/RPMS/nginx-1.22.1-1.el8.ngx.x86_64.rpm
    dnf install nginx-1.22.1-1.el8.ngx.x86_64.rpm -y
    dnf install /data/bunkerweb.rpm -y
    """

    with tempfile.NamedTemporaryFile(mode="w") as f:
        f.write(bash_script)
        f.flush()
        subprocess.run(["docker", "cp", f.name, "systemd-rhel:/data/install_nginx.sh"])
        result = subprocess.run(
            [
                "docker",
                "exec",
                "-it",
                "systemd-rhel",
                "bash",
                "/data/install_nginx.sh",
            ]
        )
    if result.returncode != 0:
        bunkerweb_logs = subprocess.run(
            [
                "docker",
                "exec",
                "-it",
                "systemd-rhel",
                "bash",
                "-c",
                "systemctl status bunkerweb.service",
            ],
            capture_output=True,
        )
        print("Logs from bunkerweb:", bunkerweb_logs.stdout.decode())

        bunkerweb_ui_logs = subprocess.run(
            [
                "docker",
                "exec",
                "-it",
                "systemd-rhel",
                "bash",
                "-c",
                "systemctl status bunkerweb-ui.service",
            ],
            capture_output=True,
        )
        print("Logs from bunkerweb-ui:", bunkerweb_ui_logs.stdout.decode())
        sys.exit(result.returncode)
        exit(result.returncode)
    else:
        print("✔️ Installation successful ✔️")
    # Checking Installation test
    try:
        if result.returncode == 0:
            test_results["Installation test"] = "OK"
        else:
            test_results["Installation test"] = "KO"
            sys.exit(1)
    except:
        test_results["Installation test"] = "KO"
        sys.exit(1)

    # Reloading test
    print("Reloading bunkerweb...")
    subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-rhel",
            "bash",
            "-c",
            "echo 'HTTPS_PORT=8443' >> /etc/bunkerweb/variables.env",
        ]
    )
    subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-rhel",
            "bash",
            "-c",
            "echo 'new_value=1' >> /etc/bunkerweb/ui.env",
        ]
    )
    subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-rhel",
            "bash",
            "-c",
            "systemctl reload bunkerweb",
        ]
    )
    subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-rhel",
            "bash",
            "-c",
            "systemctl reload bunkerweb-ui",
        ]
    )

    bunkerweb_state = subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-rhel",
            "bash",
            "-c",
            "systemctl is-active bunkerweb.service",
        ],
        capture_output=True,
    )
    if bunkerweb_state.stdout.decode().strip() != "active":
        bunkerweb_logs = subprocess.run(
            [
                "docker",
                "exec",
                "-it",
                "systemd-rhel",
                "bash",
                "-c",
                "journalctl -u bunkerweb.service",
            ],
            capture_output=True,
        )
        print(
            "❌ bunkerweb.service is not running. Logs:", bunkerweb_logs.stdout.decode()
        )

    bunkerweb_ui_state = subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-rhel",
            "bash",
            "-c",
            "systemctl is-active bunkerweb-ui.service",
        ],
        capture_output=True,
    )
    if bunkerweb_ui_state.stdout.decode().strip() != "active":
        bunkerweb_ui_logs = subprocess.run(
            [
                "docker",
                "exec",
                "-it",
                "systemd-rhel",
                "bash",
                "-c",
                "journalctl -u bunkerweb-ui.service",
            ],
            capture_output=True,
        )
        print(
            "❌ bunkerweb-ui.service is not running. Logs:",
            bunkerweb_ui_logs.stdout.decode(),
        )
    else:
        print("✔️ bunkerweb.service and bunkerweb-ui.service are running ✔️")
    # Checking Reloading test
    try:
        if bunkerweb_state.stdout.decode().strip() == "active":
            test_results["Reloading test"] = "OK"
        else:
            test_results["Reloading test"] = "KO"
    except:
        test_results["Reloading test"] = "KO"

    # Removing test
    print("Removing bunkerweb...")
    subprocess.run(
        [
            "sudo",
            "docker",
            "exec",
            "-it",
            "systemd-rhel",
            "bash",
            "-c",
            "dnf remove -y bunkerweb",
        ]
    )

    result = subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-rhel",
            "bash",
            "-c",
            "[ -d /usr/share/bunkerweb ]",
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        print("✔️ /usr/share/bunkerweb not found.")
    else:
        print("❌ /usr/share/bunkerweb found.")

    result = subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-rhel",
            "bash",
            "-c",
            "[ -d /var/tmp/bunkerweb ]",
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        print("✔️ /var/tmp/bunkerweb not found.")
    else:
        print("❌ /var/tmp/bunkerweb found.")

    result = subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-rhel",
            "bash",
            "-c",
            "[ -d /var/cache/bunkerweb ]",
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        print("✔️ /var/cache/bunkerweb not found.")
    else:
        print("❌ /var/cache/bunkerweb found.")

    result = subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-rhel",
            "bash",
            "-c",
            "[ -f /usr/bin/bwcli ]",
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        print("✔️ /usr/bin/bwcli not found.")
    else:
        print("❌ /usr/bin/bwcli found.")

    result = subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-rhel",
            "bash",
            "-c",
            "[ -d /var/lib/bunkerweb ]",
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        print("✔️ /var/lib/bunkerweb not found.")
    else:
        print("❌ /var/lib/bunkerweb found.")

    result = subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-rhel",
            "bash",
            "-c",
            "[ -d /etc/bunkerweb ]",
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        print("✔️ /etc/bunkerweb not found.")
    else:
        print("❌ /etc/bunkerweb found.")
    # Checking Removing test
    try:
        if (
            pathlib.Path("/usr/share/bunkerweb").is_dir()
            or pathlib.Path("/var/tmp/bunkerweb").is_dir()
            or pathlib.Path("/var/cache/bunkerweb").is_dir()
            or pathlib.Path("/usr/bin/bwcli").is_file()
            or pathlib.Path("/var/lib/bunkerweb").is_dir()
            or pathlib.Path("/etc/bunkerweb").is_dir()
        ):
            test_results["Removing test"] = "KO"
        else:
            test_results["Removing test"] = "OK"
    except:
        test_results["Removing test"] = "KO"

    ############################################################################################################
    # Upgrading test is disabled because RHEL is the new Integration test                                      #
    ############################################################################################################
    # Upgrading test
    # print("Upgrading bunkerweb...")
    # subprocess.run(
    #     [
    #         "docker",
    #         "rm",
    #         "-f",
    #         "systemd-rhel",
    #     ]
    # )
    # subprocess.run(
    #     [
    #         "docker",
    #         "run",
    #         "-d",
    #         "--name",
    #         "systemd-rhel",
    #         "-v",
    #         "deb:/data",
    #         "--privileged",
    #         "-v",
    #         "/sys/fs/cgroup:/sys/fs/cgroup",
    #         "registry.access.redhat.com/ubi8/ubi-init:8.7-10",
    #     ]
    # )
    # subprocess.run(
    #     [
    #         "docker",
    #         "exec",
    #         "-it",
    #         "systemd-rhel",
    #         "bash",
    #         "-c",
    #         "dnf install -y curl sudo",
    #     ]
    # )
    # subprocess.run(
    #     [
    #         "docker",
    #         "exec",
    #         "-it",
    #         "systemd-rhel",
    #         "bash",
    #         "-c",
    #         "curl -s https://packagecloud.io/install/repositories/bunkerity/bunkerweb/script.rpm.sh | sudo bash",
    #     ]
    # )
    # subprocess.run(
    #     [
    #         "docker",
    #         "exec",
    #         "-it",
    #         "systemd-rhel",
    #         "bash",
    #         "-c",
    #         "sudo dnf check-update",
    #     ]
    # )
    # subprocess.run(
    #     [
    #         "docker",
    #         "exec",
    #         "-it",
    #         "systemd-rhel",
    #         "bash",
    #         "-c",
    #         "sudo dnf install -y bunkerweb-1.4.5",
    #     ]
    # )

    # # Checking version
    # old_version = subprocess.run(
    #     [
    #         "docker",
    #         "exec",
    #         "-it",
    #         "systemd-rhel",
    #         "bash",
    #         "-c",
    #         "cat /opt/bunkerweb/VERSION",
    #     ],
    #     capture_output=True,
    # )
    # print("Old version:", old_version.stdout.decode().strip())

    # # Upgrading package
    # subprocess.run(
    #     [
    #         "docker",
    #         "exec",
    #         "-it",
    #         "systemd-rhel",
    #         "bash",
    #         "-c",
    #         "sudo dnf remove -y nginx",
    #     ]
    # )
    # subprocess.run(
    #     [
    #         "docker",
    #         "exec",
    #         "-it",
    #         "systemd-rhel",
    #         "bash",
    #         "-c",
    #         "sudo dnf autoremove -y",
    #     ]
    # )
    # subprocess.run(
    #     [
    #         "docker",
    #         "exec",
    #         "-it",
    #         "systemd-rhel",
    #         "bash",
    #         "-c",
    #         "sudo dnf install -y /data/bunkerweb.rpm",
    #     ]
    # )

    # # Checking version
    # new_version = subprocess.run(
    #     [
    #         "docker",
    #         "exec",
    #         "-it",
    #         "systemd-rhel",
    #         "bash",
    #         "-c",
    #         "cat /usr/share/bunkerweb/VERSION",
    #     ],
    #     capture_output=True,
    # )
    # print("New version:", new_version.stdout.decode().strip())
    # try:
    #     if old_version.stdout.decode().strip() != new_version.stdout.decode().strip():
    #         test_results["Upgrading test"] = "OK"
    #     else:
    #         test_results["Upgrading test"] = "KO"
    # except:
    #     test_results["Upgrading test"] = "KO"

    # Print summary
    for key, value in test_results.items():
        print(f"{key}: {value}")
    if "KO" in test_results.values():
        sys.exit(1)

elif distro == "centos":
    test_results = {
        "Installation test": None,
        "Reloading test": None,
        "Removing test": None,
        "Upgrading test": None,
    }
    subprocess.run(
        [
            "docker",
            "build",
            "-t",
            "centos-image",
            "-f",
            "src/linux/Dockerfile-centos",
            ".",
        ]
    )
    # Building local systemd image
    subprocess.run(
        ["docker", "build", "-t", "centos", "-f", "tests/Dockerfile-centos", "."]
    )
    subprocess.run(
        [
            "docker",
            "run",
            "-it",
            "--name",
            "centos-container",
            "-v",
            "deb:/data",
            "centos-image",
        ]
    )
    subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            "systemd-{}".format(distro),
            "--privileged",
            "-v",
            "/sys/fs/cgroup:/sys/fs/cgroup",
            "-v",
            "deb:/data",
            "centos",
        ]
    )

    # Installing test
    print("Installing bunkerweb...")
    bash_script = """
    dnf install yum-utils epel-release redhat-lsb-core -y
    dnf install -y nginx-1.22.1
    dnf install /data/bunkerweb.rpm -y
    """

    with tempfile.NamedTemporaryFile(mode="w") as f:
        f.write(bash_script)
        f.flush()
        subprocess.run(
            [
                "docker",
                "cp",
                "src/linux/nginx.repo",
                "systemd-centos:/etc/yum.repos.d/nginx.repo",
            ]
        )
        subprocess.run(
            ["docker", "cp", f.name, "systemd-centos:/data/install_nginx.sh"]
        )
        result = subprocess.run(
            [
                "docker",
                "exec",
                "-it",
                "systemd-centos",
                "bash",
                "/data/install_nginx.sh",
            ]
        )
    if result.returncode != 0:
        bunkerweb_logs = subprocess.run(
            [
                "docker",
                "exec",
                "-it",
                "systemd-centos",
                "bash",
                "-c",
                "systemctl status bunkerweb.service",
            ],
            capture_output=True,
        )
        print("Logs from bunkerweb:", bunkerweb_logs.stdout.decode())

        bunkerweb_ui_logs = subprocess.run(
            [
                "docker",
                "exec",
                "-it",
                "systemd-centos",
                "bash",
                "-c",
                "systemctl status bunkerweb-ui.service",
            ],
            capture_output=True,
        )
        print("Logs from bunkerweb-ui:", bunkerweb_ui_logs.stdout.decode())
        sys.exit(result.returncode)
        exit(result.returncode)
    else:
        print("✔️ Installation successful ✔️")
    # Checking Installation test
    try:
        if result.returncode == 0:
            test_results["Installation test"] = "OK"
        else:
            test_results["Installation test"] = "KO"
            sys.exit(1)
    except:
        test_results["Installation test"] = "KO"
        sys.exit(1)

    # Reloading test
    print("Reloading bunkerweb...")
    subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-centos",
            "bash",
            "-c",
            "echo 'HTTPS_PORT=8443' >> /etc/bunkerweb/variables.env",
        ]
    )
    subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-centos",
            "bash",
            "-c",
            "echo 'new_value=1' >> /etc/bunkerweb/ui.env",
        ]
    )
    subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-centos",
            "bash",
            "-c",
            "systemctl reload bunkerweb",
        ]
    )
    subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-centos",
            "bash",
            "-c",
            "systemctl reload bunkerweb-ui",
        ]
    )

    bunkerweb_state = subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-centos",
            "bash",
            "-c",
            "systemctl is-active bunkerweb.service",
        ],
        capture_output=True,
    )
    if bunkerweb_state.stdout.decode().strip() != "active":
        bunkerweb_logs = subprocess.run(
            [
                "docker",
                "exec",
                "-it",
                "systemd-centos",
                "bash",
                "-c",
                "journalctl -u bunkerweb.service",
            ],
            capture_output=True,
        )
        print(
            "❌ bunkerweb.service is not running. Logs:", bunkerweb_logs.stdout.decode()
        )

    bunkerweb_ui_state = subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-centos",
            "bash",
            "-c",
            "systemctl is-active bunkerweb-ui.service",
        ],
        capture_output=True,
    )
    if bunkerweb_ui_state.stdout.decode().strip() != "active":
        bunkerweb_ui_logs = subprocess.run(
            [
                "docker",
                "exec",
                "-it",
                "systemd-centos",
                "bash",
                "-c",
                "journalctl -u bunkerweb-ui.service",
            ],
            capture_output=True,
        )
        print(
            "❌ bunkerweb-ui.service is not running. Logs:",
            bunkerweb_ui_logs.stdout.decode(),
        )
    else:
        print("✔️ bunkerweb.service and bunkerweb-ui.service are running ✔️")
    # Checking Reloading test
    try:
        if bunkerweb_state.stdout.decode().strip() == "active":
            test_results["Reloading test"] = "OK"
        else:
            test_results["Reloading test"] = "KO"
    except:
        test_results["Reloading test"] = "KO"

    # Removing test
    print("Removing bunkerweb...")
    subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-centos",
            "bash",
            "-c",
            "dnf remove -y bunkerweb",
        ]
    )

    result = subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-centos",
            "bash",
            "-c",
            "[ -d /usr/share/bunkerweb ]",
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        print("✔️ /usr/share/bunkerweb not found.")
    else:
        print("❌ /usr/share/bunkerweb found.")

    result = subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-centos",
            "bash",
            "-c",
            "[ -d /var/tmp/bunkerweb ]",
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        print("✔️ /var/tmp/bunkerweb not found.")
    else:
        print("❌ /var/tmp/bunkerweb found.")

    result = subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-centos",
            "bash",
            "-c",
            "[ -d /var/cache/bunkerweb ]",
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        print("✔️ /var/cache/bunkerweb not found.")
    else:
        print("❌ /var/cache/bunkerweb found.")

    result = subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-centos",
            "bash",
            "-c",
            "[ -f /usr/bin/bwcli ]",
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        print("✔️ /usr/bin/bwcli not found.")
    else:
        print("❌ /usr/bin/bwcli found.")

    result = subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-centos",
            "bash",
            "-c",
            "[ -d /var/lib/bunkerweb ]",
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        print("✔️ /var/lib/bunkerweb not found.")
    else:
        print("❌ /var/lib/bunkerweb found.")

    result = subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-centos",
            "bash",
            "-c",
            "[ -d /etc/bunkerweb ]",
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        print("✔️ /etc/bunkerweb not found.")
    else:
        print("❌ /etc/bunkerweb found.")
    # Checking Removing test
    try:
        if (
            pathlib.Path("/usr/share/bunkerweb").is_dir()
            or pathlib.Path("/var/tmp/bunkerweb").is_dir()
            or pathlib.Path("/var/cache/bunkerweb").is_dir()
            or pathlib.Path("/usr/bin/bwcli").is_file()
            or pathlib.Path("/var/lib/bunkerweb").is_dir()
            or pathlib.Path("/etc/bunkerweb").is_dir()
        ):
            test_results["Removing test"] = "KO"
        else:
            test_results["Removing test"] = "OK"
    except:
        test_results["Removing test"] = "KO"

    # Upgrading test
    print("Upgrading bunkerweb...")
    subprocess.run(
        [
            "docker",
            "rm",
            "-f",
            "systemd-centos",
        ]
    )
    subprocess.run(
        [
            "sudo",
            "docker",
            "build",
            "-t",
            "systemd-centos",
            "-f",
            "tests/Dockerfile-centos",
            ".",
        ]
    )
    subprocess.run(
        [
            "sudo",
            "docker",
            "run",
            "-d",
            "--name",
            "systemd-centos",
            "--privileged",
            "-v",
            "/sys/fs/cgroup:/sys/fs/cgroup",
            "-v",
            "deb:/data",
            "systemd-centos",
        ]
    )
    subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-centos",
            "bash",
            "-c",
            "curl -s https://packagecloud.io/install/repositories/bunkerity/bunkerweb/script.rpm.sh | sudo bash",
        ]
    )
    subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-centos",
            "bash",
            "-c",
            "sudo dnf check-update",
        ]
    )
    subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-centos",
            "bash",
            "-c",
            "sudo dnf install -y bunkerweb-1.4.5",
        ]
    )

    # Checking version
    old_version = subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-centos",
            "bash",
            "-c",
            "cat /opt/bunkerweb/VERSION",
        ],
        capture_output=True,
    )
    print("Old version:", old_version.stdout.decode().strip())

    # Upgrading package
    subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-centos",
            "bash",
            "-c",
            "sudo dnf remove -y nginx",
        ]
    )
    subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-centos",
            "bash",
            "-c",
            "sudo dnf autoremove -y",
        ]
    )
    subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-centos",
            "bash",
            "-c",
            "sudo dnf install -y /data/bunkerweb.rpm",
        ]
    )

    # Checking version
    new_version = subprocess.run(
        [
            "docker",
            "exec",
            "-it",
            "systemd-centos",
            "bash",
            "-c",
            "cat /usr/share/bunkerweb/VERSION",
        ],
        capture_output=True,
    )
    print("New version:", new_version.stdout.decode().strip())
    try:
        if old_version.stdout.decode().strip() != new_version.stdout.decode().strip():
            test_results["Upgrading test"] = "OK"
        else:
            test_results["Upgrading test"] = "KO"
    except:
        test_results["Upgrading test"] = "KO"

    # Print summary
    for key, value in test_results.items():
        print(f"{key}: {value}")
    if "KO" in test_results.values():
        sys.exit(1)
else:
    print("Invalid argument. Please pass one of: ubuntu, debian, fedora, rhel, centos")
    sys.exit(1)
