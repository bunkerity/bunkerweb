"""Real TLS/HTTP2/HTTP3/mTLS traffic against two isolated BunkerWeb workers.

Uses only disposable locally generated certificates. This does not exploit a CVE;
it verifies protocol compatibility and enforcement on the selected worker image.
"""
import asyncio
from http.client import HTTPResponse
import json
import os
from pathlib import Path
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import time

import audit_runtime as audit
import audit_runtime_launch

BASE_COMPOSE = audit.build_compose
CERTS = Path(tempfile.mkdtemp(prefix='bw-audit-certificates-'))
audit.OUT = Path('audit-results/tls').resolve()
audit.COMPOSE = ['docker', 'compose', '--project-name', 'bw-audit-runtime', '--file', str(audit.OUT / 'compose.json')]


def compose():
    config = BASE_COMPOSE()
    for worker, port in (('bw', 18443), ('bw2', 18444)):
        config['services'][worker]['ports'].extend([f'127.0.0.1:{port}:8443/tcp', f'127.0.0.1:{port}:8443/udp'])
    return config


def openssl(*args):
    audit.command(['openssl', *args], cwd=CERTS)


def certificates():
    openssl('req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', 'server.key', '-out', 'server.pem', '-days', '2',
            '-subj', '/CN=tls.audit.test', '-addext', 'subjectAltName=DNS:tls.audit.test,DNS:mtls.audit.test,DNS:missing.audit.test')
    openssl('req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', 'ca.key', '-out', 'ca.pem', '-days', '2',
            '-subj', '/CN=Disposable audit client CA')
    openssl('req', '-newkey', 'rsa:2048', '-nodes', '-keyout', 'client.key', '-out', 'client.csr', '-subj', '/CN=Audit client')
    (CERTS / 'client.ext').write_text('extendedKeyUsage=clientAuth\n')
    openssl('x509', '-req', '-in', 'client.csr', '-CA', 'ca.pem', '-CAkey', 'ca.key', '-CAcreateserial',
            '-out', 'client.pem', '-days', '1', '-extfile', 'client.ext')
    openssl('req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', 'rogue.key', '-out', 'rogue.pem', '-days', '1',
            '-subj', '/CN=Untrusted audit client', '-addext', 'extendedKeyUsage=clientAuth')


def tls_request(port, host, client=None, version=None, headers=None, path='/'):
    context = ssl.create_default_context(cafile=str(CERTS / 'server.pem'))
    if version is not None:
        context.minimum_version = version
        context.maximum_version = version
    if client:
        context.load_cert_chain(str(CERTS / f'{client}.pem'), str(CERTS / f'{client}.key'))
    with socket.create_connection(('127.0.0.1', port), timeout=8) as raw:
        with context.wrap_socket(raw, server_hostname=host) as stream:
            values = {'Host': host, 'User-Agent': 'BunkerWeb-audit-tls', 'Connection': 'close'}
            values.update(headers or {})
            wire = f'GET {path} HTTP/1.1\r\n' + ''.join(f'{key}: {value}\r\n' for key, value in values.items()) + '\r\n'
            stream.sendall(wire.encode())
            response = HTTPResponse(stream)
            response.begin()
            return response.status, response.read(), stream.version()


def await_tls(port, host, client=None, expected=200):
    last = None
    for _ in range(50):
        try:
            last = tls_request(port, host, client=client)
            if last[0] == expected:
                return last
        except (OSError, ssl.SSLError) as exc:
            last = str(exc)
        time.sleep(2)
    raise AssertionError(f'TLS publication failed {host}:{port}; last={str(last)[:250]}')


def must_deny(port, host, client=None):
    try:
        status, content, protocol = tls_request(port, host, client=client)
    except ssl.SSLError as exc:
        return {'tls_rejected': str(exc)}
    audit.need(status in (400, 401, 403, 495, 496), f'mTLS unexpectedly returned {status} for {host} client={client}')
    return {'http_status': status, 'client': client}


def http2(port):
    output = audit.command(['curl', '--silent', '--show-error', '--noproxy', '*', '--max-time', '10', '--http2',
            '--cacert', str(CERTS / 'server.pem'), '--resolve', f'tls.audit.test:{port}:127.0.0.1',
            '-w', '\n%{http_code} %{http_version}', f'https://tls.audit.test:{port}/'])
    payload, _, meta = output.rpartition('\n')
    audit.need(meta == '200 2', f'HTTP/2 not negotiated successfully: {meta}')
    audit.need(json.loads(payload).get('fixture') == 'audit-backend', 'HTTP/2 did not reach upstream')
    return {'status': 200, 'actual_http_version': '2'}


