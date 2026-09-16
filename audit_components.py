"""Audit-only checks against installed, unmodified BunkerWeb modules.

Runs in a disposable scheduler image. Never point DATABASE_URI at a real database.
All results are expectations, not xfails: reproduced defects remain FAIL.
"""
import importlib.util
import io
import json
import logging
import multiprocessing
import os
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
import time
import traceback

ROOT = Path('/usr/share/bunkerweb')
sys.path[:0] = [str(ROOT / p) for p in ('deps/python', 'utils', 'db', 'gen')]
OUT = Path(os.getenv('AUDIT_OUT', '/audit-results'))
OUT.mkdir(parents=True, exist_ok=True)
RESULTS = []
LOG = logging.getLogger('AUDIT')
logging.basicConfig(level=logging.INFO)


def check(name, fn):
    start = time.monotonic()
    try:
        details = fn()
        item = dict(name=name, status='PASS', details=details)
    except Exception as exc:
        item = dict(name=name, status='FAIL', error=str(exc), traceback=traceback.format_exc())
    item['seconds'] = round(time.monotonic() - start, 4)
    RESULTS.append(item)
    print(json.dumps(item), flush=True)


def need(condition, message):
    if not condition:
        raise AssertionError(message)


def database_checks():
    from Database import Database
    from common_utils import bytes_hash, get_version
    from jobs import Job
    uri = os.environ['DATABASE_URI']
    db = Database(LOG, sqlalchemy_string=uri)
    plugins = [json.loads(p.read_text()) for p in (ROOT / 'core').glob('*/plugin.json')]
    ok, err = db.init_tables([json.loads((ROOT / 'settings.json').read_text()), plugins, [], []])
    need(not err, f'init_tables: {err}')
    need(not db.initialize_db(version=get_version(), integration='Docker'), 'initialize_db failed')
    config = {'MULTISITE': 'yes', 'SERVER_NAME': 'audit.test', 'audit.test_SERVER_NAME': 'audit.test',
              'USE_GZIP': 'no', 'audit.test_USE_GZIP': 'yes'}

    def save_does_not_mutate():
        before = dict(config)
        ret = db.save_config(config, 'api', changed=False)
        need(not isinstance(ret, str), f'save_config: {ret}')
        need(config == before, f'caller config mutated: {config}')
        values = db.get_config()
        need(values.get('audit.test_USE_GZIP') == 'yes', f'service override not effective: {values.get("audit.test_USE_GZIP")}')
        return {'input_preserved': True, 'effective_service_override': 'yes'}
    check('database.save_config_preserves_input_and_service_override', save_does_not_mutate)

    def draft_roundtrip():
        ret = db.save_config(dict(config), 'api', changed=False, draft_settings={'audit.test_USE_GZIP': True})
        need(not isinstance(ret, str), f'draft save: {ret}')
        effective = db.get_config()
        need(effective.get('audit.test_USE_GZIP') == 'no', f'draft leaked into effective config: {effective.get("audit.test_USE_GZIP")}')
        ret = db.save_config(dict(config), 'api', changed=False, draft_settings={'audit.test_USE_GZIP': False})
        need(not isinstance(ret, str), f'activation save: {ret}')
        need(db.get_config().get('audit.test_USE_GZIP') == 'yes', 'activation not effective')
        return {'draft_inherits_global': True, 'activation_persisted': True}
    check('database.raw_draft_effective_value_and_activation', draft_roundtrip)

    def custom_checksum():
        ret = db.save_custom_configs([{'service_id': 'audit.test', 'type': 'server_http', 'name': 'audit_conf',
                                      'data': b'add_header X-Audit value;', 'is_draft': False, 'method': 'api'}], 'api', changed=False)
        need(not ret, f'custom config without checksum failed: {ret}')
        configs = db.get_custom_configs(with_data=True)
        row = next(row for row in configs if row['name'] == 'audit_conf')
        need(row.get('checksum') == bytes_hash(b'add_header X-Audit value;'), f'checksum not populated: {row}')
        return {'computed_checksum': row['checksum']}
    check('database.custom_config_computes_missing_checksum', custom_checksum)

    job = Job(LOG, ROOT / 'core/letsencrypt/jobs/certbot-new.py', db=db, deprecated=True)
    target = Path('/var/cache/bunkerweb/letsencrypt/audit-contract')
    target.mkdir(parents=True, exist_ok=True)

    def regular_cache():
        (target / 'payload.txt').write_text('persistent certificate cache control')
        ok, err = job.cache_dir(target)
        need(ok, f'cache_dir failed: {err}')
        shutil.rmtree(target)
        need(job.restore_cache(), 'restore_cache rejected regular directory')
        need((target / 'payload.txt').read_text() == 'persistent certificate cache control', 'restored bytes differ')
        return {'database_to_filesystem_roundtrip': True}
    check('cache.database_directory_roundtrip_regular_files', regular_cache)

    def reproducible_cache():
        need(job.cache_dir(target)[0], 'first cache write failed')
        first = db.get_job_cache_file(job.job_name, f'folder:{target}.tgz')
        time.sleep(1.1)
        need(job.cache_dir(target)[0], 'second cache write failed')
        second = db.get_job_cache_file(job.job_name, f'folder:{target}.tgz')
        need(first is not None and first == second, 'identical tree changed archive bytes')
        return {'byte_identical_after_delay': True}
    check('cache.repeated_directory_archive_is_byte_reproducible', reproducible_cache)

    def certificate_link_cache():
        archive = target / 'archive/example.test'
        live = target / 'live/example.test'
        archive.mkdir(parents=True, exist_ok=True)
        live.mkdir(parents=True, exist_ok=True)
        (archive / 'fullchain1.pem').write_text('certificate-fixture-content')
        (live / 'fullchain.pem').symlink_to('../../archive/example.test/fullchain1.pem')
        ok, err = job.cache_dir(target)
        need(ok, f'certificate directory not cached: {err}')
        data = db.get_job_cache_file(job.job_name, f'folder:{target}.tgz')
        need(data, 'archive absent from real database')
        with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as tar:
            need(any(m.issym() for m in tar), 'archive did not preserve certificate symlink')
        shutil.rmtree(target)
        restored = job.restore_cache()
        need(restored, 'Job.cache_dir stored a valid relative certificate symlink but Job.restore_cache returned False')
        need((live / 'fullchain.pem').is_symlink(), 'symlink lost')
        need((live / 'fullchain.pem').read_text() == 'certificate-fixture-content', 'certificate target unreadable')
        return {'real_database_roundtrip': True, 'relative_symlink_readable': True}
    check('cache.database_certificate_symlink_roundtrip', certificate_link_cache)
    db.close()


