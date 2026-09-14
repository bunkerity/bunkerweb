"""Integration tier — save_config: renaming a service must MOVE its row, not delete+insert it.

`PATCH /services/{s}` with a new SERVER_NAME (api/app/routers/services.py:409-460) hands
save_config a config where the old id has dropped out of SERVER_NAME and a new one appeared.
Before the rename heuristic, the old id landed in `missing_ids` and was hard-deleted
(config_save.py, `delete_service_rows`), taking its `bw_custom_configs` /
`bw_services_settings` / `bw_jobs_cache` / `bw_resource_attachments` rows with it; the new id
was inserted empty. The UI hid this behind a private re-key workaround
(ui/app/routes/services.py:1567-1613); the API and autoconf did not.

These tests pin the fix AND its limits: exactly one id dropped + exactly one id added under
the same method is a rename; anything else stays delete+insert.
"""

import pytest

from fixtures.seed import FIXED_DT, seed_multisite, session
from model import Custom_configs, Jobs_cache, Redirects, ResourceAttachments, Resources, Services, Services_settings, Settings  # type: ignore

pytestmark = pytest.mark.slow

OLD = "api.example.com"
NEW = "renamed.example.com"


@pytest.fixture
def seeded(db):
    """seed_multisite + one api-owned service carrying an api custom config."""
    seed_multisite(db)
    conf = _snapshot(db)
    conf["SERVER_NAME"] = f"{conf['SERVER_NAME']} {OLD}"
    conf[f"{OLD}_USE_REVERSE_PROXY"] = "yes"
    assert not isinstance(db.save_config(conf, "api", changed=True), str)
    assert (
        db.save_custom_configs(
            [{"service_id": OLD, "type": "server_http", "name": "mysnippet", "data": "# keep me", "method": "api"}],
            "api",
        )
        == ""
    )
    return db


def _snapshot(db):
    conf = db.get_non_default_settings(methods=False, with_drafts=True)
    return {k: v for k, v in conf.items() if not k.endswith("IS_DRAFT")}


def _rename_payload(db, pairs):
    """Build the payload PATCH /services/{s} builds: swap the names in SERVER_NAME and
    re-prefix every `{old}_…` setting key (routers/services.py:454-459)."""
    conf = _snapshot(db)
    names = conf["SERVER_NAME"].split()
    mapping = dict(pairs)
    conf["SERVER_NAME"] = " ".join(mapping.get(n, n) for n in names)
    for old, new in pairs:
        for key in list(conf):
            if key.startswith(f"{old}_"):
                conf[f"{new}_{key[len(old) + 1:]}"] = conf.pop(key)  # noqa: E203
    return conf


def _add_setting(db, setting_id, *, regex="^.*$", default="", type="text", context="multisite", multiple=None):
    """Declare one extra setting the seed does not carry; save_config validates every key."""
    with session(db) as s:
        s.add(
            Settings(id=setting_id, name=setting_id, plugin_id="general", context=context, help="h", regex=regex, type=type, default=default, multiple=multiple)
        )


def _configs(db):
    return {(c["service_id"], c["name"]) for c in db.get_custom_configs(with_drafts=True, with_data=False)}


def _service_ids(db):
    with session(db) as s:
        return {row.id for row in s.query(Services).all()}


# --- the defect ------------------------------------------------------------------------


def test_rename_keeps_the_custom_configs(seeded):
    db = seeded
    assert (OLD, "mysnippet") in _configs(db)

    assert not isinstance(db.save_config(_rename_payload(db, [(OLD, NEW)]), "api", changed=True), str)

    assert NEW in _service_ids(db) and OLD not in _service_ids(db)
    assert (NEW, "mysnippet") in _configs(db), "the rename destroyed the custom config"
    assert (OLD, "mysnippet") not in _configs(db)


def test_rename_keeps_the_service_settings_and_the_creation_date(seeded):
    db = seeded
    with session(db) as s:
        created = s.query(Services).filter_by(id=OLD).one().creation_date

    assert not isinstance(db.save_config(_rename_payload(db, [(OLD, NEW)]), "api", changed=True), str)

    with session(db) as s:
        row = s.query(Services).filter_by(id=NEW).one()
        assert row.creation_date == created, "the row was re-created, not renamed"
        assert row.method == "api"
        assert {r.setting_id for r in s.query(Services_settings).filter_by(service_id=NEW).all()} >= {"USE_REVERSE_PROXY"}
        assert s.query(Services_settings).filter_by(service_id=OLD).count() == 0


