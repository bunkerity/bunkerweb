from fixtures.seed import add_global_value, add_service, add_service_setting, add_setting, seed_minimal, session
from model import Plugins, Redirects, ResourceAttachments, Resources, Settings  # type: ignore


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


def test_service_redirects_use_attachment_id_when_timestamps_tie(db):
    seed_minimal(db)
    _seed_redirect_plugin(db)
    first = _create(db, name="zzz-first", from_path="/first")
    second = _create(db, name="aaa-second", from_path="/second")
    assert db.attach_redirect(first, "app1.example.com") == ""
    assert db.attach_redirect(second, "app1.example.com") == ""
    with session(db) as db_session:
        attachments = db_session.query(ResourceAttachments).filter_by(service_id="app1.example.com").order_by(ResourceAttachments.id).all()
        attachments[1].creation_date = attachments[0].creation_date

    assert [item["name"] for item in db.get_service_redirects()["app1.example.com"]] == ["zzz-first", "aaa-second"]


def test_redirect_cannot_attach_to_stream_service(db):
    seed_minimal(db)
    _seed_redirect_plugin(db)
    add_setting(db, "SERVER_TYPE", context="multisite", regex="^(http|stream)$", default="http")
    add_service_setting(db, service_id="app1.example.com", setting_id="SERVER_TYPE", value="stream")
    resource_id = _create(db)

    assert db.attach_redirect(resource_id, "app1.example.com") == "Cannot attach a redirect to app1.example.com: redirects require an HTTP service"


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
    assert "already serves /docs through the redirect “docs”" in error
    assert db.get_redirect_details(second)["services"] == []


def test_attach_refuses_a_path_an_inline_rule_already_serves(db):
    seed_minimal(db)
    _seed_redirect_plugin(db)
    add_service_setting(db, service_id="app1.example.com", setting_id="REDIRECT_FROM", value="/docs")
    add_service_setting(db, service_id="app1.example.com", setting_id="REDIRECT_TO", value="https://inline.example.com")

    resource_id = _create(db)
    assert "already serves /docs through its own redirect settings" in db.attach_redirect(resource_id, "app1.example.com")


def _seed_reverse_proxy_settings(db) -> None:
    """The inline reverse-proxy settings the location guard reads.

    ``REVERSE_PROXY_URL`` already comes from ``seed_minimal``; the host is the trigger the
    template loops on and without it the guard sees no inline location at all.
    """
    with session(db) as s:
        s.add(Plugins(id="reverseproxy", name="Reverse proxy", description="Reverse proxy settings.", version="1.0"))
    add_setting(db, "REVERSE_PROXY_HOST", plugin_id="general", context="multisite", multiple="reverse-proxy")


def test_from_path_takes_an_anchored_value(db):
    """Unlike an upstream's ``match_path`` (``upstreams.py``: *must start with /*), a redirect's
    ``from_path`` has no path validation — which is what lets a regex location reach the guard."""
    seed_minimal(db)
    _seed_redirect_plugin(db)

    resource_id, error = db.create_redirect(name="rx", from_path="^/api", to_url="https://x.example.com")

    assert error == "" and resource_id


def test_an_anchored_path_is_claimed_as_the_regex_location_it_renders(db):
    """The two location guards are mirrors and must normalize identically.

    ``db_methods/locations.py`` refuses at mutation time, ``utils/location_claims.py`` claims at
    render time, and each docstring names the other. All three templates now render an anchored
    path as ``location ~ …``, so ``^/api`` and ``~ ^/api`` are ONE location.

    **If only one mirror normalizes, this test fails**, and it fails in both directions:
    normalize neither and the first assertion misses a real duplicate; normalize only the
    render-time side and the guard produces a false refusal on a pair NGINX accepts.
    """
    seed_minimal(db)
    _seed_redirect_plugin(db)
    _seed_reverse_proxy_settings(db)
    add_service_setting(db, service_id="app1.example.com", setting_id="REVERSE_PROXY_HOST", value="http://a:80", suffix=1)
    add_service_setting(db, service_id="app1.example.com", setting_id="REVERSE_PROXY_URL", value="^/api", suffix=1)

    # Same location, spelled the other way: NGINX would refuse the pair, so the guard must too.
    spelled_differently = _create(db, name="rx", from_path="~ ^/api")
    assert "already serves" in db.attach_redirect(spelled_differently, "app1.example.com")

    # A different regex on the same service renders a different location and stays free.
    unrelated = _create(db, name="ry", from_path="^/other")
    assert db.attach_redirect(unrelated, "app1.example.com") == ""


