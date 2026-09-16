"""Installed Flask session interface + real Redis + real filesystem integration.

Run only against the dedicated disposable audit Redis container. No application
methods or Redis commands are mocked. A miniature Flask app isolates this contract;
this is not a substitute for the separately executed full-UI login test.
"""
from datetime import timedelta
import json
import logging
import os
from pathlib import Path
import sys
import tempfile
import time
import traceback

ROOT = Path('/usr/share/bunkerweb')
sys.path[:0] = [str(ROOT / p) for p in ('deps/python', 'ui', 'utils', 'db')]
from flask import Flask, jsonify, request, session
from redis import Redis
from redis.backoff import NoBackoff
from redis.retry import Retry
from app.models.resilient_session import ResilientRedisSessionInterface
from app.models.safe_session_cache import SafeFileSystemCache
from app.utils import revoke_sessions, is_session_revoked

OUT = Path('/audit-results')
OUT.mkdir(exist_ok=True)
LOG = logging.getLogger('session-audit')
logging.basicConfig(level=logging.INFO)
RESULTS = []
HOST = os.environ.get('AUDIT_REDIS_HOST', 'audit-session-redis')
control = Redis(host=HOST, socket_timeout=10, socket_connect_timeout=2, retry=Retry(NoBackoff(), 0))
client = Redis(host=HOST, socket_timeout=0.2, socket_connect_timeout=0.2, retry=Retry(NoBackoff(), 0))


def need(ok, message):
    if not ok:
        raise AssertionError(message)


def record(name, fn):
    start = time.monotonic()
    try:
        result = {'name': name, 'status': 'PASS', 'detail': fn()}
    except Exception as exc:
        result = {'name': name, 'status': 'FAIL', 'error': str(exc), 'traceback': traceback.format_exc()}
    result['seconds'] = round(time.monotonic() - start, 4)
    RESULTS.append(result)
    print(json.dumps(result), flush=True)
    (OUT / 'session-results.json').write_text(json.dumps(RESULTS, indent=2))


def new_app():
    control.config_set('maxmemory', 0)
    control.flushdb()
    app = Flask(__name__)
    app.secret_key = os.urandom(32)
    app.config.update(PERMANENT_SESSION_LIFETIME=timedelta(minutes=5), SESSION_ABSOLUTE_SECONDS=300)
    cache = SafeFileSystemCache(tempfile.mkdtemp(prefix='audit-session-'), threshold=0)
    app.session_interface = ResilientRedisSessionInterface(app, client=client, fallback=cache, logger=LOG)
    @app.get('/state')
    def state():
        revoked = is_session_revoked(session.get('session_id'))
        return jsonify(value=session.get('value'), revoked=revoked)
    @app.post('/state')
    def set_state():
        session['session_id'] = 'audit-session-identity'
        session['value'] = request.json['value']
        session.permanent = True
        if request.json.get('pause'):
            control.execute_command('CLIENT', 'PAUSE', 1800, 'ALL')
        return jsonify(value=session['value'])
    @app.post('/logout')
    def logout():
        error = revoke_sessions([session.get('session_id')])
        session.clear()
        return jsonify(revocation_error=bool(error))
    return app, app.test_client(), cache


def healthy_roundtrip():
    app, browser, cache = new_app()
    need(browser.post('/state', json={'value': 'original'}).status_code == 200, 'initial save failed')
    need(browser.get('/state').json['value'] == 'original', 'healthy read failed')
    return {'redis_persisted': True, 'real_flask_session_lifecycle': True}


def oom_recovery():
    app, browser, cache = new_app()
    browser.post('/state', json={'value': 'original'})
    control.config_set('maxmemory-policy', 'noeviction')
    control.config_set('maxmemory', 1)
    response = browser.post('/state', json={'value': 'newer'})
    need(response.status_code == 200, f'OOM caused HTTP {response.status_code}')
    during = browser.get('/state').json
    control.config_set('maxmemory', 0)
    after = browser.get('/state').json
    need(during['value'] == 'newer' and after['value'] == 'newer', f'OOM recovery lost state: during={during} after={after}')
    return {'during_redis_oom': during['value'], 'after_redis_recovery': after['value']}


def timeout_recovery():
    app, browser, cache = new_app()
    browser.post('/state', json={'value': 'original'})
    response = browser.post('/state', json={'value': 'newer', 'pause': True})
    need(response.status_code == 200, f'timeout caused HTTP {response.status_code}')
    during = browser.get('/state').json
    need(during['value'] == 'newer', f'local fallback lost write: {during}')
    time.sleep(11)
    after = browser.get('/state').json
    print('RECOVERY_OBSERVATION ' + json.dumps({'during_outage': during, 'after_recovery': after}), flush=True)
    need(after['value'] == 'newer', f'recovery reverted newer fallback state to stale Redis payload: during={during}, after={after}')
    return {'during_outage': during, 'after_recovery': after}


def logout_with_unreachable_redis():
    app, browser, cache = new_app()
    browser.post('/state', json={'value': 'authenticated'})
    browser.post('/state', json={'value': 'authenticated-new', 'pause': True})
    old_cookie = browser.get_cookie('session')
    need(old_cookie is not None, 'no session cookie')
    response = browser.post('/logout')
    need(response.status_code == 200, 'logout failed')
    time.sleep(11)
    replay = app.test_client()
    replay.set_cookie('session', old_cookie.value)
    state = replay.get('/state').json
    need(state['value'] is None or state['revoked'], f'logout lost local revocation: {state}')
    return {'stale_cookie_payload_present': state['value'] is not None, 'revocation_blocks_it': state['revoked']}


try:
    need(control.ping(), 'test Redis unavailable')
    record('sessions.healthy_real_redis_roundtrip', healthy_roundtrip)
    record('sessions.oom_fallback_and_recovery_preserve_newer_state', oom_recovery)
    record('sessions.timeout_recovery_preserves_newer_state', timeout_recovery)
    record('sessions.logout_during_outage_rejects_stale_cookie', logout_with_unreachable_redis)
finally:
    control.config_set('maxmemory', 0)
    control.flushdb()
    (OUT / 'session-results.json').write_text(json.dumps(RESULTS, indent=2))
sys.exit(1 if any(item['status'] == 'FAIL' for item in RESULTS) else 0)
