"""Refuse to start an instance that was enrolled and has lost its credential.

``api.lua:is_allowed_token`` answers ONLY to the stored credential once an instance is enrolled --
the global ``API_TOKEN`` stops being a key to it. So an enrolled instance that comes back without
its credential file is not degraded, it is unreachable: the control plane keeps dialing it with a
credential it no longer holds and every push is refused with nothing anywhere to read. The PO ruling
of 2026-09-02 makes that shape fatal at boot, with one message that says how to recover.

The local signal is a marker written next to the credential the first time the instance boots
holding one. It cannot see the database, so this is the honest bound: it fires when the data volume
survived and the credential did not, and it is self-healing for instances enrolled before it
existed. A container recreated with *no* volume at all loses the marker too and boots as a fresh
instance -- documented in ``report-L-A3.md``, not silently assumed here.

Exercised by running the real ``utils.sh`` functions, because the bug this guards against is a shell
one: a guard placed before ``redeem_enrollment_code`` would refuse a boot that carries a valid code.
"""

import json
import os
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
UTILS = ROOT / "src" / "common" / "helpers" / "utils.sh"


def _run(snippet: str, credential: Path, marker: Path, **env) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", "-c", f'source "$UTILS"; {snippet}'],
        capture_output=True,
        text=True,
        env={
            "PATH": "/usr/bin:/bin:/usr/local/bin",
            "UTILS": str(UTILS),
            "INSTANCE_CREDENTIAL_FILE": str(credential),
            "INSTANCE_ENROLLED_MARKER": str(marker),
            **env,
        },
    )


def _guard(tmp_path, **env) -> subprocess.CompletedProcess:
    return _run('check_instance_credential "TEST"', tmp_path / "instance-credential.json", tmp_path / "instance-enrolled", **env)


class TestAFreshInstanceIsUnaffected:
    def test_no_marker_and_no_credential_boots(self, tmp_path):
        """Every instance that never enrolled looks exactly like this. Refusing here would make the
        guard a boot failure for the entire installed base."""
        result = _guard(tmp_path)
        assert result.returncode == 0, result.stderr
        assert not (tmp_path / "instance-enrolled").exists()


class TestAnEnrolledInstanceLeavesAMarker:
    def test_a_usable_credential_writes_the_marker(self, tmp_path):
        (tmp_path / "instance-credential.json").write_text(json.dumps({"credential": "abc", "code_fingerprint": "x"}))

        assert _guard(tmp_path).returncode == 0
        assert (tmp_path / "instance-enrolled").is_file()

    def test_it_is_written_for_an_instance_enrolled_before_the_marker_existed(self, tmp_path):
        """Self-healing on upgrade: 1.7 instances enrolled by an earlier build have a credential and
        no marker, and must gain one rather than stay unprotected forever."""
        (tmp_path / "instance-credential.json").write_text(json.dumps({"credential": "abc"}))
        assert _guard(tmp_path).returncode == 0

        (tmp_path / "instance-credential.json").unlink()
        assert _guard(tmp_path).returncode == 1


class TestALostCredentialIsFatal:
    def test_marker_without_a_credential_refuses_to_start(self, tmp_path):
        (tmp_path / "instance-enrolled").write_text("enrolled")

        result = _guard(tmp_path)

        assert result.returncode == 1
        output = result.stdout + result.stderr
        assert "was enrolled but its credential is gone" in output

    def test_the_message_names_the_recovery(self, tmp_path):
        """One message, and it has to be actionable: what happened, why it is broken, and the exact
        way out. An operator reading it must not need to find this file."""
        (tmp_path / "instance-enrolled").write_text("enrolled")

        result = _guard(tmp_path)
        output = result.stdout + result.stderr

        assert "INSTANCE_ENROLLMENT_CODE" in output
        assert "/instances/<hostname>/enroll" in output
        # The escape hatch, for an operator who removed the credential on purpose. Without it the
        # only documented way out of the refusal is to enroll an instance you wanted unenrolled.
        assert str(tmp_path / "instance-enrolled") in output

    def test_the_message_does_not_blame_a_cause_it_cannot_detect(self, tmp_path):
        """`/var/lib/bunkerweb` is a symlink to `/data/lib` in the container image, so a container
        recreated with no data volume loses the MARKER too and never reaches this branch. Naming
        that case here sends the operator to check a volume that is not the problem."""
        (tmp_path / "instance-enrolled").write_text("enrolled")

        result = _guard(tmp_path)

        assert "persistent /data volume" not in result.stdout + result.stderr

    @pytest.mark.parametrize("content", ("", "not json", "{}", '{"credential": ""}', '["credential"]'))
    def test_an_unusable_credential_file_counts_as_missing(self, tmp_path, content):
        """A file that exists but carries no credential is the same outage: api.lua refuses every
        request rather than fall back to API_TOKEN."""
        (tmp_path / "instance-enrolled").write_text("enrolled")
        (tmp_path / "instance-credential.json").write_text(content)

        assert _guard(tmp_path).returncode == 1


