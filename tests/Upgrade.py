import subprocess
import sys
import tempfile
import os

distro = sys.argv[1]
if distro == "ubuntu":
    test_results = {"Installation test": None, "Reloading test": None, "Removing test": None, "Purging test": None, "Upgrading test": None}
    subprocess.run(["docker", "build", "-t", "ubuntu-image", "-f", "src/linux/Dockerfile-ubuntu", "."])
    subprocess.run(["docker", "run", "-it", "--name", "ubuntu-container", "-v", "deb:/data", "ubuntu-image"])
    subprocess.run(["docker", "run", "-d", "--name", "systemd-{}".format(distro), "--privileged", "-v", "/sys/fs/cgroup:/sys/fs/cgroup", "-v", "deb:/data", "jrei/systemd-ubuntu:22.04"])

    # Installing test
    print("Installing bunkerweb...")
    bash_script = """
    apt update && \
    apt install -y curl gnupg2 ca-certificates lsb-release ubuntu-keyring && \
    curl https://nginx.org/keys/nginx_signing.key | gpg --dearmor \
    | tee /usr/share/keyrings/nginx-archive-keyring.gpg >/dev/null && \
    echo "deb [signed-by=/usr/share/keyrings/nginx-archive-keyring.gpg] \
    http://nginx.org/packages/ubuntu `lsb_release -cs` nginx" \
    | tee /etc/apt/sources.list.d/nginx.list
    apt update && \
    apt install -y nginx=1.22.1-1~jammy
    apt install /data/bunkerweb.deb -y
    """

    with tempfile.NamedTemporaryFile(mode='w') as f:
        f.write(bash_script)
        f.flush()
        subprocess.run(["docker", "cp", f.name, "systemd-ubuntu:/tmp/install_nginx.sh"])
        result = subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "/tmp/install_nginx.sh"])
    if result.returncode != 0:
        bunkerweb_logs = subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "systemctl status bunkerweb.service"], capture_output=True)
        print("Logs from bunkerweb:", bunkerweb_logs.stdout.decode())

        bunkerweb_ui_logs = subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "systemctl status bunkerweb-ui.service"], capture_output=True)
        print("Logs from bunkerweb-ui:", bunkerweb_ui_logs.stdout.decode())
        sys.exit(result.returncode)
        exit(result.returncode)
    else:
        print("✔️ Installation successful ✔️")
    #Checking Installation test
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
    subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "echo 'HTTPS_PORT=8443' >> /etc/bunkerweb/variables.env"])
    subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "echo 'new_value=1' >> /etc/bunkerweb/ui.env"])
    subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "systemctl reload bunkerweb"])
    subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "systemctl reload bunkerweb-ui"])

    bunkerweb_state = subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "systemctl is-active bunkerweb.service"], capture_output=True)
    if bunkerweb_state.stdout.decode().strip() != "active":
        bunkerweb_logs = subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "journalctl -u bunkerweb.service"], capture_output=True)
        print("❌ bunkerweb.service is not running. Logs:", bunkerweb_logs.stdout.decode())

    bunkerweb_ui_state = subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "systemctl is-active bunkerweb-ui.service"], capture_output=True)
    if bunkerweb_ui_state.stdout.decode().strip() != "active":
        bunkerweb_ui_logs = subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "journalctl -u bunkerweb-ui.service"], capture_output=True)
        print("❌ bunkerweb-ui.service is not running. Logs:", bunkerweb_ui_logs.stdout.decode())
    #Checking Reloading test
    try:
        if bunkerweb_state.stdout.decode().strip() == "active":
            test_results["Reloading test"] = "OK"
        else:
            test_results["Reloading test"] = "KO"
    except:
        test_results["Reloading test"] = "KO"
    
    # Removing test
    print("Removing bunkerweb...")
    subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "apt remove -y bunkerweb"])

    result = subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "[ -d /usr/share/bunkerweb ]"], capture_output=True)
    if result.returncode != 0:
        print("✔️ /usr/share/bunkerweb not found.")
    else:
        print("❌ /usr/share/bunkerweb found.")

    result = subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "[ -d /var/tmp/bunkerweb ]"], capture_output=True)
    if result.returncode != 0:
        print("✔️ /var/tmp/bunkerweb not found.")
    else:
        print("❌ /var/tmp/bunkerweb found.")

    result = subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "[ -d /var/cache/bunkerweb ]"], capture_output=True)
    if result.returncode != 0:
        print("✔️ /var/cache/bunkerweb not found.")
    else:
        print("❌ /var/cache/bunkerweb found.")

    result = subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "[ -f /usr/bin/bwcli ]"], capture_output=True)
    if result.returncode != 0:
        print("✔️ /usr/bin/bwcli not found.")
    else:
        print("❌ /usr/bin/bwcli found.")
    #Checking Removing test
    try:
        if not os.path.isdir("/usr/share/bunkerweb") and not os.path.isdir("/var/tmp/bunkerweb") and not os.path.isdir("/var/cache/bunkerweb") and not os.path.isfile("/usr/bin/bwcli"):
            test_results["Removing test"] = "OK"
        else:
            test_results["Removing test"] = "KO"
            sys.exit(1)
    except:
        test_results["Removing test"] = "KO"

    # Purging test
    print("Purging bunkerweb...")
    subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "apt purge -y bunkerweb"])

    result = subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "[ -d /var/lib/bunkerweb ]"], capture_output=True)
    if result.returncode != 0:
        print("✔️ /var/lib/bunkerweb not found.")
    else:
        print("❌ /var/lib/bunkerweb found.")

    result = subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "[ -d /etc/bunkerweb ]"], capture_output=True)
    if result.returncode != 0:
        print("✔️ /etc/bunkerweb not found.")
    else:
        print("❌ /etc/bunkerweb found.")
    #Checking Purging test
    try:
        if not os.path.isdir("/var/lib/bunkerweb") and not os.path.isdir("/etc/bunkerweb"):
            test_results["Purging test"] = "OK"
        else:
            test_results["Purging test"] = "KO"
    except:
        test_results["Purging test"] = "KO"


    # Upgrading test
    print("Upgrading bunkerweb...")
    # Installing official package
    subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "sudo apt remove -y nginx"])
    subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "sudo apt-get install -y -o Dpkg::Options::=\"--force-confdef\" -o Dpkg::Options::=\"--force-confold\" nginx=1.20.2-1~jammy"])
    subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "curl -s https://packagecloud.io/install/repositories/bunkerity/bunkerweb/script.deb.sh | sudo bash"])
    subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "sudo apt update"])
    subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "sudo apt install -y bunkerweb=1.4.5"])

    # Checking version
    old_version = subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "cat /opt/bunkerweb/VERSION"], capture_output=True)
    print("Old version:", old_version.stdout.decode().strip())

    # Upgrading package
    subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "sudo apt install -y /data/bunkerweb.deb"])

    # Checking version
    new_version = subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "cat /usr/share/bunkerweb/VERSION"], capture_output=True)
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
        print(f'{key}: {value}')
    if "KO" in test_results.values():
        print("❌ Some tests failed.")
        sys.exit(1)