async def http3_request(port, path='/'):
    from aioquic.asyncio import connect, QuicConnectionProtocol
    from aioquic.h3.connection import H3Connection, H3_ALPN
    from aioquic.h3.events import HeadersReceived, DataReceived
    from aioquic.quic.configuration import QuicConfiguration
    class Protocol(QuicConnectionProtocol):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.http = H3Connection(self._quic)
            self.finished = asyncio.get_running_loop().create_future()
            self.status = None
            self.body = bytearray()
        def quic_event_received(self, event):
            for item in self.http.handle_event(event):
                if isinstance(item, HeadersReceived):
                    self.status = int(dict(item.headers).get(b':status', b'0'))
                if isinstance(item, DataReceived):
                    self.body.extend(item.data)
                if getattr(item, 'stream_ended', False) and not self.finished.done():
                    self.finished.set_result((self.status, bytes(self.body)))
        async def request(self):
            stream = self._quic.get_next_available_stream_id()
            self.http.send_headers(stream, [(b':method', b'GET'), (b':scheme', b'https'),
                (b':authority', b'tls.audit.test'), (b':path', path.encode()), (b'user-agent', b'BunkerWeb-audit-h3')], end_stream=True)
            self.transmit()
            return await asyncio.wait_for(self.finished, 8)
    config = QuicConfiguration(is_client=True, alpn_protocols=H3_ALPN, server_name='tls.audit.test', idle_timeout=8)
    config.load_verify_locations(cafile=str(CERTS / 'server.pem'))
    async with connect('127.0.0.1', port, configuration=config, create_protocol=Protocol) as protocol:
        return await protocol.request()


def http3(port, path='/', expected=200):
    status, body = asyncio.run(asyncio.wait_for(http3_request(port, path), 12))
    audit.need(status == expected, f'HTTP/3 status {status}, expected {expected}')
    if expected == 200:
        audit.need(json.loads(body).get('fixture') == 'audit-backend', 'HTTP/3 did not reach upstream')
    return {'status': status, 'actual_http_version': '3'}


def await_variable(worker, name, value):
    expected = f'{name}={value}'
    for _ in range(40):
        try:
            audit.command([*audit.COMPOSE, 'exec', '-T', worker, 'grep', '-Fxq', expected, '/etc/nginx/variables.env'])
            return
        except subprocess.CalledProcessError:
            time.sleep(2)
    raise AssertionError('Updated variable was not published: ' + name)


