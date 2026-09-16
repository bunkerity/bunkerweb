"""Audit-only real HTTP/API/SQLite/scheduler/Redis/NGINX scenarios.

Requires Docker on an ephemeral runner. It creates only the bw-audit-runtime Compose
project, binds client ports to loopback, generates throwaway credentials, collects
results, and removes its own containers and volumes in finally.
"""
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import re
import secrets
import socket
import struct
import subprocess
import sys
import threading
import time
import traceback
import urllib.parse
import urllib.request
import urllib.error
from http.cookiejar import CookieJar

SHA = '5d91090c3c42a4bc2b0a57adce37f9c04b9d7b5f'
RESULTS = []
OUT = Path('audit-results').resolve()
TOKEN = secrets.token_urlsafe(32)
PASSWORD = 'Audit-' + secrets.token_urlsafe(24) + '-7!'
SECRET = 'runtime-' + secrets.token_hex(16)
COMPOSE = ['docker', 'compose', '--project-name', 'bw-audit-runtime', '--file', str(OUT / 'compose.json')]


def command(args, **kwargs):
    return subprocess.run(args, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180, **kwargs).stdout


def need(ok, message):
    if not ok:
        raise AssertionError(message)


def record(name, fn):
    start = time.monotonic()
    try:
        detail = fn()
        result = {'name': name, 'status': 'PASS', 'detail': detail}
    except Exception as exc:
        result = {'name': name, 'status': 'FAIL', 'error': str(exc), 'traceback': traceback.format_exc()}
    result['seconds'] = round(time.monotonic() - start, 3)
    RESULTS.append(result)
    print(json.dumps(result), flush=True)
    (OUT / 'runtime-results.json').write_text(json.dumps(RESULTS, indent=2))


def http(port, path='/', method='GET', host='app.audit.test', headers=None, body=None):
    conn = HTTPConnection('127.0.0.1', port, timeout=8)
    supplied = {'Host': host, 'User-Agent': 'BunkerWeb-audit', 'X-Forwarded-For': '8.8.4.4'}
    supplied.update(headers or {})
    try:
        conn.request(method, path, body=body, headers=supplied)
        response = conn.getresponse()
        content = response.read()
        return response.status, dict(response.getheaders()), content
    finally:
        conn.close()


def api(path, method='GET', payload=None, authenticated=True):
    headers = {'Content-Type': 'application/json'}
    if authenticated:
        headers['Authorization'] = 'Bearer ' + TOKEN
    code, _, data = http(18888, path, method, host='localhost', headers=headers,
                         body=json.dumps(payload).encode() if payload is not None else None)
    try:
        data = json.loads(data)
    except ValueError:
        data = data.decode(errors='replace')[:1200]
    return code, data


def await_http(port, host, status=200, path='/', headers=None, timeout=100):
    stop = time.monotonic() + timeout
    last = None
    while time.monotonic() < stop:
        try:
            last = http(port, path, host=host, headers=headers)
            if last[0] == status:
                return last
        except (OSError, TimeoutError) as exc:
            last = str(exc)
        time.sleep(2)
    raise AssertionError(f'{host}:{port}{path}: expected {status}, last={str(last)[:900]}')


def expect_status(port, host, expected, path='/', headers=None, body=None):
    code, rh, data = http(port, path, 'POST' if body is not None else 'GET', host, headers, body)
    need(code == expected, f'{host}:{port}{path}: expected {expected}, got {code}; body={data[:300]!r}')
    return {'http_status': code, 'worker_port': port, 'bytes': len(data)}


def patch(service, variables):
    code, body = api('/services/' + service, 'PATCH', {'variables': variables})
    need(200 <= code < 300, f'API patch failed {code}: {body}')
    return {'api_status': code}


