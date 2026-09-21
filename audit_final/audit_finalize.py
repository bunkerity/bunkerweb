"""Final audit pass. Fixture corrections are separate from the opt-in UI patch.

Only AUDIT_UI_PATCH=1 mounts a proposed two-call serialization correction. Every
other application byte remains pinned. Real Redis and two live workers are used.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import audit_runtime as a
import audit_runtime_launch as launch

base_compose = a.build_compose
base_api = a.api
removing_ca = False


def compose():
    config = base_compose()
    config['services']['scheduler']['environment']['DNSBL_LIST'] = 'dnsbl.audit.test'
    if os.getenv('AUDIT_AUX_PLATFORM'):
        for service in ('scheduler', 'api', 'ui', 'backend'):
            config['services'][service]['platform'] = os.environ['AUDIT_AUX_PLATFORM']
    if os.getenv('AUDIT_UI_PATCH') == '1':
        source = Path('src/ui/app/utils.py').read_text()
        assert source.count('flask_flash(message, category)') == 1
        assert source.count('flask_flash(message)') == 1
        corrected = source.replace('flask_flash(message, category)', 'flask_flash(str(message), category)').replace('flask_flash(message)', 'flask_flash(str(message))')
        target = Path('audit-ui-utils-fixed.py').resolve()
        target.write_text(corrected)
        target.chmod(0o644)
        config['services']['ui']['volumes'].append(str(target) + ':/usr/share/bunkerweb/ui/app/utils.py:ro')
        import difflib
        (a.OUT / 'candidate-ui-only.patch').write_text(''.join(difflib.unified_diff(source.splitlines(True), corrected.splitlines(True), fromfile='a/src/ui/app/utils.py', tofile='b/src/ui/app/utils.py')))
    return config


def api(path, method='GET', payload=None, authenticated=True):
    global removing_ca
    if method == 'POST' and path == '/services' and payload:
        payload = dict(payload)
        payload['variables'] = dict(payload.get('variables', {}))
        payload['variables'].pop('DNSBL_LIST', None)
    if method == 'PATCH' and payload and 'MTLS_CA_CERTIFICATE_DATA' in payload.get('variables', {}):
        removing_ca = payload['variables']['MTLS_CA_CERTIFICATE_DATA'] == ''
    if method == 'PATCH' and path == '/services/modsec.audit.test' and payload and 'server_name' in payload:
        before = base_api('/configs?service=modsec.audit.test&with_data=true')
        result = base_api(path, method, payload, authenticated)
        after = base_api('/configs?service=renamed.audit.test&with_data=true')
        old = base_api('/services/modsec.audit.test')
        new = base_api('/services/renamed.audit.test')
        (a.OUT / 'rename-http-evidence.json').write_text(json.dumps({'before': before, 'rename_response': result, 'after': after, 'old_service': old, 'new_service': new}, indent=2))
        return result
    return base_api(path, method, payload, authenticated)


a.build_compose = compose
a.api = api


def boot():
    for component in ('bunkerweb', 'scheduler', 'api', 'ui'):
        ref = f'ghcr.io/bunkerity/{component}-tests:dev'
        subprocess.run(['docker', 'pull', ref], check=True, timeout=180)
        image = json.loads(a.command(['docker', 'image', 'inspect', ref]))
        a.need(image[0]['Config']['Labels'].get('org.opencontainers.image.revision') == a.SHA, 'Image source mismatch: ' + ref)
        (a.OUT / f'image-{component}.json').write_text(json.dumps(image, indent=2))
    (a.OUT / 'variant.json').write_text(json.dumps({'source_sha': a.SHA, 'ui_serialization_patch': os.getenv('AUDIT_UI_PATCH') == '1', 'auxiliary_platform': os.getenv('AUDIT_AUX_PLATFORM'), 'worker_image': os.getenv('AUDIT_WORKER_IMAGE'), 'published': False}, indent=2))
    (a.OUT / 'compose.json').write_text(json.dumps(compose(), indent=2))
    a.command([*a.COMPOSE, 'create', '--no-build', 'scheduler'])
    subprocess.run([*a.COMPOSE, 'up', '-d', '--wait', '--wait-timeout', '500', '--no-build'], check=True, timeout=540)


def browser_scenarios():
    from playwright.sync_api import sync_playwright
    boot()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.set_default_timeout(20000)
        base = 'http://127.0.0.1:18700'
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        def login():
            response = page.goto(base + '/login')
            a.need(response.status == 200, f'Login form HTTP {response.status}')
            page.locator('input[name="username"]').fill('audit-admin')
            page.locator('input[name="password"]').fill(a.PASSWORD)
            with page.expect_response(lambda r: r.request.method == 'POST' and '/login' in r.url) as post:
                page.locator('#login-form button[type="submit"]').click()
            status = post.value.status
            a.need(status in (200, 302, 303), f'Browser login POST returned {status}')
            response = page.goto(base + '/services')
            a.need(response.status == 200 and '/login' not in page.url, f'Authenticated services page failed {response.status}: {page.url}')
            return {'post_status': status, 'authenticated_services': True}
        a.record('browser.login', login)
        if a.RESULTS[-1]['status'] == 'FAIL':
            browser.close()
            return
        for path in ('/', '/services', '/configs', '/plugins', '/jobs', '/reports', '/bans', '/profile', '/global-settings?mode=raw'):
            def navigation(path=path):
                response = page.goto(base + path, wait_until='domcontentloaded')
                a.need(response.status == 200 and '/login' not in page.url, f'Page {path}: {response.status} {page.url}')
                return {'http_status': response.status, 'url': path}
            a.record('browser.navigate.' + path, navigation)
        def raw_creation():
            response = page.goto(base + '/services/new?mode=raw')
            a.need(response.status == 200, f'RAW editor HTTP {response.status}')
            page.wait_for_function('window.ace && document.getElementById("raw-config-editor") && ace.edit("raw-config-editor").session')
            content = 'IS_DRAFT=no\nSERVER_NAME=browser.audit.test\nUSE_REVERSE_PROXY=yes\nREVERSE_PROXY_HOST=http://backend:8080\nREFERRER_POLICY=same-origin\n'
            page.evaluate('(text) => ace.edit("raw-config-editor").setValue(text, -1)', content)
            with page.expect_response(lambda r: r.request.method == 'POST' and '/services/new' in r.url) as saved:
                page.locator('.raw-config-save-btn').click()
            a.need(saved.value.status in (200, 302, 303), f'RAW save HTTP {saved.value.status}')
            for port in (18880, 18881):
                a.await_http(port, 'browser.audit.test', 200)
            code, data = a.api('/services/browser.audit.test')
            a.need(code == 200, f'Browser-created service missing: {code} {data}')
            return {'created_through_browser': True, 'served_by_both_workers': True}
        a.record('browser.raw_create_to_database_scheduler_and_workers', raw_creation)
        def logout():
            stale = context.cookies()
            page.goto(base + '/logout')
            replay = browser.new_context()
            replay.add_cookies(stale)
            check = replay.new_page()
            response = check.goto(base + '/services')
            a.need(response.status in (401, 403) or '/login' in check.url or '/setup' in check.url, f'Stale cookie accepted: {response.status} {check.url}')
            replay.close()
            return {'logged_out_cookie_rejected': True}
        a.record('browser.logout_rejects_replayed_cookie', logout)
        (a.OUT / 'browser-page-errors.json').write_text(json.dumps(errors, indent=2))
        browser.close()


def tls_mode():
    import audit_tls as tls
    original_deny = tls.must_deny
    def settled_deny(port, host, client=None):
        if not removing_ca or host != 'mtls.audit.test' or client != 'client':
            return original_deny(port, host, client)
        started = time.monotonic()
        deadline = started + 100
        consecutive = 0
        observations = []
        while time.monotonic() < deadline:
            # A previously valid client may remain trusted until reload. A client
            # with no certificate must NEVER gain access during that transition.
            original_deny(port, host, None)
            try:
                result = original_deny(port, host, client)
                consecutive += 1
            except AssertionError as exc:
                result = {'pending_reload': str(exc)}
                consecutive = 0
            observations.append({'seconds': round(time.monotonic() - started, 3), **result})
            (a.OUT / f'ca-removal-{port}.json').write_text(json.dumps(observations, indent=2))
            if consecutive == 3:
                return {'denied_after_automatic_reload_seconds': round(time.monotonic() - started, 3), 'three_fresh_connections_denied': True}
            time.sleep(2)
        raise AssertionError('Removed CA remained trusted after 100 seconds of automatic publication')
    tls.must_deny = settled_deny
    try:
        return a.main()
    finally:
        shutil.rmtree(tls.CERTS)


if __name__ == '__main__':
    mode = sys.argv[1]
    if mode == 'tls':
        sys.exit(tls_mode())
    if mode == 'browser':
        a.run_scenarios = browser_scenarios
    elif mode != 'runtime':
        raise SystemExit('Expected runtime, tls or browser')
    sys.exit(a.main())
