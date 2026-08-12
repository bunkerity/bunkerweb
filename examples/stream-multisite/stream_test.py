#!/usr/bin/env python3

import json
import socket
import subprocess
import sys
import time
from pathlib import Path


def udp_echo_server():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server:
        server.bind(("0.0.0.0", 9000))
        while True:
            data, address = server.recvfrom(65535)
            server.sendto(b"app2:" + data, address)


if __name__ == "__main__" and sys.argv[1:] == ["--udp-server"]:
    udp_echo_server()
    raise SystemExit(0)

requests = None

HERE = Path(__file__).resolve().parent
CENTRAL_API = "http://127.0.0.1:8888"
API_TOKEN = "stream-integration-token"
AUTH = {"Authorization": f"Bearer {API_TOKEN}"}
CORE_HEADERS = {**AUTH, "Host": "bwapi"}
CORE_PORTS = {"http": 5000, "https": 5443}

TCP_DETECT = ("app1.example.com", 10000)
UDP_DETECT = ("app2.example.com", 20000)
BLOCK = ("block.example.com", 10010)
ALLOW = ("allow.example.com", 10011)
BAN = ("ban.example.com", 10012)
PEER = ("peer.example.com", 10013)
AUTO_BAN = ("auto.example.com", 10014)
WEB_SERVICE = "web.example.com"


def eventually(label, check, timeout=90, interval=1):
    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        try:
            result = check()
            if result:
                return result
        except Exception as exc:
            last_error = exc
        time.sleep(interval)
    raise AssertionError(f"timed out waiting for {label}: {last_error}")


def central(method, path, **kwargs):
    response = requests.request(method, CENTRAL_API + path, headers=AUTH, timeout=10, **kwargs)
    if response.status_code >= 400:
        raise AssertionError(f"central API {method} {path} returned {response.status_code}: {response.text}")
    data = response.json()
    if data.get("status") == "error":
        raise AssertionError(f"central API {method} {path} failed: {data}")
    return data


def core(method, scheme, path, **kwargs):
    url = f"{scheme}://127.0.0.1:{CORE_PORTS[scheme]}{path}"
    response = requests.request(method, url, headers=CORE_HEADERS, timeout=8, verify=False, **kwargs)
    if response.status_code >= 400:
        raise AssertionError(f"core API {method} {url} returned {response.status_code}: {response.text}")
    data = response.json()
    if data.get("status") != "success":
        raise AssertionError(f"core API {method} {url} failed: {data}")
    return data


def public_api_closed(scheme):
    try:
        requests.get(
            f"{scheme}://127.0.0.1:{CORE_PORTS[scheme]}/health",
            headers=CORE_HEADERS,
            timeout=2,
            verify=False,
        )
    except requests.RequestException:
        return True
    return False


def reports(scheme):
    data = core("GET", scheme, "/metrics/requests/query?start=0&length=-1&count_only=false")
    return data["msg"]["data"]