def fixture_server():
    class Backend(BaseHTTPRequestHandler):
        def do_GET(self):
            status = 404 if self.path.startswith('/backend-error') else 200
            data = json.dumps({'fixture': 'audit-backend', 'path': self.path,
                               'headers': dict(self.headers)}).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        def do_POST(self):
            data = self.rfile.read(int(self.headers.get('Content-Length', '0')))
            output = json.dumps({'fixture': 'audit-backend', 'body_bytes': len(data)}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(output)))
            self.end_headers()
            self.wfile.write(output)
        def log_message(self, *args):
            pass
    def dns():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('0.0.0.0', 5353))
        while True:
            query, addr = sock.recvfrom(4096)
            try:
                pos, labels = 12, []
                while query[pos]:
                    size = query[pos]
                    labels.append(query[pos+1:pos+1+size].decode('ascii').lower())
                    pos += size + 1
                pos += 1
                qtype, qclass = struct.unpack('!HH', query[pos:pos+4])
                end = pos + 4
                if '.'.join(labels).endswith('.dnsbl.audit.test'):
                    answer = qtype == 1
                    response = query[:2] + struct.pack('!HHHHH', 0x8180, 1, int(answer), 0, 0) + query[12:end]
                    if answer:
                        response += b'\xc0\x0c' + struct.pack('!HHIH', 1, 1, 5, 4) + socket.inet_aton('127.0.0.2')
                else:
                    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as upstream:
                        upstream.settimeout(3)
                        upstream.sendto(query, ('127.0.0.11', 53))
                        response = upstream.recv(4096)
                sock.sendto(response, addr)
            except Exception:
                continue
    threading.Thread(target=dns, daemon=True).start()
    ThreadingHTTPServer(('0.0.0.0', 8080), Backend).serve_forever()


def build_compose():
    image = lambda name: f'ghcr.io/bunkerity/{name}-tests:dev'
    shared = {'DATABASE_URI': 'sqlite:////data/db.sqlite3', 'API_TOKEN': TOKEN,
              'API_WHITELIST_IP': '127.0.0.0/8 10.77.0.0/24', 'LOG_LEVEL': 'notice'}
    settings = dict(shared, MULTISITE='yes', SERVER_NAME='bootstrap.audit.test',
                    BUNKERWEB_INSTANCES='bw bw2', WORKER_PROCESSES='2', USE_BUNKERNET='no',
                    SEND_ANONYMOUS_REPORT='no', USE_BACKUP='no', USE_BLACKLIST='no',
                    USE_WHITELIST='no', USE_GREYLIST='no', USE_DNSBL='no', USE_REVERSE_SCAN='no',
                    USE_BAD_BEHAVIOR='no', USE_LIMIT_REQ='no', USE_LIMIT_CONN='no', USE_ANTIBOT='no',
                    USE_MODSECURITY='no', USE_MODSECURITY_CRS='no', USE_MODSECURITY_CRS_PLUGINS='no',
                    USE_METRICS='yes', USE_REDIS='yes', REDIS_HOST='redis', REDIS_TIMEOUT='250',
                    USE_REAL_IP='yes', REAL_IP_FROM='10.77.0.0/24 127.0.0.0/8', REAL_IP_HEADER='X-Forwarded-For',
                    DNS_RESOLVERS='10.77.0.53:5353', USE_REVERSE_PROXY='yes',
                    REVERSE_PROXY_HOST='http://backend:8080', DISABLE_DEFAULT_SERVER='yes',
                    REDIRECT_HTTP_TO_HTTPS='no')
    services = {
        'bw': {'image': image('bunkerweb'), 'environment': dict(shared, KEEP_CONFIG_ON_RESTART='yes'),
               'ports': ['127.0.0.1:18880:8080'], 'volumes': ['worker1:/data']},
        'bw2': {'image': image('bunkerweb'), 'environment': dict(shared, KEEP_CONFIG_ON_RESTART='yes'),
                'ports': ['127.0.0.1:18881:8080'], 'volumes': ['worker2:/data']},
        'scheduler': {'image': image('scheduler'), 'environment': settings, 'volumes': ['shared:/data'],
                      'depends_on': ['bw', 'bw2', 'backend', 'redis']},
        'api': {'image': image('api'), 'environment': dict(shared, API_LISTEN_PORT='8888', MAX_WORKERS='2'),
                'volumes': ['shared:/data'], 'ports': ['127.0.0.1:18888:8888'],
                'depends_on': {'scheduler': {'condition': 'service_healthy'}}},
        'ui': {'image': image('ui'), 'environment': dict(shared, ADMIN_USERNAME='audit-admin', ADMIN_PASSWORD=PASSWORD,
                  MAX_WORKERS='2', ENABLE_HEALTHCHECK='yes'), 'volumes': ['shared:/data'],
                'ports': ['127.0.0.1:18700:7000'], 'depends_on': {'scheduler': {'condition': 'service_healthy'}}},
        'redis': {'image': 'redis:8-alpine', 'command': ['redis-server', '--save', '', '--appendonly', 'no']},
        'backend': {'image': image('api'), 'entrypoint': ['python3', '/audit_runtime.py', 'backend'],
                    'volumes': [str(Path(__file__).resolve()) + ':/audit_runtime.py:ro'],
                    'healthcheck': {'disable': True}, 'networks': {'default': {'ipv4_address': '10.77.0.53'}}}
    }
    for value in services.values():
        value['restart'] = 'no'
    return {'services': services, 'volumes': {key: {} for key in ('shared', 'worker1', 'worker2')},
            'networks': {'default': {'ipam': {'config': [{'subnet': '10.77.0.0/24'}]}}}}


