from fixtures.seed import add_global_value, add_service, add_service_setting, seed_minimal, session
from model import Plugins, Redirects, Resources, Settings  # type: ignore


def _seed_redirect_plugin(db) -> None:
    """Register the ``redirect`` plugin and its settings.

    The mixin validates rule values against these Settings rows and flags the plugin as
    config-changed on every attachment, so a test that skips this seed silently exercises
    the "plugin not installed" degradation instead of the real path.
    """
    with session(db) as s:
        s.add(Plugins(id="redirect", name="Redirect", description="Manage HTTP redirects.", version="1.0"))
        s.flush()
        s.add_all(
            [
                Settings(
                    id="REDIRECT_FROM",
                    name="Redirect from",
                    plugin_id="redirect",
                    context="multisite",
                    default="/",
                    help="Path to redirect from.",
                    label="Redirect from",
                    regex="^.+",
                    type="text",
                    multiple="redirect",
                ),
                Settings(
                    id="REDIRECT_TO",
                    name="Redirect to",
                    plugin_id="redirect",
                    context="multisite",
                    default="",
                    help="Redirect a whole site to another one.",
                    label="Redirect to",
                    regex=r"^(https?:\/\/[\-\w@:%.+~#=]+[\-\w\(\)!@:%+.~#?&\/=$]*)?$",
                    type="text",
                    multiple="redirect",
                ),
                Settings(
                    id="REDIRECT_TO_STATUS_CODE",
                    name="Redirect status code",
                    plugin_id="redirect",
                    context="multisite",
                    default="301",
                    help="HTTP status code for the redirect.",
                    label="Redirect status code",
                    regex="^30[12378]$",
                    type="select",
                    multiple="redirect",
                ),
            ]
        )


def _create(db, *, name="docs", from_path="/docs", to_url="https://docs.example.com", **kwargs):
    resource_id, error = db.create_redirect(name=name, from_path=from_path, to_url=to_url, **kwargs)
    assert error == ""
    return resource_id


def _config_changed(db) -> bool:
    with session(db) as s:
        return bool(s.get(Plugins, "redirect").config_changed)


def test_create_list_and_details(db):
    seed_minimal(db)
    _seed_redirect_plugin(db)
    resource_id = _create(db, description="Docs moved")

    listing = db.get_redirects()
    assert listing["total"] == 1
    item = listing["items"][0]
    assert item["id"] == resource_id
    assert (item["name"], item["from_path"], item["to_url"]) == ("docs", "/docs", "https://docs.example.com")
    assert item["status_code"] == "301" and item["append_request_uri"] is False
    assert item["services"] == []
    assert db.get_redirect_details(resource_id) == item
    assert db.get_redirect_details("missing") is None

    with session(db) as s:
        assert s.get(Resources, resource_id).type == "redirect"
        assert s.get(Redirects, resource_id).from_path == "/docs"


def test_create_is_not_a_config_change_until_attached(db):
    seed_minimal(db)
    _seed_redirect_plugin(db)
    _create(db)
    # A rule attached to nothing renders nothing; flagging it would trigger a pointless
    # generation and reload.
    assert _config_changed(db) is False


def test_duplicate_name_is_refused(db):
    seed_minimal(db)
    _seed_redirect_plugin(db)
    _create(db)
    _, error = db.create_redirect(name="docs", from_path="/other", to_url="https://other.example.com")
    assert "already exists" in error


def test_empty_target_is_refused(db):
    seed_minimal(db)
    _seed_redirect_plugin(db)
    _, error = db.create_redirect(name="blank", from_path="/x", to_url="")
    assert error == "Redirect target is required"


def test_invalid_values_are_refused_against_the_plugin_schema(db):
    seed_minimal(db)
    _seed_redirect_plugin(db)
    _, error = db.create_redirect(name="bad-target", from_path="/x", to_url="ftp://example.com")
    assert "REDIRECT_TO" in error
    _, error = db.create_redirect(name="bad-code", from_path="/x", to_url="https://example.com", status_code="404")
    assert "REDIRECT_TO_STATUS_CODE" in error


def test_attach_share_and_detach(db):
    seed_minimal(db)
    _seed_redirect_plugin(db)
    add_service(db, "app2.example.com")
    resource_id = _create(db)

    assert db.attach_redirect(resource_id, "app1.example.com") == ""
    assert _config_changed(db) is True
    assert db.attach_redirect(resource_id, "app2.example.com") == ""
    assert db.get_redirect_details(resource_id)["services"] == ["app1.example.com", "app2.example.com"]

    # The same rule serves both services, which is the point of a shared resource.
    service_redirects = db.get_service_redirects()
    assert set(service_redirects) == {"app1.example.com", "app2.example.com"}
    assert service_redirects["app1.example.com"][0]["to_url"] == "https://docs.example.com"

    assert db.attach_redirect(resource_id, "app1.example.com") == ""  # idempotent
    assert len(db.get_redirect_details(resource_id)["services"]) == 2

    assert db.detach_redirect(resource_id, "app1.example.com") == ""
    assert db.get_redirect_details(resource_id)["services"] == ["app2.example.com"]
    assert db.detach_redirect(resource_id, "app1.example.com") == "Redirect attachment not found"


def test_attach_rejects_unknown_service_and_redirect(db):
    seed_minimal(db)
    _seed_redirect_plugin(db)
    resource_id = _create(db)
    assert db.attach_redirect(resource_id, "nope.example.com") == "Service not found"
    assert db.attach_redirect("missing", "app1.example.com") == "Redirect not found"


