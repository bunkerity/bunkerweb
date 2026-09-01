"""The dedicated bwcli image stays a target of the Scheduler dependency build."""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
DOCKERFILE = ROOT / "src" / "scheduler" / "Dockerfile"
COMPOSE = ROOT / "misc" / "dev" / "docker-compose.bwcli.yml"
RESTORE = ROOT / "src" / "common" / "core" / "backup" / "bwcli" / "restore.py"
DOCS = ROOT / "docs" / "integrations.md"
CHANGELOG = ROOT / "CHANGELOG.md"
WORKFLOWS = ROOT / ".github" / "workflows"


def _target(name):
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    match = re.search(rf"^FROM .+ AS {name}$\n(?P<body>.*?)(?=^FROM |\Z)", dockerfile, re.MULTILINE | re.DOTALL)
    assert match, f"missing Docker target {name}"
    return match.group("body")


def _workflow(name):
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


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


def test_bwcli_target_contains_every_supported_database_client_and_patched_openssl():
    target = _target("bwcli")
    # postgresql-client-18, not the meta-package: the image reaches PGDG for it, and a bare
    # "postgresql-client" would pass by substring even after a revert. On 32-bit the install line
    # resolves to the distribution's client through the architecture gate -- see
    # tests/unit/integrations/test_postgres_client_version.py for both arms.
    for package in ("sqlite3", "mariadb-client", "postgresql-client-18", "openssl"):
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


def test_bwcli_named_target_is_built_and_published_by_every_release_workflow():
    build_jobs = {
        "1.7-dev.yml": ("build-containers",),
        "dev.yml": ("build-containers",),
        "staging.yml": ("build-containers",),
        "release.yml": ("build-containers", "build-containers-arm"),
    }
    build_row = {"image": "bwcli", "dockerfile": "src/scheduler/Dockerfile", "target": "bwcli"}

    for workflow_name, job_names in build_jobs.items():
        workflow = _workflow(workflow_name)
        for job_name in job_names:
            job = workflow["jobs"][job_name]
            assert "bwcli" in job["strategy"]["matrix"]["image"], f"{workflow_name}:{job_name}"
            assert build_row in job["strategy"]["matrix"]["include"], f"{workflow_name}:{job_name}"
            assert job["with"]["TARGET"] == "${{ matrix.target }}", f"{workflow_name}:{job_name}"

    staging_runs = [step.get("run", "") for step in _workflow("staging.yml")["jobs"]["push-images"]["steps"]]
    assert any("bwcli-tests:testing" in run and "bunkerweb-bwcli:testing" in run for run in staging_runs)

    push_row = {"image": "bunkerweb-bwcli", "cache_from": "bwcli", "dockerfile": "src/scheduler/Dockerfile", "target": "bwcli"}
    for workflow_name in ("release.yml",):
        push_job = _workflow(workflow_name)["jobs"]["push-images"]
        assert "bunkerweb-bwcli" in push_job["strategy"]["matrix"]["image"], workflow_name
        assert push_row in push_job["strategy"]["matrix"]["include"], workflow_name
        assert push_job["with"]["TARGET"] == "${{ matrix.target }}", workflow_name

    for workflow_name, action_count in (("container-build.yml", 2), ("push-docker.yml", 1)):
        workflow = _workflow(workflow_name)
        workflow_call = (workflow.get("on") or workflow[True])["workflow_call"]
        assert workflow_call["inputs"]["TARGET"] == {"required": False, "type": "string", "default": ""}
        build_steps = [step for step in workflow["jobs"].values() for step in step["steps"] if "docker/build-push-action@" in step.get("uses", "")]
        assert len(build_steps) == action_count
        assert all(step["with"]["target"] == "${{ inputs.TARGET }}" for step in build_steps)