def run_scenarios():
    for component in ('bunkerweb', 'scheduler', 'api', 'ui'):
        ref = f'ghcr.io/bunkerity/{component}-tests:dev'
        subprocess.run(['docker', 'pull', ref], check=True, timeout=180)
        inspected = json.loads(command(['docker', 'image', 'inspect', ref]))
        (OUT / f'image-{component}.json').write_text(json.dumps(inspected, indent=2))
        need(inspected[0]['Config']['Labels'].get('org.opencontainers.image.revision') == SHA, 'Image source mismatch: ' + ref)
    (OUT / 'compose.json').write_text(json.dumps(build_compose(), indent=2))
    command([*COMPOSE, 'create', '--no-build', 'scheduler'])
    subprocess.run([*COMPOSE, 'up', '-d', '--wait', '--wait-timeout', '500', '--no-build'], check=True, timeout=540)
    for port in (18880, 18881):
        record(f'bootstrap.worker_{port}', lambda port=port: await_http(port, 'bootstrap.audit.test')[0])
    code, body = api('/services', authenticated=False)
    record('api.anonymous_access_denied', lambda: need(code in (401, 403), f'anonymous API returned {code} {body}'))
    definitions = {
        'app': {},
        'antibot': {'USE_ANTIBOT': 'cookie', 'ANTIBOT_IGNORE_HEADER_NAME_1': 'X-Audit-Bypass', 'ANTIBOT_IGNORE_HEADER_VALUE_1': '^' + SECRET + '$'},
        'blacklist': {'USE_BLACKLIST': 'yes', 'BLACKLIST_COMMUNITY_LISTS': '', 'BLACKLIST_IP': '8.8.4.4',
                      'BLACKLIST_IGNORE_HEADER_NAME_1': 'X-Audit-Bypass', 'BLACKLIST_IGNORE_HEADER_VALUE_1': '^' + SECRET + '$'},
        'greylist': {'USE_GREYLIST': 'yes', 'GREYLIST_HEADER_NAME_1': 'X-Audit-Bypass', 'GREYLIST_HEADER_VALUE_1': '^' + SECRET + '$'},
        'whitelist': {'USE_WHITELIST': 'yes', 'WHITELIST_COUNTRY': 'FR',
                      'WHITELIST_HEADER_NAME_1': 'X-Audit-Bypass', 'WHITELIST_HEADER_VALUE_1': '^' + SECRET + '$'},
        'country': {'WHITELIST_COUNTRY': 'FR', 'COUNTRY_IGNORE_HEADER_NAME_1': 'X-Audit-Bypass', 'COUNTRY_IGNORE_HEADER_VALUE_1': '^' + SECRET + '$'},
        'dnsbl': {'USE_DNSBL': 'yes', 'DNSBL_LIST': 'dnsbl.audit.test', 'DNSBL_IGNORE_HEADER_NAME_1': 'X-Audit-Bypass', 'DNSBL_IGNORE_HEADER_VALUE_1': '^' + SECRET + '$'},
        'body': {'MAX_CLIENT_SIZE': '1k', 'USE_MODSECURITY': 'yes', 'REVERSE_PROXY_HOST_1': 'http://backend:8080',
                 'REVERSE_PROXY_URL_1': '/large/', 'REVERSE_PROXY_MAX_CLIENT_SIZE_1': '4k'},
        'modsec': {'USE_MODSECURITY': 'yes'},
    }
    for prefix, values in definitions.items():
        host = prefix + '.audit.test'
        code, body = api('/services', 'POST', {'server_name': host, 'variables': values})
        record('api.create.' + prefix, lambda code=code, body=body: need(200 <= code < 300, f'{code}: {body}'))
    for prefix in definitions:
        host = prefix + '.audit.test'
        for port in (18880, 18881):
            record(f'publication.{prefix}.{port}', lambda host=host, port=port: await_http(port, host, headers={'X-Audit-Bypass': SECRET})[0])
    for prefix in ('antibot', 'blacklist', 'greylist', 'whitelist', 'country', 'dnsbl'):
        host = prefix + '.audit.test'
        blocked = 302 if prefix == 'antibot' else 403
        for port in (18880, 18881):
            for label, headers, expected in (
                ('missing', {}, blocked), ('wrong', {'X-Audit-Bypass': 'wrong'}, blocked),
                ('correct', {'x-audit-bypass': SECRET}, 200),
                ('not_cached_after_match', {}, blocked),
                ('anchored', {'X-Audit-Bypass': 'prefix' + SECRET + 'suffix'}, blocked)):
                record(f'header.{prefix}.{label}.{port}', lambda port=port, host=host, expected=expected, headers=headers: expect_status(port, host, expected, headers=headers))
    for port in (18880, 18881):
        for label, path, body, expected in (
                ('service_limit_small', '/', b'x' * 512, 200), ('service_limit_large', '/', b'x' * 2048, 413),
                ('location_limit_allows', '/large/', b'x' * 2048, 200), ('location_limit_rejects', '/large/', b'x' * 5000, 413)):
            record(f'body.{label}.{port}', lambda port=port, path=path, body=body, expected=expected: expect_status(port, 'body.audit.test', expected, path, {'Content-Type': 'application/octet-stream'}, body))
    code, body = api('/configs', 'POST', {'service': 'modsec.audit.test', 'type': 'modsec', 'name': 'audit_deny',
                      'data': 'SecRule ARGS:audit_probe "@streq blocked" "id:11001,phase:2,deny,status:403,log,msg:\'Audit contract rule\'"'})
    record('api.custom_modsecurity_rule_create', lambda: need(code == 201, f'{code}: {body}'))
    for port in (18880, 18881):
        record(f'modsecurity.real_rule_blocks.{port}', lambda port=port: await_http(port, 'modsec.audit.test', 403, '/?audit_probe=blocked')[0])
        record(f'modsecurity.normal_request_allowed.{port}', lambda port=port: expect_status(port, 'modsec.audit.test', 200))
    def restart_worker():
        command([*COMPOSE, 'restart', 'bw'])
        await_http(18880, 'modsec.audit.test', 403, '/?audit_probe=blocked')
        return {'enforcement_after_KEEP_CONFIG_ON_RESTART': True}
    record('restart.keep_config_preserves_modsecurity_enforcement', restart_worker)
    code, body = api('/bans', 'POST', {'ip': '8.8.4.4', 'service': 'app.audit.test', 'exp': 120, 'reason': 'audit'})
    record('api.create_service_ban', lambda: need(code == 200, f'{code}: {body}'))
    for port in (18880, 18881):
        record(f'ban.propagates.{port}', lambda port=port: await_http(port, 'app.audit.test', 403)[0])
    command([*COMPOSE, 'stop', 'redis'])
    for port in (18880, 18881):
        record(f'ban.cached_enforcement_with_redis_unreachable.{port}', lambda port=port: expect_status(port, 'app.audit.test', 403))
    command([*COMPOSE, 'start', 'redis'])
    time.sleep(3)
    code, body = api('/bans/unban', 'POST', {'ip': '8.8.4.4', 'service': 'app.audit.test'})
    record('api.remove_service_ban', lambda: need(code == 200, f'{code}: {body}'))
    for port in (18880, 18881):
        record(f'unban.propagates.{port}', lambda port=port: await_http(port, 'app.audit.test', 200)[0])
    def ui_login_logout():
        jar = CookieJar()
        client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        client.addheaders = [('User-Agent', 'BunkerWeb-audit-ui')]
        login_url = 'http://127.0.0.1:18700/login'
        response = client.open(login_url, timeout=15)
        page = response.read().decode()
        match = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', page)
        need(match is not None, f'login page lacked CSRF token, final URL {response.url}')
        data = urllib.parse.urlencode({'username': 'audit-admin', 'password': PASSWORD, 'csrf_token': match.group(1)}).encode()
        response = client.open(login_url, data=data, timeout=15)
        response.read()
        response = client.open('http://127.0.0.1:18700/services', timeout=15)
        response.read()
        need('/login' not in response.url and '/setup' not in response.url, f'authenticated UI refused: {response.url}')
        stale_cookie = '; '.join(c.name + '=' + c.value for c in jar)
        response = client.open('http://127.0.0.1:18700/logout', timeout=15)
        response.read()
        replay = urllib.request.Request('http://127.0.0.1:18700/services', headers={'Cookie': stale_cookie, 'User-Agent': 'BunkerWeb-audit-ui'})
        try:
            response = urllib.request.urlopen(replay, timeout=15)
            response.read()
            need('/login' in response.url or '/setup' in response.url, f'logged-out cookie accepted: {response.url}')
        except urllib.error.HTTPError as exc:
            need(exc.code in (401, 403), f'logout replay unexpected error {exc.code}')
        return {'real_UI_login': True, 'authenticated_services_route': True, 'logged_out_cookie_rejected': True}
    record('ui.login_and_logout_replay', ui_login_logout)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        record('runtime.scenario_execution', run_scenarios)
    finally:
        if (OUT / 'compose.json').exists():
            for label, args in [('compose-logs', ['logs', '--no-color']), ('compose-ps', ['ps', '--all', '--format', 'json'])]:
                try:
                    text = command([*COMPOSE, *args])
                    for secret in (TOKEN, PASSWORD, SECRET):
                        text = text.replace(secret, '[AUDIT-REDACTED]')
                    (OUT / (label + '.log')).write_text(text)
                except Exception as exc:
                    print(f'Diagnostics failed: {exc}', flush=True)
            subprocess.run([*COMPOSE, 'down', '--volumes', '--remove-orphans'], timeout=120, check=False)
            (OUT / 'compose.json').unlink()
        (OUT / 'runtime-results.json').write_text(json.dumps(RESULTS, indent=2))
    return 1 if any(r['status'] == 'FAIL' for r in RESULTS) else 0


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'backend':
        fixture_server()
    else:
        sys.exit(main())
