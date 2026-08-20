"""Checks the Datalog run-limit handling of the Biscuit guard.

biscuit-rust authorizes under a wall-clock budget that defaults to 1 ms and reports blowing it as
the same AuthorizationError a real policy denial raises. An honest token authorizes in ~0.01 ms,
but a CPU-starved host still overran 1 ms often enough to turn valid tokens into 401s. The guard
fixes that by raising *only* max_time; max_facts and max_iterations stay at their defaults because
those are the dimensions a token's own content drives.

That distinction is the point of these tests. Biscuit attenuation is offline: any holder of any
valid token can append a block with no private key and explode the fact/iteration limits, raising
the identical top-level message. So a run-limit abort is not evidence of a busy host, and must be
denied like any other bad credential rather than reported as transient.

Ported from dev's `src/api/tests/test_biscuit_run_limit.py` (a72deb504). 1.7 has no
`src/api/tests/`, and this cannot live in the main unit suite: it imports the API's `app` package,
while `tests/unit/ui/conftest.py` relies on `import app` resolving uniquely to `src/ui/app`. There
is no by-path escape hatch either -- `biscuit.py` imports `..config`, `..utils` and `.common`
relatively, so it has to be imported as part of its package. Hence a lane of its own, in its own
interpreter. See `tests/unit/api_app/README.md`.

Run it with:

    BW_API_APP_LANE=1 .venv-unit/bin/python -m pytest tests/unit/api_app
"""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from os import environ
from pathlib import Path
from sys import path as sys_path
from tempfile import NamedTemporaryFile
from time import perf_counter
from types import SimpleNamespace
from unittest import TestCase, main

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys_path[:0] = [
    str(_REPO_ROOT / "src" / "api"),
    str(_REPO_ROOT / "src" / "common" / "utils"),
    str(_REPO_ROOT / "src" / "common" / "db"),
]

if "SETTINGS_YAML_FILE" not in environ:
    _stub = NamedTemporaryFile("w", suffix=".yml", delete=False)  # noqa: SIM115 - must outlive import
    _stub.write("{}\n")
    _stub.close()
    environ["SETTINGS_YAML_FILE"] = _stub.name

from biscuit_auth import AuthorizationError, AuthorizerBuilder, Biscuit, BiscuitBuilder, BlockBuilder, Check, Fact, KeyPair, Policy  # noqa: E402
from fastapi import HTTPException  # noqa: E402

# get_version() reads /usr/share/bunkerweb/VERSION, which only exists in the image. biscuit.py
# binds it by value at import, so patch it here first and let the guard and the test agree.
import common_utils  # type: ignore # noqa: E402

VERSION = "0.0.0-test"
common_utils.get_version = lambda: VERSION

# biscuit.py instantiates its guard at import time, which reads the public key from
# /var/lib/bunkerweb. Point that constant at a throwaway key so the module imports off-box.
import app.utils as api_utils  # noqa: E402

_KEYPAIR = KeyPair()
_key_file = NamedTemporaryFile("w", delete=False)  # noqa: SIM115 - must outlive import
_key_file.write(repr(_KEYPAIR.public_key))
_key_file.close()
api_utils.BISCUIT_PUBLIC_KEY_FILE = Path(_key_file.name)

import app.auth.biscuit as biscuit_mod  # noqa: E402
from app.auth.biscuit import guard  # noqa: E402

# What the guard must NOT relax: these bound the work a token's own Datalog can demand.
_DEFAULTS = AuthorizerBuilder().limits()

EXPECTED_MAX_TIME = timedelta(milliseconds=100)


class RecordingBuilder:
    """Delegates to a real AuthorizerBuilder, recording the limits the guard installs and how many
    times it authorizes. Nothing is stubbed out, so the guard runs against real biscuit Datalog."""

    installed_limits: list = []
    builds: list = []

    def __init__(self) -> None:
        self._inner = AuthorizerBuilder()

    def set_limits(self, limits):
        RecordingBuilder.installed_limits.append(limits)
        return self._inner.set_limits(limits)

    def build(self, token):
        RecordingBuilder.builds.append(token)
        return self._inner.build(token)

    def __getattr__(self, name):
        return getattr(self._inner, name)


@contextmanager
def recording():
    RecordingBuilder.installed_limits = []
    RecordingBuilder.builds = []
    original = biscuit_mod.AuthorizerBuilder
    biscuit_mod.AuthorizerBuilder = RecordingBuilder
    try:
        yield RecordingBuilder
    finally:
        biscuit_mod.AuthorizerBuilder = original