def extraction_safety_checks():
    from cache_restore import restore_directory
    base = Path(tempfile.mkdtemp(prefix='bw-audit-safe-', dir='/var/cache/bunkerweb'))
    target = base / 'published'
    target.mkdir()
    (target / 'old.txt').write_text('last-good')
    def reject_bad(kind):
        payload = io.BytesIO()
        with tarfile.open(fileobj=payload, mode='w:gz') as tar:
            member = tarfile.TarInfo('../escape.txt' if kind == 'traversal' else 'escape')
            if kind == 'absolute-link':
                member.type = tarfile.SYMTYPE
                member.linkname = '/etc/passwd'
            elif kind == 'relative-link':
                member.type = tarfile.SYMTYPE
                member.linkname = '../../outside'
            else:
                member.size = 3
            tar.addfile(member, io.BytesIO(b'bad') if member.isreg() else None)
        try:
            restore_directory(target, payload.getvalue())
        except (ValueError, tarfile.TarError):
            pass
        else:
            raise AssertionError(f'unsafe {kind} archive accepted')
        need((target / 'old.txt').read_text() == 'last-good', 'failed restore destroyed prior directory')
        need(not (base / 'escape.txt').exists(), 'archive escaped extraction target')
        return {'rejected': kind, 'previous_tree_preserved': True}
    for kind in ('traversal', 'absolute-link', 'relative-link'):
        check(f'cache.reject_{kind}_preserve_last_good_tree', lambda kind=kind: reject_bad(kind))
    shutil.rmtree(base)


def lock_checks():
    spec = importlib.util.spec_from_file_location('audit_backup', ROOT / 'core/backup/backup.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    directory = Path(tempfile.mkdtemp(prefix='bw-audit-lock-'))
    module.DB_LOCK_FILE = directory / 'db.lock'
    ctx = multiprocessing.get_context('fork')
    acquired = ctx.Event()
    release = ctx.Event()
    result = ctx.Queue()
    def contender():
        start = time.monotonic()
        module.acquire_db_lock()
        result.put({'wait_seconds': time.monotonic() - start, 'contender_pid': os.getpid()})
        acquired.set()
        release.wait(10)
    module.acquire_db_lock()
    child = ctx.Process(target=contender)
    child.start()
    def live_owner_not_stolen():
        entered = acquired.wait(32)
        details = result.get(timeout=2) if entered else {'contender_did_not_enter': True}
        details['original_holder_pid'] = os.getpid()
        details['original_holder_still_alive'] = True
        print('LOCK_OBSERVATION ' + json.dumps(details), flush=True)
        need(not entered, f'Live owner lock stolen after {details.get("wait_seconds")} real seconds: {details}')
        return details
    check('backup.live_lock_not_stolen_after_30_seconds', live_owner_not_stolen)
    release.set()
    child.join(12)
    if child.is_alive():
        child.terminate()
        child.join(5)
    shutil.rmtree(directory)


if __name__ == '__main__':
    name = sys.argv[1] if len(sys.argv) > 1 else 'sqlite'
    try:
        if name == 'lock':
            lock_checks()
        else:
            check('database.initialize_and_execute_contracts', database_checks)
            extraction_safety_checks()
    finally:
        (OUT / f'components-{name}.json').write_text(json.dumps(RESULTS, indent=2))
    sys.exit(1 if any(r['status'] == 'FAIL' for r in RESULTS) else 0)