def scenarios():
    certificates()
    for component in ('bunkerweb', 'scheduler', 'api', 'ui'):
        image = f'ghcr.io/bunkerity/{component}-tests:dev'
        subprocess.run(['docker', 'pull', image], check=True, timeout=180)
        data = json.loads(audit.command(['docker', 'image', 'inspect', image]))
        audit.need(data[0]['Config']['Labels'].get('org.opencontainers.image.revision') == audit.SHA, 'Image source mismatch')
        (audit.OUT / f'image-{component}.json').write_text(json.dumps(data, indent=2))
    (audit.OUT / 'compose.json').write_text(json.dumps(compose(), indent=2))
    audit.command([*audit.COMPOSE, 'create', '--no-build', 'scheduler'])
    subprocess.run([*audit.COMPOSE, 'up', '-d', '--wait', '--wait-timeout', '500', '--no-build'], check=True, timeout=540)
    common = {'USE_CUSTOM_SSL': 'yes', 'CUSTOM_SSL_CERT_PRIORITY': 'data',
              'CUSTOM_SSL_CERT_DATA': (CERTS / 'server.pem').read_text(), 'CUSTOM_SSL_KEY_DATA': (CERTS / 'server.key').read_text(),
              'HTTP2': 'yes', 'HTTP3': 'yes', 'SSL_PROTOCOLS': 'TLSv1.2 TLSv1.3', 'USE_MODSECURITY': 'yes'}
    for host, settings in [('tls.audit.test', {}), ('mtls.audit.test', {'USE_MTLS': 'yes', 'MTLS_CA_CERTIFICATE_PRIORITY': 'data',
                             'MTLS_CA_CERTIFICATE_DATA': (CERTS / 'ca.pem').read_text()}),
                            ('missing.audit.test', {'USE_MTLS': 'yes', 'MTLS_CA_CERTIFICATE_PRIORITY': 'data'})]:
        code, result = audit.api('/services', 'POST', {'server_name': host, 'variables': common | settings})
        audit.need(code == 200, f'TLS service creation failed: {code}: {result}')
    for port in (18443, 18444):
        audit.record(f'tls.ready.{port}', lambda port=port: await_tls(port, 'tls.audit.test')[0])
        for version in (ssl.TLSVersion.TLSv1_2, ssl.TLSVersion.TLSv1_3):
            def protocol_check(port=port, version=version):
                status, body, actual = tls_request(port, 'tls.audit.test', version=version)
                audit.need(status == 200, f'TLS request failed {status}')
                return {'negotiated': actual, 'status': status}
            audit.record(f'tls.{version.name}.{port}', protocol_check)
        audit.record(f'http2.real_request.{port}', lambda port=port: http2(port))
        audit.record(f'http3.real_request.{port}', lambda port=port: http3(port))
        audit.record(f'mtls.trusted_client.{port}', lambda port=port: await_tls(port, 'mtls.audit.test', 'client')[0])
        audit.record(f'mtls.no_client_denied.{port}', lambda port=port: must_deny(port, 'mtls.audit.test'))
        audit.record(f'mtls.untrusted_client_denied.{port}', lambda port=port: must_deny(port, 'mtls.audit.test', 'rogue'))
        audit.record(f'mtls.initial_missing_ca_fails_closed.{port}', lambda port=port: must_deny(port, 'missing.audit.test', 'client'))
        def strip_spoofed(port=port):
            status, body, _ = tls_request(port, 'tls.audit.test', headers={'X-SSL-Client-Verify': 'SUCCESS'})
            values = {k.lower(): v for k, v in json.loads(body)['headers'].items()}
            audit.need(status == 200 and 'x-ssl-client-verify' not in values, f'Client spoof reached upstream: {values}')
            return {'spoofed_mtls_header_removed': True}
        audit.record(f'mtls.client_spoof_stripped_without_mtls.{port}', strip_spoofed)
    code, result = audit.api('/configs', 'POST', {'service': 'tls.audit.test', 'type': 'modsec', 'name': 'tls_audit_rule',
        'data': 'SecRule ARGS:audit_probe "@streq blocked" "id:11002,phase:2,deny,status:403,log,msg:\'TLS audit rule\'"'})
    audit.need(code == 201, f'Cannot create HTTP3 ModSecurity test rule: {code} {result}')
    for port in (18443, 18444):
        for _ in range(40):
            if tls_request(port, 'tls.audit.test', path='/?audit_probe=blocked')[0] == 403:
                break
            time.sleep(2)
        audit.record(f'http3.modsecurity_rule_enforced.{port}', lambda port=port: http3(port, '/?audit_probe=blocked', 403))
    def invalid_ca_preserves_good():
        audit.patch('mtls.audit.test', {'MTLS_CA_CERTIFICATE_DATA': 'audit-invalid-ca'})
        for worker, port in (('bw', 18443), ('bw2', 18444)):
            await_variable(worker, 'mtls.audit.test_MTLS_CA_CERTIFICATE_DATA', 'audit-invalid-ca')
            audit.need(tls_request(port, 'mtls.audit.test', 'client')[0] == 200, 'Invalid CA replacement lost last-good trust')
            must_deny(port, 'mtls.audit.test', 'rogue')
        return {'last_good_CA_retained_on_both_workers': True}
    audit.record('mtls.invalid_ca_replacement_preserves_last_good_material', invalid_ca_preserves_good)
    def removal_fails_closed():
        audit.patch('mtls.audit.test', {'MTLS_CA_CERTIFICATE_DATA': ''})
        for worker, port in (('bw', 18443), ('bw2', 18444)):
            await_variable(worker, 'mtls.audit.test_MTLS_CA_CERTIFICATE_DATA', '')
            must_deny(port, 'mtls.audit.test', 'client')
        return {'removed_CA_no_longer_trusted': True}
    audit.record('mtls.ca_removal_does_not_allow_unverified_clients', removal_fails_closed)


audit.run_scenarios = scenarios
if __name__ == '__main__':
    try:
        sys.exit(audit.main())
    finally:
        shutil.rmtree(CERTS)