def test_rename_carries_the_jobs_cache(seeded):
    db = seeded
    with session(db) as s:
        s.add(Jobs_cache(service_id=OLD, job_name="testjob", file_name="f.txt", data=b"x"))

    assert not isinstance(db.save_config(_rename_payload(db, [(OLD, NEW)]), "api", changed=True), str)

    with session(db) as s:
        assert s.query(Jobs_cache).filter_by(service_id=NEW).count() == 1
        assert s.query(Jobs_cache).filter_by(service_id=OLD).count() == 0


def test_rename_carries_the_resource_attachments(seeded):
    """The fourth re-keyed child, and the one that matters most: a certificate, an upstream pool or
    a redirect is attached through `bw_resource_attachments`. Losing it on a rename drops the
    service's certificate; carrying it onto the WRONG service serves somebody else's."""
    db = seeded
    with session(db) as s:
        s.add(Resources(id="res-1", type="redirect", name="r1", creation_date=FIXED_DT, last_update=FIXED_DT))
        s.flush()
        s.add(ResourceAttachments(resource_id="res-1", service_id=OLD, is_primary=True, match_path="", creation_date=FIXED_DT))

    assert not isinstance(db.save_config(_rename_payload(db, [(OLD, NEW)]), "api", changed=True), str)

    with session(db) as s:
        assert s.query(ResourceAttachments).filter_by(service_id=NEW).count() == 1
        assert s.query(ResourceAttachments).filter_by(service_id=OLD).count() == 0


# --- the heuristic's limits ------------------------------------------------------------


def test_two_renames_in_one_save_stay_delete_plus_insert(seeded, monkeypatch):
    """{dropped} == {added} == 1 is the only safe signal: with two of each there is no way
    to pair them, so both fall back to the (lossy) delete+insert path."""
    db = seeded
    conf = _snapshot(db)
    conf["SERVER_NAME"] = f"{conf['SERVER_NAME']} second.example.com"
    conf["second.example.com_USE_REVERSE_PROXY"] = "yes"
    assert not isinstance(db.save_config(conf, "api", changed=True), str)
    assert (
        db.save_custom_configs(
            [{"service_id": "second.example.com", "type": "server_http", "name": "other", "data": "# two", "method": "api"}],
            "api",
        )
        == ""
    )

    from unittest.mock import Mock

    warning = Mock()
    monkeypatch.setattr(db.logger, "warning", warning)
    payload = _rename_payload(db, [(OLD, NEW), ("second.example.com", "second-renamed.example.com")])
    assert not isinstance(db.save_config(payload, "api", changed=True), str)

    ids = _service_ids(db)
    assert {NEW, "second-renamed.example.com"} <= ids
    assert not {OLD, "second.example.com"} & ids
    assert _configs(db) == set(), "documented limitation: two renames in one save still delete"
    assert any("also destroys" in str(call.args[0]) and "custom config" in str(call.args[0]) for call in warning.call_args_list)


def test_a_drop_with_no_add_still_deletes(seeded):
    db = seeded
    conf = _snapshot(db)
    conf["SERVER_NAME"] = " ".join(n for n in conf["SERVER_NAME"].split() if n != OLD)
    for key in list(conf):
        if key.startswith(f"{OLD}_"):
            conf.pop(key)

    assert not isinstance(db.save_config(conf, "api", changed=True), str)

    assert OLD not in _service_ids(db)
    assert _configs(db) == set()


def test_an_add_with_no_drop_does_not_touch_anything_else(seeded):
    db = seeded
    conf = _snapshot(db)
    conf["SERVER_NAME"] = f"{conf['SERVER_NAME']} extra.example.com"
    conf["extra.example.com_USE_REVERSE_PROXY"] = "yes"

    assert not isinstance(db.save_config(conf, "api", changed=True), str)

    assert {OLD, "extra.example.com"} <= _service_ids(db)
    assert (OLD, "mysnippet") in _configs(db)


