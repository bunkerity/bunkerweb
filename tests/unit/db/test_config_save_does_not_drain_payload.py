"""`save_config` must not empty the dict its caller handed it (port of dev ``dfa3273eb``).

Two passes inside `save_config` pop as they go: `DATABASE_URI` first
(`db_methods/config_save.py`, the `if config:` block), then every `<service>_IS_DRAFT` marker
(`_sc_collect_multisite_data`). They ran on the caller's own dict, so:

- the conflict retry replayed the ALREADY DRAINED dict, and every service the caller had marked
  as a draft was published;
- a caller that keeps its payload (autoconf hands over its long-lived config) got it back short
  and read the difference as a configuration change on its next pass.

Reaching those pops takes a seeded settings universe: `save_config` validates every key against
what the database knows and returns `"Invalid setting …"` EARLY otherwise — an early return skips
both pops, which is exactly how a first version of this test passed against the unfixed code. Hence
`seed_multisite`, the locally-seeded `IS_DRAFT` row (in `src/common/settings.json` but not in the
fixture universe), and the `not isinstance(ret, str)` assertion that pins the save actually ran.
"""

from copy import deepcopy

from fixtures.seed import add_service, add_setting, seed_multisite

PAYLOAD = {
    "MULTISITE": "yes",
    "SERVER_NAME": "app1.example.com app2.example.com app3.example.com",
    "DATABASE_URI": "sqlite:////var/lib/bunkerweb/db.sqlite3",
    "SECURITY_MODE": "detect",
    "app1.example.com_SERVER_NAME": "app1.example.com",
    "app2.example.com_SERVER_NAME": "app2.example.com",
    "app2.example.com_USE_REVERSE_PROXY": "yes",
    "app3.example.com_SERVER_NAME": "app3.example.com",
    "app3.example.com_IS_DRAFT": "yes",
}


def _prepared(db):
    seed_multisite(db)
    # `IS_DRAFT` ships in src/common/settings.json but is not part of the shared fixture universe;
    # without it the draft marker is refused as an unknown setting and the save never reaches the
    # pops this test is about.
    add_setting(db, "IS_DRAFT", context="multisite", type="check", regex="^(yes|no)$", default="no")
    # A draft only lands on a row the saving method may edit (`EDITABLE_METHODS`): the fixture's
    # services are `manual`, so the marker needs a service this "ui" save owns.
    add_service(db, "app3.example.com", method="ui")


def test_the_callers_payload_survives_the_save(db):
    _prepared(db)
    payload = deepcopy(PAYLOAD)
    before = deepcopy(payload)

    ret = db.save_config(payload, "ui")

    # An early return ("Invalid setting …") skips both pops and would make the assertion below
    # hold on the unfixed code as well.
    assert not isinstance(ret, str), f"save_config early-returned: {ret!r}"
    assert payload == before, f"save_config drained the caller's dict: {sorted(set(before) - set(payload))} were popped"


def test_the_save_really_reaches_the_pops(db):
    """Non-vacuity floor: prove the key the save pops was actually consumed inside it.

    The draft marker must have taken effect — if it were still merely "ignored", the test above
    would be pinning nothing. Only the draft half carries this floor: `DATABASE_URI` is not a
    setting id in `src/common/settings.json` or any `core/*/plugin.json`, so it can never become a
    stored row whether the pop runs or not, and asserting its absence would prove nothing.
    """
    _prepared(db)
    ret = db.save_config(deepcopy(PAYLOAD), "ui")
    assert not isinstance(ret, str), f"save_config early-returned: {ret!r}"

    drafts = {service["id"]: service.get("is_draft") for service in db.get_services(with_drafts=True)}
    assert drafts.get("app3.example.com") is True, f"the draft marker never reached the service row: {drafts}"
    assert drafts.get("app2.example.com") is False, f"app2 must not be a draft: {drafts}"


def test_the_conflict_retry_replays_the_undrained_payload(db, monkeypatch):
    """The half that actually loses data: the retry must replay what the CALLER sent.

    `save_config` retries once when the flush hits an `IntegrityError` (another writer inserted
    rows we had read as missing). The retry used to be handed the dict the first attempt had
    already drained, so every `<service>_IS_DRAFT` marker was gone by then and the retry PUBLISHED
    services the caller had explicitly marked as drafts.

    The conflict is forced by failing the first `commit()` on the session `save_config` holds.
    """
    from contextlib import contextmanager

    from sqlalchemy.exc import IntegrityError

    _prepared(db)

    state = {"commits_failed": 0}

    class _FailFirstCommit:
        def __init__(self, inner):
            self._inner = inner

        def __getattr__(self, name):
            return getattr(self._inner, name)

        def commit(self):
            if state["commits_failed"] == 0:
                state["commits_failed"] += 1
                raise IntegrityError("INSERT INTO bw_services", {}, Exception("UNIQUE constraint failed: bw_services.id"))
            return self._inner.commit()

    original = type(db)._db_session

    @contextmanager
    def _wrapped(self, *args, **kwargs):
        with original(self, *args, **kwargs) as session:
            yield _FailFirstCommit(session)

    monkeypatch.setattr(type(db), "_db_session", _wrapped)

    payload = deepcopy(PAYLOAD)
    ret = db.save_config(payload, "ui")

    assert state["commits_failed"] == 1, "the conflict was never triggered; this test proves nothing"
    assert not isinstance(ret, str), f"save_config early-returned: {ret!r}"

    drafts = {service["id"]: service.get("is_draft") for service in db.get_services(with_drafts=True)}
    assert drafts.get("app3.example.com") is True, f"the retry published a service the caller marked as a draft: {drafts}"
    assert payload == deepcopy(PAYLOAD), "the caller's dict was drained across the retry"
