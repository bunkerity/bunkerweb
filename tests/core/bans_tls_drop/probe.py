#!/usr/bin/env python3
"""Probes for tests/core/bans_tls_drop/test.sh.

  probe.py peer                  the address BunkerWeb sees for a connection from this runner
  probe.py proxy SRC [--port N]  TLS handshake behind a PROXY v1 header claiming SRC as the client

`proxy` prints `OK <status line>` or `RESET <error>` and exits 0 / 3.
"""

import socket
import ssl
import subprocess
import sys
import time

HTTPS_PORT = 443
SNI = "www.example.com"


def peer() -> str:
    """Hold a TCP connection to the published HTTPS port and read the container's own view of it.

    The runner reaches BunkerWeb through Docker's published port, so the address nginx sees is the
    bridge gateway, not 127.0.0.1, and it differs per host. /proc/net/tcp of the instance is the one
    place that states it without parsing a log.
    """
    connection = socket.create_connection(("127.0.0.1", HTTPS_PORT), timeout=5)
    try:
        time.sleep(1)
        table = subprocess.run(["docker", "exec", "bunkerweb", "cat", "/proc/net/tcp"], capture_output=True, text=True, check=True).stdout
        addresses = set()
        for line in table.splitlines()[1:]:
            fields = line.split()
            local, remote, state = fields[1], fields[2], fields[3]
            # 01 = ESTABLISHED; the local half must be the HTTPS port (0x01BB).
            if state == "01" and int(local.split(":")[1], 16) == HTTPS_PORT:
                addresses.add(socket.inet_ntoa(bytes.fromhex(remote.split(":")[0])[::-1]))
        if len(addresses) != 1:
            sys.exit(f"expected exactly one client of :{HTTPS_PORT}, got {sorted(addresses)}")
        return addresses.pop()
    finally:
        connection.close()


def proxy(source: str, port: int) -> int:
    sock = socket.create_connection(("127.0.0.1", port), timeout=10)
    sock.sendall(f"PROXY TCP4 {source} 10.0.0.1 54321 {port}\r\n".encode())
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    try:
        tls = context.wrap_socket(sock, server_hostname=SNI)
        tls.sendall(f"GET / HTTP/1.0\r\nHost: {SNI}\r\n\r\n".encode())
        status = tls.recv(200).split(b"\r\n")[0].decode(errors="replace")
        tls.close()
        print(f"OK {status}")
        return 0
    except (ssl.SSLError, OSError) as error:
        sock.close()
        print(f"RESET {type(error).__name__}")
        return 3


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["peer"]:
        print(peer())
    elif args[:1] == ["proxy"] and len(args) >= 2:
        port = int(args[args.index("--port") + 1]) if "--port" in args else HTTPS_PORT
        sys.exit(proxy(args[1], port))
    else:
        sys.exit(__doc__)