def make_token(with_version: bool = True, privileged: bool = True) -> str:
    """A real, signed token that satisfies phase 1 (version, TTL, client IP) and phase 2 (admin)."""
    facts = "time({now}); client_ip({ip});"
    if with_version:
        facts = "version({version}); " + facts
    if privileged:
        facts += " admin(true);"
    return BiscuitBuilder(facts, {"version": VERSION, "now": datetime.now(timezone.utc), "ip": "127.0.0.1"}).build(_KEYPAIR.private_key).to_base64()


def cross_product(width: int, extra_body: str = "") -> str:
    """A rule whose body is a 4-way self-join over `width` facts: width**4 candidate tuples, which
    exhausts max_facts/max_iterations regardless of how generous the wall clock is."""
    facts = "".join(f"h({i});" for i in range(width))
    return f"{facts} k($a,$b,$c,$d) <- h($a), h($b), h($c), h($d){extra_body};"


def make_single_block_hostile_token(extra_body: str = "") -> str:
    """A token whose *authority* block carries the explosion, so it passes the block-count guard and
    still reaches the authorizer. An attacker cannot mint this (it needs the private key); it exists
    so the run-limit handling stays under test independently of that guard."""
    facts = "version({version}); time({now}); client_ip({ip}); admin(true); " + cross_product(12, extra_body)
    return BiscuitBuilder(facts, {"version": VERSION, "now": datetime.now(timezone.utc), "ip": "127.0.0.1"}).build(_KEYPAIR.private_key).to_base64()


def attenuate(token_b64: str, code: str) -> str:
    """Append a block to an already-signed token. Biscuit attenuation is offline and needs no
    private key, which is exactly why a run-limit abort cannot be read as 'the host was busy'."""
    block = BlockBuilder()
    block.add_code(code)
    return Biscuit.from_base64(token_b64, _KEYPAIR.public_key).append(block).to_base64()


def make_request(token: str, path: str = "/instances/ping", method: str = "GET"):
    return SimpleNamespace(
        scope={"path": path},
        url=SimpleNamespace(path=path),
        method=method,
        headers={"Authorization": f"Bearer {token}"},
        client=SimpleNamespace(host="127.0.0.1"),
    )


class TestAuthorizerLimits(TestCase):
    """The raised budget must actually reach the authorizer, and must raise nothing else."""

    def test_guard_installs_the_raised_time_budget_in_both_phases(self):
        with recording() as rec:
            self.assertIsNone(guard(make_request(make_token())))
        self.assertEqual(len(rec.installed_limits), 2, "both phases must install limits")
        for phase, limits in enumerate(rec.installed_limits, start=1):
            with self.subTest(phase=phase):
                self.assertEqual(limits.max_time, EXPECTED_MAX_TIME)

    def test_guard_leaves_the_token_driven_limits_at_their_defaults(self):
        # max_facts/max_iterations are what a hostile token inflates. Raising them would trade a
        # false 401 for an unbounded authorize, so they must stay put.
        with recording() as rec:
            guard(make_request(make_token()))
        for phase, limits in enumerate(rec.installed_limits, start=1):
            with self.subTest(phase=phase):
                self.assertEqual(limits.max_facts, _DEFAULTS.max_facts)
                self.assertEqual(limits.max_iterations, _DEFAULTS.max_iterations)


class TestGenuineVerdicts(TestCase):
    """Real, library-produced verdicts keep their status and are reached in one attempt."""

    def test_valid_token_is_authorized(self):
        self.assertIsNone(guard(make_request(make_token())))

    def test_phase1_denial_returns_401(self):
        # No version fact: a genuine phase 1 check failure.
        with recording() as rec:
            with self.assertRaises(HTTPException) as ctx:
                guard(make_request(make_token(with_version=False)))
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(len(rec.builds), 1, "a denial must not be retried")

    def test_phase2_denial_returns_403(self):
        # Passes phase 1, but carries no admin/api_perm fact for /instances/ping.
        with recording() as rec:
            with self.assertRaises(HTTPException) as ctx:
                guard(make_request(make_token(privileged=False)))
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(len(rec.builds), 2, "phase 1 passes, phase 2 denies once")