elif distro == "debian":
    test_results = {"Installation test": None, "Reloading test": None, "Removing test": None, "Purging test": None, "Upgrading test": None}
    subprocess.run(["docker", "build", "-t", "debian-image", "-f", "src/linux/Dockerfile-debian", "."])
    subprocess.run(["docker", "run", "-it", "--name", "debian-container", "-v", "deb:/data", "debian-image"])
    subprocess.run(["docker", "run", "-d", "--name", "systemd-{}".format(distro), "--privileged", "-v", "/sys/fs/cgroup:/sys/fs/cgroup", "-v", "deb:/data", "jrei/systemd-debian:11"])

    # Installing test
    print("Installing bunkerweb...")
    bash_script = """
    apt update && \
    apt-get install gnupg2 ca-certificates lsb-release wget curl -y && \
    echo "deb https://nginx.org/packages/debian/ bullseye nginx" > /etc/apt/sources.list.d/nginx.list && \
    echo "deb-src https://nginx.org/packages/debian/ bullseye nginx" >> /etc/apt/sources.list.d/nginx.list && \
    apt-key adv --keyserver keyserver.ubuntu.com --recv-keys ABF5BD827BD9BF62 && \
    apt-get update && \
    apt-get install -y --no-install-recommends nginx=${NGINX_VERSION}-1~bullseye
    apt install /data/bunkerweb.deb -y
    """

    with tempfile.NamedTemporaryFile(mode='w') as f:
        f.write(bash_script)
        f.flush()
        subprocess.run(["docker", "cp", f.name, "systemd-debian:/tmp/install_nginx.sh"])
        result = subprocess.run(["docker", "exec", "-it", "systemd-debian", "bash", "/tmp/install_nginx.sh"])
    if result.returncode != 0:
        bunkerweb_logs = subprocess.run(["docker", "exec", "-it", "systemd-debian", "bash", "-c", "systemctl status bunkerweb.service"], capture_output=True)
        print("Logs from bunkerweb:", bunkerweb_logs.stdout.decode())

        bunkerweb_ui_logs = subprocess.run(["docker", "exec", "-it", "systemd-debian", "bash", "-c", "systemctl status bunkerweb-ui.service"], capture_output=True)
        print("Logs from bunkerweb-ui:", bunkerweb_ui_logs.stdout.decode())
        sys.exit(result.returncode)
        exit(result.returncode)
    else:
        print("✔️ Installation successful ✔️")
    #Checking Installation test
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
    subprocess.run(["docker", "exec", "-it", "systemd-debian", "bash", "-c", "echo 'HTTPS_PORT=8443' >> /etc/bunkerweb/variables.env"])
    subprocess.run(["docker", "exec", "-it", "systemd-debian", "bash", "-c", "echo 'new_value=1' >> /etc/bunkerweb/ui.env"])
    subprocess.run(["docker", "exec", "-it", "systemd-debian", "bash", "-c", "systemctl reload bunkerweb"])
    subprocess.run(["docker", "exec", "-it", "systemd-debian", "bash", "-c", "systemctl reload bunkerweb-ui"])

    bunkerweb_state = subprocess.run(["docker", "exec", "-it", "systemd-debian", "bash", "-c", "systemctl is-active bunkerweb.service"], capture_output=True)
    if bunkerweb_state.stdout.decode().strip() != "active":
        bunkerweb_logs = subprocess.run(["docker", "exec", "-it", "systemd-debian", "bash", "-c", "journalctl -u bunkerweb.service"], capture_output=True)
        print("❌ bunkerweb.service is not running. Logs:", bunkerweb_logs.stdout.decode())

    bunkerweb_ui_state = subprocess.run(["docker", "exec", "-it", "systemd-debian", "bash", "-c", "systemctl is-active bunkerweb-ui.service"], capture_output=True)
    if bunkerweb_ui_state.stdout.decode().strip() != "active":
        bunkerweb_ui_logs = subprocess.run(["docker", "exec", "-it", "systemd-debian", "bash", "-c", "journalctl -u bunkerweb-ui.service"], capture_output=True)
        print("❌ bunkerweb-ui.service is not running. Logs:", bunkerweb_ui_logs.stdout.decode())
    #Checking Reloading test
    try:
        if bunkerweb_state.stdout.decode().strip() == "active":
            test_results["Reloading test"] = "OK"
        else:
            test_results["Reloading test"] = "KO"
    except:
        test_results["Reloading test"] = "KO"
    
    # Removing test
    print("Removing bunkerweb...")
    subprocess.run(["docker", "exec", "-it", "systemd-debian", "bash", "-c", "apt remove -y bunkerweb"])

    result = subprocess.run(["docker", "exec", "-it", "systemd-debian", "bash", "-c", "[ -d /usr/share/bunkerweb ]"], capture_output=True)
    if result.returncode != 0:
        print("✔️ /usr/share/bunkerweb not found.")
    else:
        print("❌ /usr/share/bunkerweb found.")

    result = subprocess.run(["docker", "exec", "-it", "systemd-debian", "bash", "-c", "[ -d /var/tmp/bunkerweb ]"], capture_output=True)
    if result.returncode != 0:
        print("✔️ /var/tmp/bunkerweb not found.")
    else:
        print("❌ /var/tmp/bunkerweb found.")

    result = subprocess.run(["docker", "exec", "-it", "systemd-debian", "bash", "-c", "[ -d /var/cache/bunkerweb ]"], capture_output=True)
    if result.returncode != 0:
        print("✔️ /var/cache/bunkerweb not found.")
    else:
        print("❌ /var/cache/bunkerweb found.")

    result = subprocess.run(["docker", "exec", "-it", "systemd-debian", "bash", "-c", "[ -f /usr/bin/bwcli ]"], capture_output=True)
    if result.returncode != 0:
        print("✔️ /usr/bin/bwcli not found.")
    else:
        print("❌ /usr/bin/bwcli found.")
    #Checking Removing test
    try:
        if not os.path.isdir("/usr/share/bunkerweb") and not os.path.isdir("/var/tmp/bunkerweb") and not os.path.isdir("/var/cache/bunkerweb") and not os.path.isfile("/usr/bin/bwcli"):
            test_results["Removing test"] = "OK"
        else:
            test_results["Removing test"] = "KO"
    except:
        test_results["Removing test"] = "KO"

    # Purging test
    print("Purging bunkerweb...")
    subprocess.run(["docker", "exec", "-it", "systemd-debian", "bash", "-c", "apt purge -y bunkerweb"])

    result = subprocess.run(["docker", "exec", "-it", "systemd-debian", "bash", "-c", "[ -d /var/lib/bunkerweb ]"], capture_output=True)
    if result.returncode != 0:
        print("✔️ /var/lib/bunkerweb not found.")
    else:
        print("❌ /var/lib/bunkerweb found.")

    result = subprocess.run(["docker", "exec", "-it", "systemd-debian", "bash", "-c", "[ -d /etc/bunkerweb ]"], capture_output=True)
    if result.returncode != 0:
        print("✔️ /etc/bunkerweb not found.")
    else:
        print("❌ /etc/bunkerweb found.")
    #Checking Purging test
    try:
        if not os.path.isdir("/var/lib/bunkerweb") and not os.path.isdir("/etc/bunkerweb"):
            test_results["Purging test"] = "OK"
        else:
            test_results["Purging test"] = "KO"
    except:
        test_results["Purging test"] = "KO"

    # Upgrading test
    print("Upgrading bunkerweb...")
    # Installing official package
    subprocess.run(["docker", "exec", "-it", "systemd-debian", "bash", "-c", "sudo apt remove -y nginx"])
    subprocess.run(["docker", "exec", "-it", "systemd-debian", "bash", "-c", "sudo apt-get install -y -o Dpkg::Options::=\"--force-confdef\" -o Dpkg::Options::=\"--force-confold\" nginx=1.20.2-1~bullseye"])
    subprocess.run(["docker", "exec", "-it", "systemd-debian", "bash", "-c", "curl -s https://packagecloud.io/install/repositories/bunkerity/bunkerweb/script.deb.sh | sudo bash"])
    subprocess.run(["docker", "exec", "-it", "systemd-debian", "bash", "-c", "sudo apt update"])
    subprocess.run(["docker", "exec", "-it", "systemd-debian", "bash", "-c", "sudo apt install -y bunkerweb=1.4.5"])

    # Checking version
    old_version = subprocess.run(["docker", "exec", "-it", "systemd-debian", "bash", "-c", "cat /opt/bunkerweb/VERSION"], capture_output=True)
    print("Old version:", old_version.stdout.decode().strip())

    # Upgrading package
    subprocess.run(["docker", "exec", "-it", "systemd-debian", "bash", "-c", "sudo apt install -y /data/bunkerweb.deb"])

    # Checking version
    new_version = subprocess.run(["docker", "exec", "-it", "systemd-debian", "bash", "-c", "cat /usr/share/bunkerweb/VERSION"], capture_output=True)
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
        print(f'{key}: {value}')
    if "KO" in test_results.values():
        print("❌ Some tests failed.")
        sys.exit(1)

