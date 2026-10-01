"""``url_download.download``: the one bounded fetch behind ``EXTERNAL_PLUGIN_URLS`` and ``EXTERNAL_TEMPLATE_URLS``.

Every case runs against a real local server (``conftest.url_server``), HTTPS with certificate
verification on. What is pinned here:

* the scheme rule: https and ``file:///`` always, plain http only when the caller allows it, and a
  redirect never downgrades an https URL to http;
* the ``#sha256=<hex>`` pin: checked on the bytes actually received, whatever the scheme, and a
  malformed pin is refused rather than read as "no pin";
* the size cap: refused from the Content-Length before the body is read, and while streaming
  when the server sends no length (chunked), and for a local file too.
"""

from hashlib import sha256

import pytest

from url_download import DownloadError, download, split_pin

BODY = b"x" * 1000
PIN = sha256(BODY).hexdigest()


def test_https_is_fetched_with_certificate_verification(url_server):
    url_server.routes["/a.zip"] = (200, BODY, {})
    assert download(url_server.https("/a.zip"), max_bytes=4096) == BODY


def test_plain_http_is_refused_unless_the_caller_allows_it(url_server):
    url_server.routes["/a.zip"] = (200, BODY, {})
    with pytest.raises(DownloadError, match="https"):
        download(url_server.http("/a.zip"), max_bytes=4096)
    assert url_server.hits == []
    assert download(url_server.http("/a.zip"), max_bytes=4096, allow_http=True) == BODY


@pytest.mark.parametrize("url", ["ftp://example.com/a.zip", "gopher://x/", "file://relative/a.zip", "/etc/passwd", "a.zip"])
def test_other_schemes_are_refused(url):
    with pytest.raises(DownloadError):
        download(url, max_bytes=4096, allow_http=True)


@pytest.mark.parametrize("allow_http", [False, True])
def test_an_https_url_redirected_to_http_is_refused(url_server, allow_http):
    url_server.routes["/plain.zip"] = (200, BODY, {})
    url_server.routes["/moved"] = (302, b"", {"Location": url_server.http("/plain.zip")})
    with pytest.raises(DownloadError, match="redirect"):
        download(url_server.https("/moved"), max_bytes=4096, allow_http=allow_http)


@pytest.mark.parametrize("allow_http", [False, True])
def test_an_https_http_https_chain_is_refused_at_the_plain_hop(url_server, allow_http):
    url_server.routes["/a.zip"] = (200, BODY, {})
    url_server.routes["/hop"] = (302, b"", {"Location": url_server.https("/a.zip")})
    url_server.routes["/moved"] = (302, b"", {"Location": url_server.http("/hop")})
    with pytest.raises(DownloadError, match="redirect"):
        download(url_server.https("/moved"), max_bytes=4096, allow_http=allow_http)


def test_a_chain_of_https_redirects_is_followed_and_capped(url_server):
    url_server.routes["/a.zip"] = (200, BODY, {})
    url_server.routes["/two"] = (301, b"", {"Location": "/a.zip"})
    url_server.routes["/one"] = (307, b"", {"Location": url_server.https("/two")})
    assert download(url_server.https("/one"), max_bytes=4096) == BODY
    url_server.routes["/loop"] = (302, b"", {"Location": "/loop"})
    with pytest.raises(DownloadError, match="redirect"):
        download(url_server.https("/loop"), max_bytes=4096)


def test_an_https_to_https_redirect_is_followed(url_server):
    url_server.routes["/a.zip"] = (200, BODY, {})
    url_server.routes["/moved"] = (302, b"", {"Location": url_server.https("/a.zip")})
    assert download(url_server.https("/moved"), max_bytes=4096) == BODY


def test_a_non_200_answer_is_an_error(url_server):
    with pytest.raises(DownloadError, match="404"):
        download(url_server.https("/missing.zip"), max_bytes=4096)


def test_a_matching_pin_passes_in_either_case(url_server):
    url_server.routes["/a.zip"] = (200, BODY, {})
    assert download(url_server.https(f"/a.zip#sha256={PIN}"), max_bytes=4096) == BODY
    assert download(url_server.https(f"/a.zip#sha256={PIN.upper()}"), max_bytes=4096) == BODY


def test_a_pin_mismatch_is_refused(url_server):
    url_server.routes["/a.zip"] = (200, BODY + b"tampered", {})
    with pytest.raises(DownloadError, match="sha256"):
        download(url_server.https(f"/a.zip#sha256={PIN}"), max_bytes=4096)


@pytest.mark.parametrize("fragment", ["sha256=abc", "sha256=" + "g" * 64, "sha256=" + PIN + "0", "sha256="])
def test_a_malformed_pin_is_refused_not_ignored(url_server, fragment):
    url_server.routes["/a.zip"] = (200, BODY, {})
    with pytest.raises(DownloadError, match="sha256"):
        download(url_server.https(f"/a.zip#{fragment}"), max_bytes=4096)
    assert url_server.hits == []


def test_any_other_fragment_is_left_alone_as_before():
    assert split_pin("https://h/a.zip#readme") == ("https://h/a.zip#readme", None)
    assert split_pin(f"https://h/a.zip#sha256={PIN}") == ("https://h/a.zip", PIN)
    assert split_pin("https://h/a.zip") == ("https://h/a.zip", None)


def test_the_cap_refuses_a_declared_length_before_reading_the_body(url_server):
    url_server.routes["/big.zip"] = (200, BODY, {})
    with pytest.raises(DownloadError, match="exceeds"):
        download(url_server.https("/big.zip"), max_bytes=len(BODY) - 1)


def test_the_cap_refuses_a_chunked_body_while_streaming(url_server):
    url_server.routes["/big.zip"] = (200, [BODY[:600], BODY[600:]], {})
    with pytest.raises(DownloadError, match="exceeds"):
        download(url_server.https("/big.zip"), max_bytes=len(BODY) - 1)
    assert download(url_server.https("/big.zip"), max_bytes=len(BODY)) == BODY


def test_a_local_file_is_read_pinned_and_capped(tmp_path):
    archive = tmp_path / "a.zip"
    archive.write_bytes(BODY)
    assert download(f"file://{archive}", max_bytes=4096) == BODY
    assert download(f"file://{archive}#sha256={PIN}", max_bytes=4096) == BODY
    with pytest.raises(DownloadError, match="sha256"):
        download(f"file://{archive}#sha256={'0' * 64}", max_bytes=4096)
    with pytest.raises(DownloadError, match="exceeds"):
        download(f"file://{archive}", max_bytes=len(BODY) - 1)


def test_a_missing_local_file_is_an_error(tmp_path):
    with pytest.raises(DownloadError):
        download(f"file://{tmp_path / 'nope.zip'}", max_bytes=4096)


def test_a_cookie_set_by_an_earlier_hop_is_sent_on_the_next_one(url_server):
    """A cookie-gated redirect (set on hop 1, required on hop 2) used to go 200 -> 403 with one session per hop."""
    url_server.routes["/a.zip"] = lambda headers: (200, BODY, {}) if "gate=open" in headers.get("Cookie", "") else (403, b"no cookie", {})
    url_server.routes["/login"] = (302, b"", {"Set-Cookie": "gate=open; Path=/", "Location": url_server.https("/a.zip")})
    assert download(url_server.https("/login"), max_bytes=4096) == BODY