class TestAttenuatedTokensAreRejected(TestCase):
    """Attenuation needs no private key and the run limits cannot bound it, because the clock is
    only consulted between Datalog iterations. So a token carrying more than the single block this
    product mints is refused before any Datalog runs at all."""

    def test_multi_block_token_is_rejected_before_any_datalog(self):
        hostile = attenuate(make_token(), cross_product(12))
        with recording() as rec:
            started = perf_counter()
            with self.assertRaises(HTTPException) as ctx:
                guard(make_request(hostile))
            elapsed = perf_counter() - started
        self.assertEqual(ctx.exception.status_code, 401)
        # The whole point: no authorizer is ever built, so the crafted join never runs. This is
        # what turns seconds of blocked event loop into the parse we had already paid for.
        self.assertEqual(len(rec.builds), 0, "an attenuated token must never reach the authorizer")
        self.assertLess(elapsed, 1.0)

    def test_every_legitimately_minted_token_is_single_block(self):
        # The guard is only safe while this holds. If a mint ever starts appending a block, this
        # fails here instead of locking every user out in production.
        for label, token in (("privileged", make_token()), ("fine-grained", make_token(privileged=False))):
            with self.subTest(mint=label):
                self.assertEqual(Biscuit.from_base64(token, _KEYPAIR.public_key).block_count(), 1)

    def test_attenuated_admin_claim_cannot_grant_privilege(self):
        # A longer clock must never buy privilege. Two independent reasons it cannot, asserted
        # separately so the property survives if either mechanism is removed.
        elevated = attenuate(make_token(privileged=False), "admin(true);")

        # 1. The guard denies the request. Any 4xx will do here: which mechanism refused it is the
        # business of the tests above, this one only cares that elevation never succeeds.
        with self.assertRaises(HTTPException) as ctx:
            guard(make_request(elevated))
        self.assertIn(ctx.exception.status_code, (401, 403))

        # 2. And with that guard bypassed, biscuit's own block scoping still refuses to let a fact
        # appended after signing satisfy an authorizer policy. This is the property that has to
        # hold regardless of block counts or time budgets.
        az = AuthorizerBuilder()
        az.add_fact(Fact("operation({operation})", {"operation": "read"}))
        az.add_fact(Fact("resource_type({rt})", {"rt": "instances"}))
        az.add_fact(Fact("required_perm({perm})", {"perm": "instances_read"}))
        az.add_policy(Policy("allow if admin(true)"))
        az.add_policy(Policy('allow if api_perm($rt, "*", $perm), required_perm($perm), resource_type($rt)'))
        biscuit_mod._raise_time_budget(az)
        with self.assertRaises(AuthorizationError):
            az.build(Biscuit.from_base64(elevated, _KEYPAIR.public_key)).authorize()


class TestRunLimitIsNotTransient(TestCase):
    """Should a run-limit abort ever reach a verdict, it is a denial: never a 5xx, never retried.
    Driven with single-block tokens so this stays under test independently of the guard above."""

    def _assert_denied_not_transient(self, token: str, expected_status: int, expected_builds: int):
        with recording() as rec:
            started = perf_counter()
            with self.assertRaises(HTTPException) as ctx:
                guard(make_request(token))
            elapsed = perf_counter() - started
        self.assertEqual(ctx.exception.status_code, expected_status)
        # The two halves of "not transient": not a 5xx, and no invitation to come back.
        self.assertLess(ctx.exception.status_code, 500)
        self.assertIsNone((ctx.exception.headers or {}).get("Retry-After"))
        # One authorize per phase. Retrying would multiply what a hostile token costs the server.
        self.assertEqual(len(rec.builds), expected_builds)
        self.assertLess(elapsed, 5.0, "denial must be prompt")

    def test_run_limit_in_phase1_denies_401(self):
        self._assert_denied_not_transient(make_single_block_hostile_token(), expected_status=401, expected_builds=1)

    def test_run_limit_in_phase2_denies_403(self):
        # Gate the explosion on `operation`, a fact only phase 2 supplies, so phase 1 runs cheaply
        # and the abort lands in the phase that maps to 403.
        self._assert_denied_not_transient(make_single_block_hostile_token(", operation($op)"), expected_status=403, expected_builds=2)

    def test_attenuation_really_does_reproduce_the_run_limit_marker(self):
        # Guards the premise behind all of this: an appended block reaches the identical top-level
        # message a policy denial raises, which is why the message alone can never mean "busy host".
        az = AuthorizerBuilder()
        az.add_check(Check(f'check if version("{VERSION}")'))
        az.add_policy(Policy("allow if true"))
        biscuit_mod._raise_time_budget(az)
        hostile = Biscuit.from_base64(attenuate(make_token(), cross_product(12)), _KEYPAIR.public_key)
        with self.assertRaises(AuthorizationError) as ctx:
            az.build(hostile).authorize()
        self.assertEqual(str(ctx.exception), biscuit_mod.RUN_LIMIT_ERROR)


if __name__ == "__main__":
    main()
