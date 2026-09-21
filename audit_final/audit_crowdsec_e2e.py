"""Real private CrowdSec 1.8 LAPI, BunkerWeb API, scheduler, Lua and two workers."""
import json
import subprocess
import sys
import time

import audit_runtime as a
import audit_finalize as final

base_compose = final.compose

def compose():
    config = base_compose()
    config['services']['crowdsec'] = {
        'image': 'crowdsecurity/crowdsec:v1.8.0',
        'environment': {'DISABLE_ONLINE_API': 'true', 'DISABLE_AGENT': 'true'},
        'volumes': ['crowdsec-config:/etc/crowdsec', 'crowdsec-data:/var/lib/crowdsec/data'],
        'restart': 'no'
    }
    config['volumes'].update({'crowdsec-config': {}, 'crowdsec-data': {}})
    return config

final.compose = compose

def cscli(*args):
    return a.command([*a.COMPOSE, 'exec', '-T', 'crowdsec', 'cscli', *args])


def scenarios():
    final.boot()
    last = ''
    for _ in range(60):
        try:
            last = cscli('lapi', 'status')
            break
        except subprocess.CalledProcessError:
            time.sleep(2)
    else:
        raise AssertionError('Private CrowdSec LAPI did not become ready')
    key = cscli('bouncers', 'add', 'audit-bouncer', '-o', 'raw').strip()
    a.need(len(key) >= 32 and '\n' not in key, 'Unexpected bouncer-key CLI output')
    a.SECRET = key
    cscli('machines', 'add', 'audit-manager', '--password', a.PASSWORD, '--file', '/tmp/audit-manager.yaml')
    (a.OUT / 'crowdsec-image.json').write_text(a.command(['docker', 'image', 'inspect', 'crowdsecurity/crowdsec:v1.8.0']))
    for mode in ('live', 'stream'):
        code, body = a.api('/services', 'POST', {'server_name': 'cs-' + mode + '.audit.test', 'variables': {
            'USE_CROWDSEC': 'yes', 'CROWDSEC_API': 'http://crowdsec:8080', 'CROWDSEC_API_KEY': key,
            'CROWDSEC_MANAGEMENT_LOGIN': 'audit-manager', 'CROWDSEC_MANAGEMENT_PASSWORD': a.PASSWORD,
            'CROWDSEC_MODE': mode, 'CROWDSEC_UPDATE_FREQUENCY': '2', 'CROWDSEC_CACHE_EXPIRATION': '1'
        }})
        a.need(code == 200, 'CrowdSec service creation failed')
        for port in (18880, 18881):
            a.record(f'crowdsec.{mode}.clean_request.{port}', lambda port=port, mode=mode: a.await_http(port, 'cs-' + mode + '.audit.test', 200)[0])
    cscli('decisions', 'add', '--ip', '8.8.4.4', '--duration', '5m', '--reason', 'isolated-audit')
    for mode in ('live', 'stream'):
        for port in (18880, 18881):
            a.record(f'crowdsec.{mode}.real_decision_enforced.{port}', lambda port=port, mode=mode: a.await_http(port, 'cs-' + mode + '.audit.test', 403)[0])
    a.record('crowdsec.disabled_service_is_not_cross_contaminated', lambda: a.expect_status(18880, 'bootstrap.audit.test', 200))
    code, connections = a.api('/crowdsec')
    a.need(code == 200, f'Cannot inspect CrowdSec connections: {code} {connections}')
    (a.OUT / 'crowdsec-connections.json').write_text(json.dumps(connections, indent=2))
    a.need(not connections.get('errors'), f'Connection discovery errors: {connections.get("errors")}')
    selected = [row for row in connections['connections'] if any('cs-live.audit.test' == host for host in row.get('services', []))]
    a.need(len(selected) == 2, f'Expected one connection on each worker: {connections}')
    first_id = selected[0]['id']
    decision_id = None
    for index, row in enumerate(selected):
        connection = row['id']
        def decisions(connection=connection):
            code, data = a.api(f'/crowdsec/{connection}/decisions?ip=8.8.4.4')
            a.need(code == 200 and data.get('total', 0) > 0, f'Decision lookup failed: {code} {data}')
            a.need(any(item['value'] == '8.8.4.4' for item in data['decisions']), 'Selected decision missing')
            return {'count': data['total'], 'decision_ids': [item['id'] for item in data['decisions']]}
        a.record(f'crowdsec.management.decisions.worker{index}', decisions)
        if index == 0:
            code, data = a.api(f'/crowdsec/{connection}/decisions?ip=8.8.4.4')
            if code == 200 and data.get('decisions'):
                decision_id = data['decisions'][0]['id']
        def investigate(connection=connection):
            code, data = a.api(f'/crowdsec/{connection}/ips/8.8.4.4')
            a.need(code == 200 and not data.get('errors'), f'Investigation failed: {code} {data}')
            a.need(data.get('decisions'), 'Investigation omitted active decision')
            return {'decisions': len(data['decisions']), 'alerts': len(data.get('alerts', [])), 'reports': len(data.get('reports', [])), 'errors': data.get('errors')}
        a.record(f'crowdsec.management.investigation.worker{index}', investigate)
        def allowlists(connection=connection):
            code, data = a.api(f'/crowdsec/{connection}/allowlists')
            a.need(code == 200 and isinstance(data.get('allowlists'), list), f'Allowlist inspection failed: {code} {data}')
            code, match = a.api(f'/crowdsec/{connection}/allowlists/check?ip=198.51.100.7')
            a.need(code == 200 and match.get('allowlisted') is False, f'Negative allowlist check failed: {code} {match}')
            return {'listed': len(data['allowlists']), 'negative_match_correct': True}
        a.record(f'crowdsec.management.allowlists.worker{index}', allowlists)
    if decision_id is not None:
        body = {'scope': 'Ip', 'value': '8.8.4.4', 'decision_type': 'ban'}
        def mismatched_selection():
            code, data = a.api(f'/crowdsec/{first_id}/decisions/{decision_id}', 'DELETE', body | {'value': '8.8.8.8'})
            a.need(code == 409, f'Mismatched selection was not rejected: {code} {data}')
            return {'http_status': code}
        a.record('crowdsec.management.mismatched_delete_is_rejected', mismatched_selection)
        def remove():
            code, data = a.api(f'/crowdsec/{first_id}/decisions/{decision_id}', 'DELETE', body)
            a.need(code == 200 and data.get('removed') is True, f'Exact decision removal failed: {code} {data}')
            return {'removed': True, 'propagation': data.get('propagation')}
        a.record('crowdsec.management.exact_delete', remove)
        for mode in ('live', 'stream'):
            for port in (18880, 18881):
                a.record(f'crowdsec.{mode}.deletion_propagates.{port}', lambda port=port, mode=mode: a.await_http(port, 'cs-' + mode + '.audit.test', 200)[0])
    def management_missing_credentials():
        for mode in ('live', 'stream'):
            a.patch('cs-' + mode + '.audit.test', {'CROWDSEC_MANAGEMENT_LOGIN': '', 'CROWDSEC_MANAGEMENT_PASSWORD': ''})
        last = None
        for _ in range(40):
            status, rows = a.api('/crowdsec')
            current = [row for row in rows.get('connections', []) if 'cs-live.audit.test' in row.get('services', [])]
            if current:
                last = a.api(f'/crowdsec/{current[0]["id"]}/allowlists')
                if last[0] == 403:
                    status, read = a.api(f'/crowdsec/{current[0]["id"]}/decisions')
                    a.need(status == 200, 'Bouncer read access broken without management credentials')
                    return {'management_denied': 403, 'bouncer_reads_work': True}
            time.sleep(2)
        raise AssertionError(f'Management permission boundary not observed: {last}')
    a.record('crowdsec.management.absent_credentials_restrict_only_management', management_missing_credentials)


a.run_scenarios = scenarios
if __name__ == '__main__':
    sys.exit(a.main())
