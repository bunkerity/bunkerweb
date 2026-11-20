r"""The package pre-install script backs up an existing /etc/nginx before the package replaces it.

Installing the Linux package overwrote an operator's NGINX configuration with no way back. `beforeInstall.sh`
now copies `/etc/nginx` to `/etc/nginx_backup_<timestamp>` first, and aborts the install when that copy fails.
The real script runs against a temp root, with `/etc/nginx` and the version file moved under it.

Refs #1589.
"""

import shutil

from _t7_helpers import bash, retarget, source


def _run(tmp_path, *, cp_fails=False):
    stubs = tmp_path / "bin"
    stubs.mkdir()
    for tool in ("cp", "date", "cat"):
        stub = stubs / tool
        if tool == "cp" and cp_fails:
            stub.write_text("#!/bin/bash\necho 'cp: simulated failure' >&2\nexit 1\n", encoding="utf-8")
        else:
            stub.write_text(f'#!/bin/bash\nexec {shutil.which(tool)} "$@"\n', encoding="utf-8")
        stub.chmod(0o755)
    script = retarget(source("src/linux/scripts/beforeInstall.sh"), tmp_path, "/etc/nginx", "/usr/share/bunkerweb", "/var/tmp")
    return bash(script, env={"PATH": str(stubs)})


def _backups(tmp_path):
    return sorted((tmp_path / "etc").glob("nginx_backup_*"))


def test_the_existing_nginx_tree_is_copied_byte_for_byte(tmp_path):
    nginx = tmp_path / "etc/nginx"
    (nginx / "conf.d").mkdir(parents=True)
    (nginx / "nginx.conf").write_bytes(b"worker_processes 7;\n")
    (nginx / "conf.d/site.conf").write_bytes(b"server { listen 8081; }\n")

    result = _run(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    backups = _backups(tmp_path)
    assert len(backups) == 1, f"expected one timestamped backup, found {backups}"
    assert (backups[0] / "nginx.conf").read_bytes() == b"worker_processes 7;\n"
    assert (backups[0] / "conf.d/site.conf").read_bytes() == b"server { listen 8081; }\n"
    assert (nginx / "nginx.conf").read_bytes() == b"worker_processes 7;\n", "the live tree must stay in place"


def test_a_host_without_nginx_gets_no_backup(tmp_path):
    """Anti-vacuity: the backup only exists because /etc/nginx did."""
    (tmp_path / "etc").mkdir()

    result = _run(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert _backups(tmp_path) == []


def test_a_failed_backup_aborts_the_install(tmp_path):
    (tmp_path / "etc/nginx").mkdir(parents=True)
    (tmp_path / "etc/nginx/nginx.conf").write_text("x\n", encoding="utf-8")

    result = _run(tmp_path, cp_fails=True)

    assert result.returncode != 0, "the install went on although the safety copy failed"
    assert "Error from command" in result.stdout
