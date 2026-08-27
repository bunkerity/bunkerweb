from pathlib import Path
from subprocess import run

ROOT = Path(__file__).resolve().parents[3]
ENTRYPOINT = ROOT / "tests" / "misc" / "scripts" / "redis-entrypoint.sh"


def _run_replica(tmp_path: Path, **env: str):
    redis_server = tmp_path / "redis-server"
    redis_server.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\"\n", encoding="utf-8")
    redis_server.chmod(0o755)
    hostname = tmp_path / "hostname"
    hostname.write_text("#!/bin/sh\nprintf '%s\\n' redis-slave-1\n", encoding="utf-8")
    hostname.chmod(0o755)

    return run(
        [ENTRYPOINT],
        env={
            "PATH": f"{tmp_path}:/usr/bin:/bin",
            "REDIS_DATA_DIR": str(tmp_path / "data"),
            "REDIS_REPLICATION_MODE": "slave",
            "REDIS_MASTER_HOST": "svc-redis-master.redis.svc.cluster.local",
            "REDIS_MASTER_PORT_NUMBER": "6379",
            **env,
        },
        capture_output=True,
        check=True,
        text=True,
    )


def test_replica_announces_its_kubernetes_nodeport(tmp_path: Path):
    result = _run_replica(
        tmp_path,
        REDIS_REPLICA_ANNOUNCE_IP="192.168.49.2",
        REDIS_REPLICA_ANNOUNCE_PORT_BASE="30380",
    )

    assert result.stdout.splitlines()[1:] == [
        "--port",
        "6379",
        "--dir",
        str(tmp_path / "data"),
        "--protected-mode",
        "no",
        "--replicaof",
        "svc-redis-master.redis.svc.cluster.local",
        "6379",
        "--replica-announce-ip",
        "192.168.49.2",
        "--replica-announce-port",
        "30381",
    ]


def test_replica_uses_no_announce_flags_outside_kubernetes(tmp_path: Path):
    result = _run_replica(tmp_path)

    assert "--replica-announce-ip" not in result.stdout
    assert "--replica-announce-port" not in result.stdout