def test_two_attached_resources_cannot_spell_one_regex_location_two_ways(db):
    """The resource-vs-resource arm of the same rule.

    ``location_conflict`` compares an incoming path against paths already mounted by *other*
    attached resources, and that comparison needs the same normalization as the inline one — a
    mutant that reverts only this arm leaves the inline test green.
    """
    seed_minimal(db)
    _seed_redirect_plugin(db)
    first = _create(db, name="rx", from_path="^/api")
    assert db.attach_redirect(first, "app1.example.com") == ""

    second = _create(db, name="ry", from_path="~ ^/api")

    assert "already serves" in db.attach_redirect(second, "app1.example.com")


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
    assert "already serves /docs through its own redirect settings" in db.attach_redirect(resource_id, "app1.example.com")


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
    assert "already serves /blog through the redirect “blog”" in db.update_redirect(resource_id, from_path="/blog")
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
    assert isinstance(error, str) and "already serves /docs through an attached resource" in error


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


def _seed_php_and_reverse_proxy_settings(db) -> None:
    """The trigger settings the location registry watches, as real Settings rows.

    ``seed_minimal`` ships ``REVERSE_PROXY_URL`` but not the host that makes the location render,
    and nothing at all for php — without these the save path rejects the keys as unknown settings
    and the conflict guard below never runs.
    """
    add_setting(db, "REVERSE_PROXY_HOST", context="multisite", multiple="reverse-proxy")
    add_setting(db, "REMOTE_PHP", context="multisite")


def test_save_config_refuses_two_inline_families_landing_on_the_same_path(db):
    """No attached resource involved: the incoming config collides with itself.

    This is the shape Autoconf and the Kubernetes controller push — one merged dict for one
    service — and it used to pass the save untouched and reach NGINX as `duplicate location "/"`,
    an [emerg] that refuses the whole reload.
    """
    seed_minimal(db)
    _seed_redirect_plugin(db)
    _seed_php_and_reverse_proxy_settings(db)

    error = db.save_config(
        {
            "MULTISITE": "yes",
            "SERVER_NAME": "app1.example.com",
            "app1.example.com_REVERSE_PROXY_HOST": "http://backend:8080",
            "app1.example.com_REDIRECT_TO": "https://elsewhere.example.com",
        },
        "ui",
    )
    assert isinstance(error, str) and "would serve / through both its reverse proxy and its redirect settings" in error


def test_save_config_refuses_php_next_to_an_inline_reverse_proxy(db):
    """php.conf hardcodes `location /`, so enabling PHP claims the default path outright."""
    seed_minimal(db)
    _seed_php_and_reverse_proxy_settings(db)

    error = db.save_config(
        {
            "MULTISITE": "yes",
            "SERVER_NAME": "app1.example.com",
            "app1.example.com_REVERSE_PROXY_HOST": "http://backend:8080",
            "app1.example.com_REMOTE_PHP": "php-fpm",
        },
        "ui",
    )
    assert isinstance(error, str) and "PHP" in error and "reverse proxy" in error


def test_save_config_accepts_two_inline_families_on_different_paths(db):
    """The false-refusal direction: NGINX accepts these two locations, so the guard must too."""
    seed_minimal(db)
    _seed_redirect_plugin(db)
    _seed_php_and_reverse_proxy_settings(db)

    result = db.save_config(
        {
            "MULTISITE": "yes",
            "SERVER_NAME": "app1.example.com",
            "app1.example.com_REVERSE_PROXY_HOST": "http://backend:8080",
            "app1.example.com_REVERSE_PROXY_URL": "/app",
            "app1.example.com_REDIRECT_TO": "https://elsewhere.example.com",
            "app1.example.com_REDIRECT_FROM": "/legacy",
        },
        "ui",
    )
    assert not isinstance(result, str) or result == ""


def test_attaching_a_resource_onto_the_path_php_serves_is_refused(db):
    """The mutation-time mirror: ``db_methods/locations.py`` has to know about php as well.

    Both mirrors read the same registry now, so a redirect on ``/`` is refused whether php was
    enabled before the attach (here) or arrives in the same save (above).
    """
    seed_minimal(db)
    _seed_redirect_plugin(db)
    _seed_php_and_reverse_proxy_settings(db)
    add_service_setting(db, service_id="app1.example.com", setting_id="REMOTE_PHP", value="php-fpm")

    resource_id = _create(db, name="root", from_path="/", to_url="https://elsewhere.example.com")
    error = db.attach_redirect(resource_id, "app1.example.com")
    assert "already serves / through its own PHP settings" in error
