"""Audit fixture corrections and extra scenarios; no production code is patched."""
from http.client import HTTPConnection
import json
import os
import sys
import time
import audit_runtime as audit

original_compose = audit.build_compose
original_scenarios = audit.run_scenarios


def control_api(path, method='GET', payload=None, authenticated=True):
    """Management requests originate locally and must not impersonate WAF client IPs."""
    headers = {'Content-Type': 'application/json', 'User-Agent': 'BunkerWeb-audit-control'}
    if authenticated:
        headers['Authorization'] = 'Bearer ' + audit.TOKEN
    conn = HTTPConnection('127.0.0.1', 18888, timeout=12)
    try:
        conn.request(method, path, body=json.dumps(payload).encode() if payload is not None else None, headers=headers)
        response = conn.getresponse()
        code, raw = response.status, response.read()
    finally:
        conn.close()
    try:
        data = json.loads(raw)
    except ValueError:
        data = raw.decode(errors='replace')[:1200]
    # Stop a broken setup at its cause, rather than spending many minutes polling
    # services which were never created. Negative-auth GET tests still see their status.
    if authenticated and method in ('POST', 'PATCH', 'PUT') and not 200 <= code < 300:
        raise AssertionError(f'Management API {method} {path} failed {code}: {data}')
    return code, data


def compose():
    config = original_compose()
    config['services']['backend']['healthcheck'] = {
        'test': ['CMD', 'python3', '-c', "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/', timeout=2).read()"],
        'interval': '2s', 'timeout': '3s', 'retries': 30, 'start_period': '3s'
    }
    worker_image = os.getenv('AUDIT_WORKER_IMAGE')
    if worker_image:
        for worker in ('bw', 'bw2'):
            config['services'][worker]['image'] = worker_image
    return config


def extra_scenarios():
    original_scenarios()
    def custom_headers():
        audit.patch('app.audit.test', {'REVERSE_PROXY_HEADERS': 'X-Audit-First   one;X-Audit-Second    two'})
        last = None
        for _ in range(40):
            code, _, data = audit.http(18880, host='app.audit.test')
            if code == 200:
                last = json.loads(data)
                headers = {k.lower(): v for k, v in last.get('headers', {}).items()}
                if headers.get('x-audit-first') == 'one' and headers.get('x-audit-second') == 'two':
                    return {'repeated_whitespace_rendered_and_forwarded': True}
            time.sleep(2)
        raise AssertionError(f'Custom headers not applied: {last}')
    audit.record('proxy.repeated_whitespace_header_lists_reach_upstream', custom_headers)

    def concurrent_audit():
        storage = '/var/log/bunkerweb/audit-concurrent'
        for worker in ('bw', 'bw2'):
            audit.command([*audit.COMPOSE, 'exec', '-T', worker, 'mkdir', '-p', storage])
        audit.patch('modsec.audit.test', {'MODSECURITY_SEC_AUDIT_LOG_TYPE': 'Concurrent',
                                         'MODSECURITY_SEC_AUDIT_LOG_STORAGE_DIR': storage,
                                         'MODSECURITY_SEC_AUDIT_LOG': '/var/log/bunkerweb/audit-index.log',
                                         'MODSECURITY_SEC_AUDIT_ENGINE': 'On'})
        seen = {}
        for _ in range(40):
            for worker, port in (('bw', 18880), ('bw2', 18881)):
                audit.http(port, '/?audit_probe=blocked', host='modsec.audit.test')
                text = audit.command([*audit.COMPOSE, 'exec', '-T', worker, 'sh', '-c',
                                      "find /var/log/bunkerweb/audit-concurrent -type f | head -5"])
                if text.strip():
                    seen[worker] = text.strip().splitlines()
            if len(seen) == 2:
                return {'real_audit_files_per_instance': seen}
            time.sleep(2)
        raise AssertionError(f'Concurrent audit produced no per-request files on every worker: {seen}')
    audit.record('modsecurity.concurrent_audit_writes_real_per_request_files', concurrent_audit)

    def rename_keeps_config():
        code, body = audit.api('/services/modsec.audit.test', 'PATCH', {'server_name': 'renamed.audit.test'})
        audit.need(code == 200, f'rename failed {code}: {body}')
        for port in (18880, 18881):
            audit.await_http(port, 'renamed.audit.test', 403, '/?audit_probe=blocked')
        code, data = audit.api('/configs?service=renamed.audit.test&with_data=true')
        audit.need(code == 200, f'cannot read renamed configs: {code} {data}')
        audit.need(any(row.get('name') == 'audit_deny' for row in data.get('configs', [])), f'custom config lost during rename: {data}')
        old, _ = audit.api('/services/modsec.audit.test')
        audit.need(old == 404, f'old service unexpectedly retained: {old}')
        return {'custom_config_retained': True, 'renamed_rule_enforced_on_both_workers': True}
    audit.record('api.service_rename_preserves_custom_config_and_enforcement', rename_keeps_config)


audit.api = control_api
audit.build_compose = compose
audit.run_scenarios = extra_scenarios
if __name__ == '__main__':
    sys.exit(audit.main())
