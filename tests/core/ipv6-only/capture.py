#!/usr/bin/env python3
"""Sample only this stack's network namespaces, from startup through teardown."""

import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

CONTAINERS = ("redis", "dnsmasq", "bunkerweb", "bw-scheduler", "app1", "ipv6-client", "ipv6-other", "ipv6-untrusted", "ipv6-backend")


def capture(root):
    root.mkdir(parents=True, exist_ok=True)
    # Reuse installed host tools, including their loader/libs, inside Alpine namespaces.
    tools = root / "tools"
    tools.mkdir(exist_ok=True)
    for binary in ("/usr/bin/ss", "/usr/sbin/ip"):
        shutil.copy2(binary, tools)
        output = subprocess.check_output(["ldd", binary], text=True)
        for library in re.findall(r"(?:=>\s+)?(/\S+)", output):
            shutil.copy2(library, tools / Path(library).name)
    loader = next(tools.glob("ld-linux*")).name
    ready = set()
    started = time.monotonic()
    with (root / "sockets.jsonl").open("w", buffering=1) as output:
        while time.monotonic() - started < 3600 and not (root / "stop").exists():
            for container in CONTAINERS:
                result = subprocess.run(["docker", "inspect", "--format", "{{.State.Pid}}", container], text=True, capture_output=True, timeout=10, check=False)
                if result.returncode or not result.stdout.strip().isdigit() or int(result.stdout) == 0:
                    continue
                pid = result.stdout.strip()
                identity = (container, pid)
                if identity not in ready:
                    result = subprocess.run(
                        ["docker", "cp", str(tools), container + ":/tmp/ipv6-tools"], text=True, capture_output=True, timeout=20, check=False
                    )
                    if result.returncode:
                        continue
                    ready.add(identity)
                for command in (
                    ["ss", "-4", "-a", "-t", "-u", "-n", "-p"],
                    ["ss", "-6", "-a", "-t", "-u", "-n", "-p"],
                    ["ip", "-j", "addr"],
                    ["ip", "-j", "-4", "route"],
                ):
                    result = subprocess.run(
                        [
                            "docker",
                            "exec",
                            "-u",
                            "0",
                            container,
                            "/tmp/ipv6-tools/" + loader,
                            "--library-path",
                            "/tmp/ipv6-tools",
                            "/tmp/ipv6-tools/" + command[0],
                            *command[1:],
                        ],
                        text=True,
                        capture_output=True,
                        timeout=10,
                        check=False,
                    )
                    output.write(
                        json.dumps(
                            dict(time=time.time(), container=container, pid=pid, command=command, code=result.returncode, out=result.stdout, err=result.stderr)
                        )
                        + "\n"
                    )
            time.sleep(1)


if __name__ == "__main__":
    capture(Path(sys.argv[1]))
