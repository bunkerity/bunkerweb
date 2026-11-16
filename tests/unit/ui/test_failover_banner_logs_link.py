"""The NGINX failover banner links to the Logs page, with `error.log` selected when it is listed (dev 2102004da, #4028).

The banner tells the operator to check BunkerWeb's logs and gave no way to get there. The link is
built with `url_for` and the markup is a `Markup` template, so the translated sentence is escaped.
"""

from datetime import datetime
from urllib.parse import parse_qs, urlparse

from test_before_request_env import _Data, _app, _metadata

FAILOVER = _metadata(failover=True, failover_message='nginx: [emerg] unknown directive "foo"')


def _banner(log_files):
    flashed = []
    application = _app(FAILOVER, _Data(LATEST_VERSION_LAST_CHECK=datetime.now().astimezone().isoformat()), flashed)
    namespace = application.before_request_funcs[None][0].__globals__
    namespace["_list_log_files"] = log_files
    response = application.test_client().get("/templates", environ_base={"REMOTE_ADDR": "127.0.0.1"}, headers={"User-Agent": "pytest"})
    assert response.status_code == 200, response.get_data(as_text=True)
    return [content for category, content in flashed if category == "error" and "<a " in content]


def _href(content):
    start = content.index("href='") + len("href='")
    return content[start : content.index("'", start)]


def test_the_banner_links_to_the_error_log_when_it_is_listed():
    (banner,) = _banner(lambda: {"main": ["access.log", "error.log"], "letsencrypt": []})

    url = urlparse(_href(banner))
    assert url.path == "/logs"
    assert parse_qs(url.query) == {"file": ["error.log"]}


def test_the_banner_links_to_the_bare_logs_page_without_an_error_log():
    (banner,) = _banner(lambda: {"main": ["access.log"], "letsencrypt": []})

    assert _href(banner) == "/logs"


def test_an_unreadable_log_directory_does_not_break_the_page():
    def broken():
        raise OSError("permission denied")

    (banner,) = _banner(broken)

    assert _href(banner) == "/logs"


def test_the_nginx_output_is_still_shown_and_still_escaped():
    flashed = []
    application = _app(
        _metadata(failover=True, failover_message="<script>alert(1)</script>"),
        _Data(LATEST_VERSION_LAST_CHECK=datetime.now().astimezone().isoformat()),
        flashed,
    )
    application.before_request_funcs[None][0].__globals__["_list_log_files"] = lambda: {"main": [], "letsencrypt": []}

    application.test_client().get("/templates", environ_base={"REMOTE_ADDR": "127.0.0.1"}, headers={"User-Agent": "pytest"})

    assert any("&lt;script&gt;" in content for _, content in flashed), flashed
    assert not any("<script>" in content for _, content in flashed), flashed
