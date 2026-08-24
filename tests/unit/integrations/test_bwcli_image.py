"""The dedicated bwcli image stays a target of the Scheduler dependency build."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DOCKERFILE = ROOT / "src" / "scheduler" / "Dockerfile"
COMPOSE = ROOT / "misc" / "dev" / "docker-compose.bwcli.yml"
RESTORE = ROOT / "src" / "common" / "core" / "backup" / "bwcli" / "restore.py"
DOCS = ROOT / "docs" / "integrations.md"
CHANGELOG = ROOT / "CHANGELOG.md"


def _target(name):
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    match = re.search(rf"^FROM .+ AS {name}$\n(?P<body>.*?)(?=^FROM |\Z)", dockerfile, re.MULTILINE | re.DOTALL)
    assert match, f"missing Docker target {name}"
    return match.group("body")


def test_bwcli_target_reuses_the_scheduler_builder_and_is_non_root():
    target = _target("bwcli")
    assert "RUN umask" not in target
    assert "COPY --from=builder" in target
    assert "useradd -u 101 -g bwcli" in target
    assert "USER bwcli:bwcli" in target
    assert 'ENTRYPOINT ["bwcli"]' in target
    assert "BWCLI_REQUIRE_BACKUP_MOUNT=yes" in target
    assert 'VOLUME ["/var/lib/bunkerweb", "/var/tmp/bunkerweb", "/tmp"]' in target


def test_default_build_stays_the_unnamed_scheduler_target():
    final_from = [line.strip() for line in DOCKERFILE.read_text(encoding="utf-8").splitlines() if line.startswith("FROM ")][-1]
    assert " AS " not in final_from.upper(), f"the final target must stay the unnamed Scheduler image: {final_from}"


def test_bwcli_target_contains_every_supported_database_client():
    target = _target("bwcli")
    for package in ("sqlite3", "mariadb-client", "postgresql-client"):
        assert package in target
    assert "COPY src/common/core core" in DOCKERFILE.read_text(encoding="utf-8")
    for path in ("/etc/bunkerweb/plugins", "/etc/bunkerweb/pro/plugins"):
        assert path in target


def test_compose_example_is_an_optional_one_shot_tool():
    assert COMPOSE.is_file(), "missing dedicated bwcli Compose example"
    compose = COMPOSE.read_text(encoding="utf-8")
    assert "\n    image:" not in compose
    assert "target: bwcli" in compose
    assert "profiles: [tools]" in compose
    assert "./backups:/var/lib/bunkerweb/backups" in compose
    assert "docker compose -f docker-compose.bwcli.yml --profile tools run --rm bwcli" in compose
    assert "- /var/tmp/bunkerweb" in compose
    assert "- /tmp" in compose


def test_restore_safety_backup_lives_on_persisted_state():
    target = _target("bwcli")
    restore = RESTORE.read_text(encoding="utf-8")
    assert "BWCLI_RESTORE_SAFETY_DIRECTORY=/var/lib/bunkerweb/backups/restore-safety" in target
    assert 'getenv("BWCLI_RESTORE_SAFETY_DIRECTORY"' in restore


def test_bwcli_capabilities_is_documented_for_local_development():
    docs = DOCS.read_text(encoding="utf-8")
    assert "bwcli capabilities" in docs
    for variable in ("BWCLI_API_URL", "BWCLI_TIMEOUT", "BWCLI_OUTPUT", "BWCLI_RESTORE_SAFETY_DIRECTORY"):
        assert variable in docs
    assert "dedicated" in CHANGELOG.read_text(encoding="utf-8").lower()