def test_the_reserved_default_server_is_never_renamed(seeded):
    """default-server is permanent: dropping it from SERVER_NAME while adding another name
    must create the new service and leave the reserved row alone."""
    db = seeded
    conf = _snapshot(db)
    conf["SERVER_NAME"] = " ".join(n for n in conf["SERVER_NAME"].split() if n != "default-server") + " brand-new.example.com"
    conf["brand-new.example.com_USE_REVERSE_PROXY"] = "yes"

    assert not isinstance(db.save_config(conf, "api", changed=True), str)

    ids = _service_ids(db)
    assert "default-server" in ids and "brand-new.example.com" in ids
    assert (OLD, "mysnippet") in _configs(db)


def test_a_foreign_method_service_is_not_renamed_by_a_scheduler_save(seeded):
    """missing_ids only ever holds rows this method owns, so the rename inherits that:
    an api-owned row is invisible to a scheduler save and must survive untouched."""
    db = seeded
    conf = _snapshot(db)
    conf["SERVER_NAME"] = f"{conf['SERVER_NAME']} sched.example.com"
    conf["sched.example.com_USE_REVERSE_PROXY"] = "yes"
    assert not isinstance(db.save_config(conf, "scheduler", changed=True), str)

    payload = _rename_payload(db, [("sched.example.com", "sched-renamed.example.com")])
    # drop the api service from SERVER_NAME too: the scheduler may not delete it, so it must
    # not be paired with the added name either.
    payload["SERVER_NAME"] = " ".join(n for n in payload["SERVER_NAME"].split() if n != OLD)
    assert not isinstance(db.save_config(payload, "scheduler", changed=True), str)

    ids = _service_ids(db)
    assert "sched-renamed.example.com" in ids and "sched.example.com" not in ids
    assert OLD in ids, "the api-owned service was deleted by a scheduler save"
    assert (OLD, "mysnippet") in _configs(db)


# --- the rename must not smuggle anything past the attachment / location guards ---------


def _attach_redirect(db, service_id, from_path="/api"):
    with session(db) as s:
        s.add(Resources(id="red-1", type="redirect", name="r1", creation_date=FIXED_DT, last_update=FIXED_DT))
        s.flush()
        s.add(Redirects(resource_id="red-1", from_path=from_path, to_url="https://example.com", status_code="301"))
        s.add(ResourceAttachments(resource_id="red-1", service_id=service_id, is_primary=False, match_path="", creation_date=FIXED_DT))


def test_a_rename_cannot_smuggle_a_stream_switch_past_the_attachment_guard(seeded):
    """`server_type_attachment_conflict` keys on `bw_resource_attachments.service_id`. If the rename
    ran after it, the guard would look up the NEW id (which has no attachments yet) while the
    redirect still hung off the OLD one -- and the rename would then carry the redirect onto a
    service that just became `stream`, which renders nothing and answers nobody."""
    db = seeded
    _add_setting(db, "SERVER_TYPE", regex="^(http|stream)$", default="http")
    _attach_redirect(db, OLD)

    conf = _rename_payload(db, [(OLD, NEW)])
    conf[f"{NEW}_SERVER_TYPE"] = "stream"
    ret = db.save_config(conf, "api", changed=True)

    assert isinstance(ret, str) and "redirect is attached" in ret, f"the guard did not fire: {ret!r}"
    assert OLD in _service_ids(db) and NEW not in _service_ids(db)


def test_a_rename_cannot_smuggle_a_location_collision_past_the_guard(seeded):
    """Same shape for the location-namespace guard: `_service_redirects` is keyed by
    `ResourceAttachments.service_id`, so a rename applied after it hides the collision. NGINX
    answers a duplicate `location` with an [emerg] that refuses the reload for EVERY service."""
    db = seeded
    _add_setting(db, "REVERSE_PROXY_HOST", multiple="reverse-proxy")  # the family's trigger (location_claims.LOCATION_FAMILIES)
    _attach_redirect(db, OLD, from_path="/api")

    conf = _rename_payload(db, [(OLD, NEW)])
    conf[f"{NEW}_USE_REVERSE_PROXY"] = "yes"
    conf[f"{NEW}_REVERSE_PROXY_URL_1"] = "/api"
    conf[f"{NEW}_REVERSE_PROXY_HOST_1"] = "http://backend1"
    ret = db.save_config(conf, "api", changed=True)

    assert isinstance(ret, str) and "already serves /api" in ret, f"the guard did not fire: {ret!r}"
    assert OLD in _service_ids(db) and NEW not in _service_ids(db)