def test_attach_refuses_a_path_another_resource_already_serves(db):
    seed_minimal(db)
    _seed_redirect_plugin(db)
    first = _create(db)
    second = _create(db, name="docs-bis", from_path="/docs", to_url="https://elsewhere.example.com")

    assert db.attach_redirect(first, "app1.example.com") == ""
    error = db.attach_redirect(second, "app1.example.com")
    assert "already has the redirect docs on path /docs" in error
    assert db.get_redirect_details(second)["services"] == []


def test_attach_refuses_a_path_an_inline_rule_already_serves(db):
    seed_minimal(db)
    _seed_redirect_plugin(db)
    add_service_setting(db, service_id="app1.example.com", setting_id="REDIRECT_FROM", value="/docs")
    add_service_setting(db, service_id="app1.example.com", setting_id="REDIRECT_TO", value="https://inline.example.com")

    resource_id = _create(db)
    assert "already has an inline redirect on path /docs" in db.attach_redirect(resource_id, "app1.example.com")


def test_a_blank_inline_target_does_not_reserve_the_path(db):
    seed_minimal(db)
    _seed_redirect_plugin(db)
    # REDIRECT_FROM without a target renders nothing, so it must not block the resource.
    add_service_setting(db, service_id="app1.example.com", setting_id="REDIRECT_FROM", value="/docs")
    add_service_setting(db, service_id="app1.example.com", setting_id="REDIRECT_TO", value="")

    resource_id = _create(db)
    assert db.attach_redirect(resource_id, "app1.example.com") == ""


def test_a_global_inline_rule_reserves_the_path_on_every_service(db):
    seed_minimal(db)
    _seed_redirect_plugin(db)
    add_global_value(db, setting_id="REDIRECT_FROM", value="/docs")
    add_global_value(db, setting_id="REDIRECT_TO", value="https://global.example.com")

    resource_id = _create(db)
    assert "already has an inline redirect on path /docs" in db.attach_redirect(resource_id, "app1.example.com")


def test_update_changes_every_attached_service_and_refuses_a_conflict(db):
    seed_minimal(db)
    _seed_redirect_plugin(db)
    resource_id = _create(db)
    other = _create(db, name="blog", from_path="/blog", to_url="https://blog.example.com")
    assert db.attach_redirect(resource_id, "app1.example.com") == ""
    assert db.attach_redirect(other, "app1.example.com") == ""

    assert db.update_redirect(resource_id, to_url="https://new.example.com", status_code="308", append_request_uri=True) == ""
    updated = db.get_redirect_details(resource_id)
    assert (updated["to_url"], updated["status_code"], updated["append_request_uri"]) == ("https://new.example.com", "308", True)

    # Moving the source path onto one already served by the other rule is refused.
    assert "already has the redirect blog on path /blog" in db.update_redirect(resource_id, from_path="/blog")
    assert db.get_redirect_details(resource_id)["from_path"] == "/docs"

    assert db.update_redirect("missing", name="x") == "Redirect not found"
    assert "already exists" in db.update_redirect(resource_id, name="blog")


def test_delete_is_refused_while_attached(db):
    seed_minimal(db)
    _seed_redirect_plugin(db)
    resource_id = _create(db)
    assert db.attach_redirect(resource_id, "app1.example.com") == ""
    assert db.delete_redirect(resource_id) == "Redirect is attached to a service"

    assert db.detach_redirect(resource_id, "app1.example.com") == ""
    assert db.delete_redirect(resource_id) == ""
    assert db.get_redirect_details(resource_id) is None
    assert db.delete_redirect(resource_id) == "Redirect not found"


def test_search_and_service_filter(db):
    seed_minimal(db)
    _seed_redirect_plugin(db)
    add_service(db, "app2.example.com")
    docs = _create(db)
    _create(db, name="blog", from_path="/blog", to_url="https://blog.example.com")
    assert db.attach_redirect(docs, "app2.example.com") == ""

    assert [item["name"] for item in db.get_redirects(search="blog")["items"]] == ["blog"]
    assert [item["name"] for item in db.get_redirects(search="docs.example")["items"]] == ["docs"]
    assert [item["name"] for item in db.get_redirects(service_id="app2.example.com")["items"]] == ["docs"]
    assert db.get_redirects(service_id="app1.example.com")["total"] == 0


def test_save_config_refuses_an_inline_rule_that_collides_with_a_resource(db):
    seed_minimal(db)
    _seed_redirect_plugin(db)
    resource_id = _create(db)
    assert db.attach_redirect(resource_id, "app1.example.com") == ""

    error = db.save_config(
        {
            "MULTISITE": "yes",
            "SERVER_NAME": "app1.example.com",
            "app1.example.com_REDIRECT_FROM": "/docs",
            "app1.example.com_REDIRECT_TO": "https://inline.example.com",
        },
        "ui",
    )
    assert isinstance(error, str) and "already has a redirect resource on path /docs" in error


def test_save_config_accepts_an_inline_rule_on_a_free_path(db):
    seed_minimal(db)
    _seed_redirect_plugin(db)
    resource_id = _create(db)
    assert db.attach_redirect(resource_id, "app1.example.com") == ""

    result = db.save_config(
        {
            "MULTISITE": "yes",
            "SERVER_NAME": "app1.example.com",
            "app1.example.com_REDIRECT_FROM": "/legacy",
            "app1.example.com_REDIRECT_TO": "https://inline.example.com",
        },
        "ui",
    )
    assert not isinstance(result, str) or result == ""
