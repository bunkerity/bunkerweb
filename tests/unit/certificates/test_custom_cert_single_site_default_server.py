"""`custom-cert.py` must not drop a single-site service that is called ``default-server``.

The job's environment is `db.get_config(global_only=False, ...)` (`src/worker/tasks.py`), i.e.
`config_read` — the one reader made **method-aware** on purpose, so that an operator's own
`default-server` row survives in `SERVER_NAME` under `MULTISITE=no` (the reserved pseudo-service is
multisite-only and does not exist there). The job then stripped that name from `all_domains`
method-blind, which emptied the roster, fired the ``if not all_domains: sys_exit()`` guard, and
never reached the per-service ``USE_CUSTOM_SSL`` branch: the operator's configured certificate was
silently ignored and the internal self-signed leaf served in its place.

Same defect and same rule as `Templator.__init__`'s strip (lane DS-B5): **strip the reserved id
unless nothing else remains** — not a plain `MULTISITE` gate, which fixes the only-name case and
breaks the alias one (the three guards have to agree on which name the single block is, because that
name is the cache directory `customcert.lua` reads).

Before DS-B5 this was masked: the Templator emptied `SERVER_NAME` too, so the deployment rendered no
server block at all and there was nothing to serve a wrong certificate to.

The whole module body is executed here, not just its definitions: the strip lives in the body, so
`test_default_server_cert.py`'s AST filter (imports/defs/assignments only) cannot reach it.
"""

import ast
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest

from test_default_server_cert import make_pair  # sibling module, same directory

ROOT = Path(__file__).resolve().parents[3]
JOB_PATH = ROOT / "src" / "common" / "core" / "customcert" / "jobs" / "custom-cert.py"


def run_job(monkeypatch, *, cached: bool = False, **environment):
    """Execute the job end to end against a mocked `Job`; return (the mock, the exit code).

    ``cached=True`` makes every ``cache_hash`` answer a digest, i.e. the default server already
    serves an override -- the only state from which clearing the settings reaches the removal
    branch rather than its "nothing to do" early return.
    """
    # The body runs the job's own `sys_path.append` loop, which the AST filter in
    # `test_default_server_cert.py` drops. Rebinding the list keeps those three
    # `/usr/share/bunkerweb/...` entries out of the rest of the pytest process -- empty on a dev box,
    # real inside the BunkerWeb image, and `pytest-randomly` means whoever collects next is arbitrary.
    monkeypatch.setattr(sys, "path", list(sys.path))
    for name in (
        "SERVER_NAME",
        "MULTISITE",
        "DISABLE_DEFAULT_SERVER",
        "USE_CUSTOM_SSL",
        "CUSTOM_SSL_CERT_DATA",
        "CUSTOM_SSL_KEY_DATA",
        "DEFAULT_SERVER_SSL_CERT_DATA",
        "DEFAULT_SERVER_SSL_KEY_DATA",
    ):
        monkeypatch.delenv(name, raising=False)
    for name, value in environment.items():
        monkeypatch.setenv(name, value)

    job_mock = Mock()
    job_mock.cache_hash.return_value = b"cached" if cached else None
    job_mock.cache_file.return_value = (True, "")
    job_mock.del_cache.return_value = (True, "")
    job_mock.db.import_certificate.return_value = ("", None)

    jobs_module = ModuleType("jobs")
    jobs_module.Job = Mock(return_value=job_mock)
    logger_module = ModuleType("logger")
    logger_mock = Mock()
    logger_module.getLogger = Mock(return_value=logger_mock)
    # The job's LOGGER, handed back on the Job mock so a caller can assert on what the operator is
    # told without changing this helper's return shape.
    job_mock.test_logger = logger_mock

    module = ModuleType("bw_custom_cert_executed")
    module.__dict__["__file__"] = str(JOB_PATH)
    tree = ast.parse(JOB_PATH.read_text(encoding="utf-8"), filename=str(JOB_PATH))
    with patch.dict(sys.modules, {"jobs": jobs_module, "logger": logger_module}):
        with pytest.raises(SystemExit) as exited:
            exec(compile(tree, str(JOB_PATH), "exec"), module.__dict__)  # noqa: S102
    return job_mock, exited.value.code