class TestAnUnknownNeverRefuses:
    """The guard's worst failure is a FALSE refusal: it would take a healthy instance off the air.

    So only one answer stops a boot -- "there is no credential in this file". A file we are not
    allowed to read, or a missing interpreter, leaves the question open, and an open question boots.
    """

    def test_an_unreadable_credential_file_does_not_refuse(self, tmp_path):
        """An older install left the file root-owned and the service now runs as nginx. Telling that
        operator to re-enroll is the wrong fix for a chmod."""
        marker = tmp_path / "instance-enrolled"
        credential = tmp_path / "instance-credential.json"
        marker.write_text("enrolled")
        credential.write_text(json.dumps({"credential": "still-here"}))
        credential.chmod(0o000)
        if os.access(credential, os.R_OK):  # running as root: the mode cannot be enforced here
            pytest.skip("cannot make a file unreadable as root")

        result = _guard(tmp_path)

        assert result.returncode == 0, result.stdout + result.stderr
        assert "Refusing to start" not in result.stdout + result.stderr

    def test_no_python_interpreter_does_not_refuse(self, tmp_path):
        """`get_python_bin` falls back to a path that may not exist. A guard that cannot run its own
        check must not conclude the credential is gone."""
        marker = tmp_path / "instance-enrolled"
        credential = tmp_path / "instance-credential.json"
        marker.write_text("enrolled")
        credential.write_text(json.dumps({"credential": "still-here"}))

        # `get_python_bin` probes /usr/local/bin, /usr/bin and /bin directly, so PATH cannot hide an
        # interpreter -- override the resolver instead, which is the contract under test anyway.
        result = _run(
            'get_python_bin() { echo /nonexistent/python3; }; check_instance_credential "TEST"',
            credential,
            marker,
        )

        assert result.returncode == 0, result.stdout + result.stderr
        assert "Refusing to start" not in result.stdout + result.stderr


class _EnrollHandler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802 -- BaseHTTPRequestHandler's own naming
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        payload = json.dumps({"credential": f"minted-for-{body['hostname']}"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


@pytest.fixture
def control_plane():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _EnrollHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


class TestANewCodeRecovers:
    def test_redeeming_a_code_then_checking_boots_and_marks(self, tmp_path, control_plane):
        """The recovery the message prescribes, end to end, in the order the entrypoint runs it.
        Ordering is the point: a guard placed BEFORE the redemption would refuse the very boot that
        carries the operator's new code."""
        (tmp_path / "instance-enrolled").write_text("enrolled")
        credential = tmp_path / "instance-credential.json"

        result = _run(
            'redeem_enrollment_code "TEST" && check_instance_credential "TEST"',
            credential,
            tmp_path / "instance-enrolled",
            API_URL=control_plane,
            INSTANCE_ENROLLMENT_CODE="a-fresh-code",
            INSTANCE_ENROLLMENT_HOSTNAME="bw-1",
        )

        assert result.returncode == 0, result.stdout + result.stderr
        assert json.loads(credential.read_text())["credential"] == "minted-for-bw-1"


class TestTheCallersRunItAfterTheRedemption:
    @pytest.mark.parametrize(
        "script",
        ("src/bw/entrypoint.sh", "src/linux/scripts/start.sh"),
    )
    def test_both_boot_paths_guard_and_exit(self, script):
        source = (ROOT / script).read_text(encoding="utf-8")
        assert "check_instance_credential" in source, f"{script} does not guard a lost credential"
        assert source.index("redeem_enrollment_code") < source.index("check_instance_credential"), f"{script} guards before it redeems"
        guard = source.split("check_instance_credential", 1)[1]
        assert "exit 1" in guard.split("fi")[0], f"{script} logs the refusal but keeps booting"
