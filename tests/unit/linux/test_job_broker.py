"""The Celery broker must stay a dedicated instance, and the worker must actually get enabled.

Both defects these tests pin were silent in production: a shared Redis that the installer
password-protected answered NOAUTH to Celery, and every deferred-start install left
bunkerweb-worker disabled. Nothing crashed in either case — jobs simply stopped running.
"""

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
INSTALLER = ROOT / "misc" / "install-bunkerweb.sh"
POSTINSTALL = ROOT / "src" / "linux" / "scripts" / "postinstall.sh"
WORKER_UNIT = ROOT / "src" / "linux" / "bunkerweb-worker.service"
API_UNIT = ROOT / "src" / "linux" / "bunkerweb-api.service"


def _dry_run(*args):
    result = subprocess.run(
        ["bash", str(INSTALLER), "--dry-run", "--yes", "--no-tui", *args],
        check=True,
        capture_output=True,
        text=True,
        env=os.environ | {"NO_COLOR": "1"},
    )
    return result.stdout


# --- the broker is provisioned, and only where a Celery worker actually runs -------------


@pytest.mark.parametrize("install_type", ["--full", "--manager"])
def test_broker_provisioned_for_worker_bearing_topologies(install_type):
    extra = ["--manager-ip", "10.0.0.5"] if install_type == "--manager" else []
    assert "Job broker: 127.0.0.1:6380 (dedicated, noeviction)" in _dry_run(install_type, *extra)


def test_no_broker_for_data_plane_node():
    # INSTALL_TYPE=worker is an nginx data-plane node, not a Celery worker: no scheduler,
    # so no broker. Getting this backwards would install a stray daemon on every edge node.
    assert "Job broker: n/a (this mode runs no Celery worker)" in _dry_run("--worker", "--manager-ip", "10.0.0.5")


def test_broker_opt_out_flags():
    assert "Job broker: none" in _dry_run("--full", "--no-broker")
    assert "Job broker: supplied URL" in _dry_run("--full", "--broker-url", "redis://:pw@10.0.0.9:6379/0")


def test_broker_url_rejects_non_redis_scheme():
    result = subprocess.run(
        ["bash", str(INSTALLER), "--dry-run", "--yes", "--no-tui", "--full", "--broker-url", "http://nope"],
        capture_output=True,
        text=True,
        env=os.environ | {"NO_COLOR": "1"},
    )
    assert result.returncode != 0
    assert "must be a redis:// or rediss:// URL" in result.stdout + result.stderr


# --- the broker's config is the whole point: noeviction, loopback, no secret in the unit ---


def test_broker_conf_is_noeviction_and_loopback():
    text = INSTALLER.read_text(encoding="utf-8")
    for directive, value in (
        ("maxmemory-policy", "noeviction"),
        ("bind", "127.0.0.1"),
        ("appendonly", "no"),
    ):
        assert f'_redis_conf_set "$BROKER_CONF" "{directive}" "{value}"' in text, f"broker {directive} must be {value}"


def test_broker_password_never_reaches_the_unit_file():
    text = INSTALLER.read_text(encoding="utf-8")
    unit = text.split("cat > \"$BROKER_UNIT\" <<'EOF'")[1].split("EOF")[0]
    # 0644 unit → --requirepass on ExecStart would expose the secret through `ps`.
    assert "requirepass" not in unit
    assert "$pw" not in unit
    assert "ExecStart=" in unit


def test_broker_url_is_written_to_variables_env():
    # Both bunkerweb-worker.sh and bunkerweb-api.sh source variables.env *before* their
    # `: "${CELERY_BROKER_URL:=...}"` default, so this one write covers both components.
    assert 'set_config_kv "$target" "CELERY_BROKER_URL" "redis://:${pw}@127.0.0.1:${port}/0"' in INSTALLER.read_text(encoding="utf-8")


# --- defect 1: the worker has to be enabled on the deferred-start legs -------------------


def test_worker_enabled_on_deferred_full_install():
    # configure_full_config runs on every leg that exported SERVICE_SCHEDULER=no (--redis,
    # external DB, CrowdSec, ...), which is exactly when postinstall skips its enable block.
    text = INSTALLER.read_text(encoding="utf-8")
    body = text.split("configure_full_config() {")[1].split("\n}\n")[0]
    assert "svc_restart_or_start bunkerweb-worker" in body


def test_worker_enabled_on_manager_install():
    text = INSTALLER.read_text(encoding="utf-8")
    body = text.split("configure_manager_api_defaults() {")[1].split("\n}\n")[0]
    assert "systemctl enable --now bunkerweb-worker" in body


def test_worker_drained_before_package_upgrade():
    assert "for svc in bunkerweb bunkerweb-api bunkerweb-ui bunkerweb-worker bunkerweb-scheduler; do" in INSTALLER.read_text(encoding="utf-8")


# --- wiring on the packaged side --------------------------------------------------------


def test_postinstall_prefers_the_dedicated_broker_unit():
    # Falling through to the distro unit would pick the WAF datastore — password-protected
    # and evicting, i.e. exactly the server a job queue must not use.
    assert "for unit in bunkerweb-broker redis-server valkey redis; do" in POSTINSTALL.read_text(encoding="utf-8")


@pytest.mark.parametrize("unit", [WORKER_UNIT, API_UNIT])
def test_units_order_after_the_broker(unit):
    text = unit.read_text(encoding="utf-8")
    assert "bunkerweb-broker.service" in text
    # Wants=, never Requires=: a missing broker must not block startup, Celery retries.
    assert "Requires=bunkerweb-broker.service" not in text
    assert "After=bunkerweb-broker.service" in text