@pytest.fixture
def pair():
    return make_pair("default-server")


class TestTheSingleSiteRosterKeepsTheName:
    def test_the_per_service_branch_is_reached(self, monkeypatch, pair):
        """The regression: the certificate is processed for `default-server` instead of the job
        exiting on an empty roster. `import_certificate` is the observable end of that branch."""
        cert_pem, key_pem = pair
        job_mock, _ = run_job(
            monkeypatch,
            SERVER_NAME="default-server",
            MULTISITE="no",
            USE_CUSTOM_SSL="yes",
            CUSTOM_SSL_CERT_DATA=cert_pem.decode(),
            CUSTOM_SSL_KEY_DATA=key_pem.decode(),
        )
        assert job_mock.db.import_certificate.called
        assert job_mock.db.import_certificate.call_args.kwargs["name"] == "default-server"

    def test_it_agrees_with_the_templator_when_an_alias_is_present(self, monkeypatch):
        """The gate has to be the SAME shape as `Templator.__init__`'s, not a flat `if multisite`.

        Single-site renders ONE block whose service id is the FIRST token of `SERVER_NAME`, and the
        Templator strips the reserved id whenever other names remain — so `variables.env` says
        `app.example.com` and `customcert.lua` reads
        `/var/cache/bunkerweb/customcert/app.example.com/`. A job that keeps the id here would take
        `all_domains[0]` = `default-server` and cache where nothing ever looks: the certificate is
        silently ignored again, one case over.

        The reserved id is FIRST in `SERVER_NAME` here on purpose. Reversed, the job picks
        `app.example.com` either way, so the test would stay green under a plain `MULTISITE` gate and
        prove nothing — this order is the one that separates the two rules.
        """
        cert_pem, key_pem = make_pair("app.example.com")
        job_mock, _ = run_job(
            monkeypatch,
            SERVER_NAME="default-server app.example.com",
            MULTISITE="no",
            USE_CUSTOM_SSL="yes",
            CUSTOM_SSL_CERT_DATA=cert_pem.decode(),
            CUSTOM_SSL_KEY_DATA=key_pem.decode(),
        )
        assert job_mock.db.import_certificate.call_args.kwargs["name"] == "app.example.com"
        assert {call.kwargs.get("service_id") for call in job_mock.cache_file.call_args_list} == {"app.example.com"}

    def test_an_ordinary_single_site_name_is_unaffected(self, monkeypatch):
        """The control: the branch was always reached for any other name, and still is."""
        cert_pem, key_pem = make_pair("app.example.com")
        job_mock, _ = run_job(
            monkeypatch,
            SERVER_NAME="app.example.com",
            MULTISITE="no",
            USE_CUSTOM_SSL="yes",
            CUSTOM_SSL_CERT_DATA=cert_pem.decode(),
            CUSTOM_SSL_KEY_DATA=key_pem.decode(),
        )
        assert job_mock.db.import_certificate.call_args.kwargs["name"] == "app.example.com"

    def test_multisite_still_strips_the_reserved_row(self, monkeypatch):
        """The other control, and the reason the fix is a gate and not a deletion: in multisite the
        id IS the reserved pseudo-service, it has no per-service certificate of its own, and it must
        stay out of the roster the loop manages."""
        cert_pem, key_pem = make_pair("app.example.com")
        job_mock, _ = run_job(
            monkeypatch,
            SERVER_NAME="app.example.com default-server",
            MULTISITE="yes",
            **{
                "app.example.com_USE_CUSTOM_SSL": "yes",
                "app.example.com_CUSTOM_SSL_CERT_DATA": cert_pem.decode(),
                "app.example.com_CUSTOM_SSL_KEY_DATA": key_pem.decode(),
                "default-server_USE_CUSTOM_SSL": "yes",
            },
        )
        managed = [call.kwargs["name"] for call in job_mock.db.import_certificate.call_args_list]
        assert managed == ["app.example.com"]