elif distro == "fedora":
    subprocess.run(["docker", "build", "-t", "fedora-image", "-f", "../src/linux/Dockerfile-fedora", "."])
    subprocess.run(["docker", "run", "-it", "--name", "fedora-container", "-v", "deb:/data", "fedora-image"])
    subprocess.run(["docker", "run", "-d", "--name", "systemd-{}".format(distro), "--privileged", "-v", "/sys/fs/cgroup:/sys/fs/cgroup", "-v", "deb:/data", "jrei/systemd-fedora"])

    # Installing test
    print("Installing bunkerweb...")
    bash_script = """
    dnf install -y nginx-1.20.2
    apt install /data/bunkerweb.deb -y
    """

    with tempfile.NamedTemporaryFile(mode='w') as f:
        f.write(bash_script)
        f.flush()
        subprocess.run(["docker", "cp", f.name, "systemd-ubuntu:/tmp/install_nginx.sh"])
        result = subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "/tmp/install_nginx.sh"])
    if result.returncode != 0:
        bunkerweb_logs = subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "systemctl status bunkerweb.service"], capture_output=True)
        print("Logs from bunkerweb:", bunkerweb_logs.stdout.decode())

        bunkerweb_ui_logs = subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "systemctl status bunkerweb-ui.service"], capture_output=True)
        print("Logs from bunkerweb-ui:", bunkerweb_ui_logs.stdout.decode())
        sys.exit(result.returncode)
        exit(result.returncode)
    else:
        print("✔️ Installation successful ✔️")
    #Checking Installation test
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
    subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "echo 'HTTPS_PORT=8443' >> /etc/bunkerweb/variables.env"])
    subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "echo 'new_value=1' >> /etc/bunkerweb/ui.env"])
    subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "systemctl reload bunkerweb"])
    subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "systemctl reload bunkerweb-ui"])

    bunkerweb_state = subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "systemctl is-active bunkerweb.service"], capture_output=True)
    if bunkerweb_state.stdout.decode().strip() != "active":
        bunkerweb_logs = subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "journalctl -u bunkerweb.service"], capture_output=True)
        print("❌ bunkerweb.service is not running. Logs:", bunkerweb_logs.stdout.decode())
        sys.exit(1)

    bunkerweb_ui_state = subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "systemctl is-active bunkerweb-ui.service"], capture_output=True)
    if bunkerweb_ui_state.stdout.decode().strip() != "active":
        bunkerweb_ui_logs = subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "journalctl -u bunkerweb-ui.service"], capture_output=True)
        print("❌ bunkerweb-ui.service is not running. Logs:", bunkerweb_ui_logs.stdout.decode())
        sys.exit(1)
    #Checking Reloading test
    try:
        if bunkerweb_state.stdout.decode().strip() == "active":
            test_results["Reloading test"] = "OK"
        else:
            test_results["Reloading test"] = "KO"
            sys.exit(1)
    except:
        test_results["Reloading test"] = "KO"
        sys.exit(1)
    
    # Removing test
    print("Removing bunkerweb...")
    subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "apt remove -y bunkerweb"])

    result = subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "[ -d /usr/share/bunkerweb ]"], capture_output=True)
    if result.returncode != 0:
        print("✔️ /usr/share/bunkerweb not found.")
    else:
        print("❌ /usr/share/bunkerweb found.")

    result = subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "[ -d /var/tmp/bunkerweb ]"], capture_output=True)
    if result.returncode != 0:
        print("✔️ /var/tmp/bunkerweb not found.")
    else:
        print("❌ /var/tmp/bunkerweb found.")

    result = subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "[ -d /var/cache/bunkerweb ]"], capture_output=True)
    if result.returncode != 0:
        print("✔️ /var/cache/bunkerweb not found.")
    else:
        print("❌ /var/cache/bunkerweb found.")

    result = subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "[ -f /usr/bin/bwcli ]"], capture_output=True)
    if result.returncode != 0:
        print("✔️ /usr/bin/bwcli not found.")
    else:
        print("❌ /usr/bin/bwcli found.")
    #Checking Removing test
    try:
        if not os.path.isdir("/usr/share/bunkerweb") and not os.path.isdir("/var/tmp/bunkerweb") and not os.path.isdir("/var/cache/bunkerweb") and not os.path.isfile("/usr/bin/bwcli"):
            test_results["Removing test"] = "OK"
        else:
            test_results["Removing test"] = "KO"
            sys.exit(1)
    except:
        test_results["Removing test"] = "KO"

    # Purging test
    print("Purging bunkerweb...")
    subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "apt purge -y bunkerweb"])

    result = subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "[ -d /var/lib/bunkerweb ]"], capture_output=True)
    if result.returncode != 0:
        print("✔️ /var/lib/bunkerweb not found.")
    else:
        print("❌ /var/lib/bunkerweb found.")

    result = subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "[ -d /etc/bunkerweb ]"], capture_output=True)
    if result.returncode != 0:
        print("✔️ /etc/bunkerweb not found.")
    else:
        print("❌ /etc/bunkerweb found.")
    #Checking Purging test
    try:
        if not os.path.isdir("/var/lib/bunkerweb") and not os.path.isdir("/etc/bunkerweb"):
            test_results["Purging test"] = "OK"
        else:
            test_results["Purging test"] = "KO"
            sys.exit(1)
    except:
        test_results["Purging test"] = "KO"
        sys.exit(1)

    # Upgrading test
    print("Upgrading bunkerweb...")
    # Installing official package
    subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "sudo apt remove -y nginx"])
    subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "sudo apt install -y nginx=1.20.2-1~jammy"])
    subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "curl -s https://packagecloud.io/install/repositories/bunkerity/bunkerweb/script.deb.sh | sudo bash"])
    subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "sudo apt update"])
    subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "sudo apt install -y bunkerweb=1.4.5"])

    # Checking version
    old_version = subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "cat /usr/share/bunkerweb/VERSION"], capture_output=True)
    print("Old version:", old_version.stdout.decode().strip())

    # Upgrading package
    subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "sudo apt install -y /data/bunkerweb.deb"])

    # Checking version
    new_version = subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "cat /usr/share/bunkerweb/VERSION"], capture_output=True)
    print("New version:", new_version.stdout.decode().strip())
    try:
        if old_version.stdout.decode().strip() != new_version.stdout.decode().strip():
            test_results["Upgrading test"] = "OK"
        else:
            test_results["Upgrading test"] = "KO"
            sys.exit(1)
    except:
        test_results["Upgrading test"] = "KO"
        sys.exit(1)

    # Print summary
    for key, value in test_results.items():
        print(f'{key}: {value}')
    if "KO" in test_results.values():
        sys.exit(1)