# --- the data-loss guards on the deletion path still fire ------------------------------


def test_empty_server_name_guard_still_aborts_an_api_save(seeded):
    db = seeded
    before = _service_ids(db)
    conf = _snapshot(db)
    conf.pop("SERVER_NAME")

    db.save_config(conf, "api", changed=True)

    assert _service_ids(db) == before
    assert (OLD, "mysnippet") in _configs(db)


def test_empty_server_name_guard_still_aborts_an_autoconf_save_with_foreign_services(seeded):
    db = seeded
    before = _service_ids(db)
    conf = _snapshot(db)
    conf["SERVER_NAME"] = ""

    db.save_config(conf, "autoconf", changed=True)

    assert _service_ids(db) == before
    assert (OLD, "mysnippet") in _configs(db)


def test_whole_service_wipe_guard_still_aborts(seeded):
    """A rename runs before the settings cleanup, so the ui/api 100%-wipe guard sees the
    renamed service — an incomplete payload is still refused."""
    db = seeded
    conf = _rename_payload(db, [(OLD, NEW)])
    for key in list(conf):
        if key.startswith(f"{NEW}_"):
            conf.pop(key)

    db.save_config(conf, "api", changed=True)

    assert OLD in _service_ids(db) and NEW not in _service_ids(db)
    assert (OLD, "mysnippet") in _configs(db)


# --- autoconf ---------------------------------------------------------------------------


@pytest.mark.parametrize("disable_cleanup", (False, True))
def test_autoconf_never_renames_it_drafts_or_deletes_exactly_as_before(db, disable_cleanup):
    """Autoconf is OUT of the heuristic on purpose (coordinator ruling 2026-09-14, Criticos round 1).

    `src/autoconf/Config.py` rebuilds the whole SERVER_NAME set from cluster state on every
    reconcile, so one-dropped-one-added is ordinary churn -- two unrelated ingress edits in one
    pass, a blue/green swap, a Helm release rename -- with no rename intent anywhere in it. Reading
    it as a rename would move the old service's certificate and upstream pools onto an unrelated new
    service, and would silently defeat `AUTOCONF_DISABLE_CLEANUP`, whose whole contract is "never
    remove a service that dropped out, draft it". This pins TODAY's behaviour, unchanged: without
    the flag the old service and its configs are deleted; with it, both are drafted; and the new
    service inherits nothing either way.
    """
    seed_multisite(db)
    conf = _snapshot(db)
    conf["SERVER_NAME"] = f"{conf['SERVER_NAME']} {OLD}"
    conf[f"{OLD}_USE_REVERSE_PROXY"] = "yes"
    assert not isinstance(db.save_config(conf, "autoconf", changed=True), str)
    assert (
        db.save_custom_configs(
            [{"service_id": OLD, "type": "server_http", "name": "mysnippet", "data": "# keep me", "method": "autoconf"}],
            "autoconf",
        )
        == ""
    )

    payload = _rename_payload(db, [(OLD, NEW)])
    assert not isinstance(db.save_config(payload, "autoconf", changed=True, disable_cleanup=disable_cleanup), str)

    assert NEW in _service_ids(db)
    with session(db) as s:
        old_row = s.query(Services).filter_by(id=OLD).one_or_none()
        old_configs = s.query(Custom_configs).filter_by(service_id=OLD).all()
        if disable_cleanup:
            assert old_row is not None and old_row.is_draft is True, "AUTOCONF_DISABLE_CLEANUP must still draft the removed service"
            assert len(old_configs) == 1 and old_configs[0].is_draft is True
        else:
            assert old_row is None, "without the flag autoconf still deletes the removed service"
            assert old_configs == []
        assert s.query(Custom_configs).filter_by(service_id=NEW).count() == 0, "the new service must NOT inherit anything"