def logged(job_mock, level: str) -> str:
    """Every `LOGGER.<level>(...)` message the run emitted, joined."""
    return "\n".join(str(call.args[0]) for call in getattr(job_mock.test_logger, level).call_args_list)


class TestTheOverrideTellsTheOperatorWhenItCannotBeServed:
    """`http.conf` includes `default-server-http.conf` only under `MULTISITE=yes`,
    `DISABLE_DEFAULT_SERVER=yes` or `IS_LOADING=yes`. A plain single-site deployment therefore has no
    default server block: the one configured service's own block is NGINX's implicit default and
    `ssl_certificate_default` never runs. The job still caches the material -- an operator can flip
    either switch without re-supplying it -- but reporting "the override was applied ... are now
    served" there is false, and it is exactly what
    `tests/core/customcert.yml:default_server_override_is_served_for_an_unknown_sni` proved by going
    red on the single-site Docker arm (CI run 34054359264).
    """

    def _run(self, monkeypatch, **environment):
        # `unknown.test` covers no configured service, so the coalescence refusal (which would
        # short-circuit before the message under test) does not fire.
        cert_pem, key_pem = make_pair("unknown.test")
        return run_job(
            monkeypatch,
            SERVER_NAME="app.example.com",
            USE_CUSTOM_SSL="no",
            DEFAULT_SERVER_SSL_CERT_DATA=cert_pem.decode(),
            DEFAULT_SERVER_SSL_KEY_DATA=key_pem.decode(),
            **environment,
        )

    def test_single_site_warns_instead_of_claiming_the_override_is_served(self, monkeypatch):
        job_mock, code = self._run(monkeypatch, MULTISITE="no")

        warning = logged(job_mock, "warning")
        assert "CANNOT be served" in warning
        assert "DISABLE_DEFAULT_SERVER=yes" in warning
        assert "MULTISITE=yes" in warning
        # The false claim is gone, not merely duplicated.
        assert "are now served the certificate" not in logged(job_mock, "info")
        # Still cached, still shipped: exit 1 is the only code that sends the cache to the instances.
        assert {call.args[0] for call in job_mock.cache_file.call_args_list} == {
            "default-server-cert.pem",
            "default-server-key.pem",
        }
        assert code == 1

    def test_multisite_reports_the_override_as_applied(self, monkeypatch):
        job_mock, code = self._run(monkeypatch, MULTISITE="yes")

        assert "are now served the certificate for unknown.test" in logged(job_mock, "info")
        assert "CANNOT be served" not in logged(job_mock, "warning")
        assert code == 1

    def test_single_site_with_the_default_server_rendered_reports_it_as_applied(self, monkeypatch):
        """`DISABLE_DEFAULT_SERVER=yes` renders the block (it refuses the request INSIDE it, after
        the handshake), so the override is genuinely served there and the warning must not fire."""
        job_mock, code = self._run(monkeypatch, MULTISITE="no", DISABLE_DEFAULT_SERVER="yes")

        assert "are now served the certificate for unknown.test" in logged(job_mock, "info")
        assert "CANNOT be served" not in logged(job_mock, "warning")
        assert code == 1

    def test_the_removal_message_does_not_promise_the_internal_leaf_either(self, monkeypatch):
        """The sibling caller. Clearing the override where no default server block is rendered does
        not bring the internal leaf back -- the configured service's own certificate is what answers
        an unknown name, before and after. `cache_hash` returns a digest so the branch runs the
        removal rather than the "nothing to do" early return."""
        job_mock, _ = run_job(monkeypatch, cached=True, SERVER_NAME="app.example.com", USE_CUSTOM_SSL="no", MULTISITE="no")

        info = logged(job_mock, "info")
        assert "never served on this single-site deployment" in info
        assert "served the internal self-signed certificate again" not in info

    def test_the_removal_message_is_unchanged_where_the_block_exists(self, monkeypatch):
        job_mock, _ = run_job(monkeypatch, cached=True, SERVER_NAME="app.example.com", USE_CUSTOM_SSL="no", MULTISITE="yes")

        info = logged(job_mock, "info")
        assert "served the internal self-signed certificate again" in info
        assert "never served on this single-site deployment" not in info