def compose(*args, check=True):
    result = subprocess.run(
        ["docker", "compose", *args],
        cwd=HERE,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if check and result.returncode != 0:
        raise AssertionError(f"docker compose {' '.join(args)} failed: {result.stderr or result.stdout}")
    return result


def valkey(service, *args):
    output = compose("exec", "-T", service, "valkey-cli", "--raw", *args).stdout.strip().splitlines()
    return output[-1] if output else ""


def redis_reports():
    output = compose("exec", "-T", "bw-redis", "valkey-cli", "--raw", "LRANGE", "requests", "0", "-1")
    return [json.loads(row) for row in output.stdout.splitlines() if row]


def ids_occur_once(rows, report_ids):
    return all(sum(row.get("id") == report_id for row in rows) == 1 for report_id in report_ids)


def tcp_exchange(port, marker=None):
    marker = marker or f"tcp-{time.time_ns()}".encode()
    with socket.create_connection(("127.0.0.1", port), timeout=4) as client:
        client.settimeout(4)
        client.sendall(marker + b"\n")
        client.shutdown(socket.SHUT_WR)
        response = client.recv(4096)
    if marker not in response:
        raise AssertionError(f"TCP {port} did not echo the marker: {response!r}")
    return response


def tcp_is_blocked(port):
    try:
        tcp_exchange(port)
    except (OSError, AssertionError):
        return True
    return False


def udp_exchange(port, marker=None):
    marker = marker or f"udp-{time.time_ns()}".encode()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
        client.settimeout(5)
        client.sendto(marker, ("127.0.0.1", port))
        response, _ = client.recvfrom(4096)
    if marker not in response:
        raise AssertionError(f"UDP {port} did not echo the marker: {response!r}")
    return response


def assert_http_service():
    response = requests.get("http://127.0.0.1:8080", headers={"Host": WEB_SERVICE}, timeout=5)
    if response.status_code != 200:
        raise AssertionError(f"HTTP service returned {response.status_code}: {response.text[:200]}")


def apply_phase(scheme, redis_enabled):
    expected = {
        # Keep HTTPS stable as the registered control-plane endpoint. Closing
        # HTTP for the HTTPS phases proves the UDS handoff with HTTPS as the
        # only public listener without exercising endpoint migration here.
        "API_LISTEN_HTTP": "yes" if scheme == "http" else "no",
        "API_LISTEN_HTTPS": "yes",
        "USE_REDIS": "yes" if redis_enabled else "no",
    }
    central("PATCH", "/global_settings", json=expected)

    def configuration_applied():
        variables = core("GET", scheme, "/variables")["data"]["global"]
        return variables if all(variables.get(key) == value for key, value in expected.items()) else False

    eventually(
        f"{scheme} API with Redis {'on' if redis_enabled else 'off'}",
        configuration_applied,
    )
    eventually(
        "central API instance handoff",
        lambda: central("GET", "/instances/bunkerweb/ping") == {"status": "success", "msg": "pong"},
    )
    if scheme == "https":
        eventually(
            "HTTP API listener to close",
            lambda: public_api_closed("http"),
            timeout=30,
        )
    assert_http_service()


def matching_reports(rows, service, started, *, security_mode=None, status=None, reason=None):
    matches = []
    for report in rows:
        if report.get("server_name") != service or float(report.get("date", 0)) < started:
            continue
        if security_mode is not None and report.get("security_mode") != security_mode:
            continue
        if status is not None and int(report.get("status", 0)) != status:
            continue
        if reason is not None and report.get("reason") != reason:
            continue
        matches.append(report)
    return matches


def fresh_report(scheme, service, started, **filters):
    matches = matching_reports(reports(scheme), service, started, **filters)
    return matches[0] if matches else None


def observe_detect_phase(scheme, redis_enabled):
    if valkey("bw-redis", "FLUSHDB") != "OK":
        raise AssertionError("failed to flush the test data-plane Redis")

    eventually("TCP detect listener readiness", lambda: tcp_exchange(TCP_DETECT[1]))
    eventually("UDP detect listener readiness", lambda: udp_exchange(UDP_DETECT[1]))
    started = time.time()
    tcp_exchange(TCP_DETECT[1])
    udp_exchange(UDP_DETECT[1])

    tcp_report = eventually(
        f"{scheme}/Redis-{redis_enabled} TCP detect report",
        lambda: fresh_report(scheme, TCP_DETECT[0], started, security_mode="detect", reason="blacklist"),
    )
    udp_report = eventually(
        f"{scheme}/Redis-{redis_enabled} UDP detect report",
        lambda: fresh_report(scheme, UDP_DETECT[0], started, security_mode="detect", reason="blacklist"),
    )
    report_ids = (tcp_report["id"], udp_report["id"])
    # The protocol is a field of its own now. It used to be smuggled into `method` as "TCP"/"UDP",
    # which put an L4 protocol in a column that only ever means an HTTP verb.
    if tcp_report.get("protocol") != "tcp" or udp_report.get("protocol") != "udp":
        raise AssertionError(f"unexpected Stream report protocols: {tcp_report.get('protocol')}, {udp_report.get('protocol')}")
    for report in (tcp_report, udp_report):
        for http_only in ("method", "url", "user_agent"):
            if report.get(http_only) is not None:
                raise AssertionError(f"Stream report carries the HTTP-only field {http_only}: {report.get(http_only)}")
        for l4_field in ("listen_port", "client_port", "bytes_sent", "bytes_received", "session_time"):
            if report.get(l4_field) is None:
                raise AssertionError(f"Stream report is missing the L4 field {l4_field}")
    if len(set(report_ids)) != 2:
        raise AssertionError(f"TCP and UDP reports reused an ID: {report_ids}")
    eventually(
        "one public report per TCP/UDP event",
        lambda: ids_occur_once(reports(scheme), report_ids),
    )

    if redis_enabled:
        eventually(
            "one Redis row per TCP/UDP event",
            lambda: ids_occur_once(redis_reports(), report_ids),
        )
    time.sleep(7)
    public_rows = reports(scheme)
    public_tcp = matching_reports(
        public_rows,
        TCP_DETECT[0],
        started,
        security_mode="detect",
        reason="blacklist",
    )
    public_udp = matching_reports(
        public_rows,
        UDP_DETECT[0],
        started,
        security_mode="detect",
        reason="blacklist",
    )
    if len(public_tcp) != 1 or len(public_udp) != 1 or not ids_occur_once(public_rows, report_ids):
        raise AssertionError(f"public report deduplication did not settle for {report_ids}")
    redis_rows = redis_reports()
    if redis_enabled:
        redis_tcp = matching_reports(
            redis_rows,
            TCP_DETECT[0],
            started,
            security_mode="detect",
            reason="blacklist",
        )
        redis_udp = matching_reports(
            redis_rows,
            UDP_DETECT[0],
            started,
            security_mode="detect",
            reason="blacklist",
        )
        if len(redis_tcp) != 1 or len(redis_udp) != 1 or not ids_occur_once(redis_rows, report_ids):
            raise AssertionError(f"Redis report deduplication did not settle for {report_ids}")
    elif any(row.get("id") in report_ids for row in redis_rows):
        raise AssertionError("USE_REDIS=no wrote current detect reports to data-plane Redis")

    print(f"ok: {scheme}, Redis {'on' if redis_enabled else 'off'}, TCP+UDP detect/report")
    return tcp_report["ip"]


def exercise_block_and_whitelist(scheme):
    started = time.time() - 1
    if not tcp_is_blocked(BLOCK[1]):
        raise AssertionError("blacklisted Stream TCP client was not blocked")
    eventually(
        "Stream block report",
        lambda: fresh_report(
            scheme,
            BLOCK[0],
            started,
            security_mode="block",
            status=403,
            reason="blacklist",
        ),
    )

    started = time.time() - 1
    tcp_exchange(ALLOW[1])
    time.sleep(7)
    if fresh_report(scheme, ALLOW[0], started):
        raise AssertionError("terminal whitelist allow unexpectedly created a report")
    print("ok: real block report and terminal whitelist allow without report")


def listed_ban(scope, ip, service=None):
    for response in central("GET", "/bans").values():
        if not isinstance(response, dict):
            continue
        for ban in response.get("data", []):
            if ban.get("ip") == ip and ban.get("ban_scope") == scope and (service is None or ban.get("service") == service):
                return ban
    return None


def unban(ip, service=None):
    payload = {"ip": ip}
    if service:
        payload["service"] = service
    central("POST", "/bans/unban", json=payload)


def exercise_ban_sync(client_ip):
    tcp_exchange(BAN[1])
    tcp_exchange(PEER[1])

    central(
        "POST",
        "/bans/ban",
        json={"ip": client_ip, "exp": 300, "reason": "stream-integration-global"},
    )
    try:
        eventually("global ban in the public API", lambda: listed_ban("global", client_ip))
        eventually("global ban in Stream workers", lambda: tcp_is_blocked(BAN[1]))
        eventually("global ban on peer Stream service", lambda: tcp_is_blocked(PEER[1]))
        assert_http_service()
    finally:
        unban(client_ip)
    eventually("global unban recovery", lambda: tcp_exchange(BAN[1]))
    eventually("global peer recovery", lambda: tcp_exchange(PEER[1]))

    central(
        "POST",
        "/bans/ban",
        json={
            "ip": client_ip,
            "exp": 300,
            "reason": "stream-integration-service",
            "service": BAN[0],
        },
    )
    try:
        eventually(
            "service ban in the public API",
            lambda: listed_ban("service", client_ip, BAN[0]),
        )
        eventually("service ban in Stream workers", lambda: tcp_is_blocked(BAN[1]))
        tcp_exchange(PEER[1])
    finally:
        unban(client_ip, BAN[0])
    eventually("service unban recovery", lambda: tcp_exchange(BAN[1]))
    print("ok: global and service ban propagation plus unban recovery")


def exercise_stream_originated_ban(client_ip):
    tcp_exchange(AUTO_BAN[1])
    try:
        eventually(
            "Stream-originated bad-behavior ban in the public API",
            lambda: listed_ban("service", client_ip, AUTO_BAN[0]),
        )
        eventually("Stream-originated bad-behavior enforcement", lambda: tcp_is_blocked(AUTO_BAN[1]))
        assert_http_service()
    finally:
        unban(client_ip, AUTO_BAN[0])
    eventually("Stream-originated ban central unban recovery", lambda: tcp_exchange(AUTO_BAN[1]))
    print("ok: Stream-originated bad-behavior ban, authority replay, and central unban")


def exercise_redis_persisted_ban(client_ip):
    redis_key = f"bans_service_{BAN[0]}_ip_{client_ip}"
    central(
        "POST",
        "/bans/ban",
        json={
            "ip": client_ip,
            "exp": 300,
            "reason": "stream-integration-redis-restart",
            "service": BAN[0],
        },
    )
    try:
        eventually("service ban persisted in Redis", lambda: valkey("bw-redis", "GET", redis_key))
        compose("restart", "bunkerweb")
        eventually(
            "core API after BunkerWeb restart",
            lambda: central("GET", "/instances/bunkerweb/ping") == {"status": "success", "msg": "pong"},
            timeout=120,
        )
        eventually("peer Stream listener after BunkerWeb restart", lambda: tcp_exchange(PEER[1]))
        eventually("Redis-only service ban after BunkerWeb restart", lambda: tcp_is_blocked(BAN[1]))
    finally:
        unban(client_ip, BAN[0])
    eventually("Redis-only service unban recovery", lambda: tcp_exchange(BAN[1]))
    print("ok: Redis-backed Stream ban survives a cold local-state restart")


def exercise_redis_fault_recovery(scheme):
    if valkey("bw-redis", "FLUSHDB") != "OK":
        raise AssertionError("failed to flush the test data-plane Redis")

    started = time.time() - 1
    recovered_report = None
    compose("stop", "bw-redis")
    try:
        if valkey("bw-jobs-broker", "PING") != "PONG":
            raise AssertionError("Celery broker was affected by the data-plane Redis fault")
        tcp_exchange(TCP_DETECT[1])
        recovered_report = eventually(
            "in-memory report while data-plane Redis is down",
            lambda: fresh_report(
                scheme,
                TCP_DETECT[0],
                started,
                security_mode="detect",
                reason="blacklist",
            ),
        )
        assert_http_service()
    finally:
        compose("start", "bw-redis", check=False)

    eventually("data-plane Redis restart", lambda: valkey("bw-redis", "PING") == "PONG")
    report_id = recovered_report["id"]
    eventually(
        "single buffered report replay to Redis",
        lambda: ids_occur_once(redis_reports(), (report_id,)),
    )
    eventually(
        "single recovered public report",
        lambda: ids_occur_once(reports(scheme), (report_id,)),
    )
    time.sleep(7)
    if not ids_occur_once(redis_reports(), (report_id,)) or not ids_occur_once(reports(scheme), (report_id,)):
        raise AssertionError("report replay was lost or duplicated after data-plane Redis recovery")
    if valkey("bw-jobs-broker", "PING") != "PONG":
        raise AssertionError("Celery broker did not remain healthy")
    print("ok: bounded data-plane Redis fault, in-memory continuity, and replay")


def best_effort_cleanup(client_ip):
    compose("start", "bw-redis", check=False)
    if not client_ip:
        return
    for service in (BAN[0], AUTO_BAN[0], None):
        try:
            unban(client_ip, service)
        except Exception:
            pass


def main():
    global requests

    import requests as requests_module

    requests = requests_module
    requests.packages.urllib3.disable_warnings()

    client_ip = None
    observations = []
    eventually(
        "central API startup",
        lambda: requests.get(CENTRAL_API + "/health", timeout=5).status_code == 200,
        timeout=120,
    )
    phases = (("http", False), ("http", True), ("https", False), ("https", True))

    try:
        for index, (scheme, redis_enabled) in enumerate(phases):
            apply_phase(scheme, redis_enabled)
            phase_ip = observe_detect_phase(scheme, redis_enabled)
            client_ip = client_ip or phase_ip
            observations.extend(((scheme, redis_enabled, "tcp"), (scheme, redis_enabled, "udp")))
            assert_http_service()
            if index == 0:
                exercise_block_and_whitelist(scheme)
                exercise_ban_sync(client_ip)
            elif index == 1:
                exercise_redis_persisted_ban(client_ip)
                exercise_stream_originated_ban(client_ip)

        if len(observations) != 8:
            raise AssertionError(f"expected 8 matrix observations, got {observations}")
        exercise_redis_fault_recovery("https")
        assert_http_service()
        print(f"ok: complete 8-observation matrix: {observations}")
    finally:
        best_effort_cleanup(client_ip)


if __name__ == "__main__":
    main()