elif distro == "rhel":
    print("RHEL not supported yet.")
elif distro == "centos":
    subprocess.run(["docker", "build", "-t", "centos-image", "-f", "../src/linux/Dockerfile-centos", "."])
    subprocess.run(["docker", "run", "-it", "--name", "centos-container", "-v", "deb:/data", "centos-image"])
    subprocess.run(["docker", "run", "-d", "--name", "systemd-{}".format(distro), "--privileged", "-v", "/sys/fs/cgroup:/sys/fs/cgroup", "-v", "deb:/data", "quay.io/centos/centos:stream8"])

    # Installing test
    print("Installing bunkerweb...")
    bash_script = """
    dnf install -y nginx-1.20.2
    apt install /data/bunkerweb.deb -y
    """

    with tempfile.NamedTemporaryFile(mode='w') as f:
        f.write(bash_script)
        f.flush()
        subprocess.run(["docker", "cp", f.name, "systemd-ubuntu:/tmp/install_nginx.sh"])
        result = subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "/tmp/install_nginx.sh"])
    if result.returncode != 0:
        bunkerweb_logs = subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "systemctl status bunkerweb.service"], capture_output=True)
        print("Logs from bunkerweb:", bunkerweb_logs.stdout.decode())

        bunkerweb_ui_logs = subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "systemctl status bunkerweb-ui.service"], capture_output=True)
        print("Logs from bunkerweb-ui:", bunkerweb_ui_logs.stdout.decode())
        sys.exit(result.returncode)
        exit(result.returncode)
    else:
        print("✔️ Installation successful ✔️")
    #Checking Installation test
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
    subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "echo 'HTTPS_PORT=8443' >> /etc/bunkerweb/variables.env"])
    subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "echo 'new_value=1' >> /etc/bunkerweb/ui.env"])
    subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "systemctl reload bunkerweb"])
    subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "systemctl reload bunkerweb-ui"])

    bunkerweb_state = subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "systemctl is-active bunkerweb.service"], capture_output=True)
    if bunkerweb_state.stdout.decode().strip() != "active":
        bunkerweb_logs = subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "journalctl -u bunkerweb.service"], capture_output=True)
        print("❌ bunkerweb.service is not running. Logs:", bunkerweb_logs.stdout.decode())
        sys.exit(1)

    bunkerweb_ui_state = subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "systemctl is-active bunkerweb-ui.service"], capture_output=True)
    if bunkerweb_ui_state.stdout.decode().strip() != "active":
        bunkerweb_ui_logs = subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "journalctl -u bunkerweb-ui.service"], capture_output=True)
        print("❌ bunkerweb-ui.service is not running. Logs:", bunkerweb_ui_logs.stdout.decode())
        sys.exit(1)
    #Checking Reloading test
    try:
        if bunkerweb_state.stdout.decode().strip() == "active":
            test_results["Reloading test"] = "OK"
        else:
            test_results["Reloading test"] = "KO"
            sys.exit(1)
    except:
        test_results["Reloading test"] = "KO"
        sys.exit(1)
    
    # Removing test
    print("Removing bunkerweb...")
    subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "apt remove -y bunkerweb"])

    result = subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "[ -d /usr/share/bunkerweb ]"], capture_output=True)
    if result.returncode != 0:
        print("✔️ /usr/share/bunkerweb not found.")
    else:
        print("❌ /usr/share/bunkerweb found.")

    result = subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "[ -d /var/tmp/bunkerweb ]"], capture_output=True)
    if result.returncode != 0:
        print("✔️ /var/tmp/bunkerweb not found.")
    else:
        print("❌ /var/tmp/bunkerweb found.")

    result = subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "[ -d /var/cache/bunkerweb ]"], capture_output=True)
    if result.returncode != 0:
        print("✔️ /var/cache/bunkerweb not found.")
    else:
        print("❌ /var/cache/bunkerweb found.")

    result = subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "[ -f /usr/bin/bwcli ]"], capture_output=True)
    if result.returncode != 0:
        print("✔️ /usr/bin/bwcli not found.")
    else:
        print("❌ /usr/bin/bwcli found.")
    #Checking Removing test
    try:
        if not os.path.isdir("/usr/share/bunkerweb") and not os.path.isdir("/var/tmp/bunkerweb") and not os.path.isdir("/var/cache/bunkerweb") and not os.path.isfile("/usr/bin/bwcli"):
            test_results["Removing test"] = "OK"
        else:
            test_results["Removing test"] = "KO"
            sys.exit(1)
    except:
        test_results["Removing test"] = "KO"

    # Purging test
    print("Purging bunkerweb...")
    subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "apt purge -y bunkerweb"])

    result = subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "[ -d /var/lib/bunkerweb ]"], capture_output=True)
    if result.returncode != 0:
        print("✔️ /var/lib/bunkerweb not found.")
    else:
        print("❌ /var/lib/bunkerweb found.")

    result = subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "[ -d /etc/bunkerweb ]"], capture_output=True)
    if result.returncode != 0:
        print("✔️ /etc/bunkerweb not found.")
    else:
        print("❌ /etc/bunkerweb found.")
    #Checking Purging test
    try:
        if not os.path.isdir("/var/lib/bunkerweb") and not os.path.isdir("/etc/bunkerweb"):
            test_results["Purging test"] = "OK"
        else:
            test_results["Purging test"] = "KO"
            sys.exit(1)
    except:
        test_results["Purging test"] = "KO"
        sys.exit(1)

    # Upgrading test
    print("Upgrading bunkerweb...")
    # Installing official package
    subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "sudo apt remove -y nginx"])
    subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "sudo apt install -y nginx=1.20.2-1~jammy"])
    subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "curl -s https://packagecloud.io/install/repositories/bunkerity/bunkerweb/script.deb.sh | sudo bash"])
    subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "sudo apt update"])
    subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "sudo apt install -y bunkerweb=1.4.5"])

    # Checking version
    old_version = subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "cat /usr/share/bunkerweb/VERSION"], capture_output=True)
    print("Old version:", old_version.stdout.decode().strip())

    # Upgrading package
    subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "sudo apt install -y /data/bunkerweb.deb"])

    # Checking version
    new_version = subprocess.run(["docker", "exec", "-it", "systemd-ubuntu", "bash", "-c", "cat /usr/share/bunkerweb/VERSION"], capture_output=True)
    print("New version:", new_version.stdout.decode().strip())
    try:
        if old_version.stdout.decode().strip() != new_version.stdout.decode().strip():
            test_results["Upgrading test"] = "OK"
        else:
            test_results["Upgrading test"] = "KO"
            sys.exit(1)
    except:
        test_results["Upgrading test"] = "KO"
        sys.exit(1)

    # Print summary
    for key, value in test_results.items():
        print(f'{key}: {value}')
    if "KO" in test_results.values():
        sys.exit(1)
else:
    print("Invalid argument. Please pass one of: ubuntu, debian, fedora, rhel, centos")
    sys.exit(1)