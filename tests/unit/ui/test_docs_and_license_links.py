"""Documentation and license links for published versions."""

from pathlib import Path

import pytest
from jinja2 import ChainableUndefined, Environment, FileSystemLoader

TEMPLATES = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "templates"


def _docs_url(context=None, **kwargs):
    """Render `docs_url()` with exactly the context given."""
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True, undefined=ChainableUndefined)
    module = env.get_template("macros/docs_link.html").make_module(context or {})
    return str(module.docs_url(**kwargs))


def _render_footer(bw_version, language=None):
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True, undefined=ChainableUndefined)
    return env.get_template("footer.html").render(bw_version=bw_version, language=language, script_nonce="n")


@pytest.mark.parametrize(
    ("bw_version", "expected_segment"),
    [
        ("1.7.0", "1.7.0"),
        ("1.6.13", "1.6.13"),
        ("1.7.0~alpha", "latest"),
        ("1.6.14~rc1", "latest"),
        ("1.7.0~beta", "latest"),
        ("dev", "latest"),
        ("testing", "latest"),
    ],
)
def test_pre_release_and_sentinel_versions_map_to_latest(bw_version, expected_segment):
    url = _docs_url(context={"bw_version": bw_version})

    assert url.startswith(f"https://docs.bunkerweb.io/{expected_segment}/")


def test_a_missing_bw_version_falls_back_to_latest_instead_of_an_empty_path_segment():
    """Every current caller imports this macro without `with context`
    (`{% from 'macros/docs_link.html' import docs_url %}`), so `bw_version` resolves as
    Undefined there -- confirmed against the live dev stack, where `/login`'s troubleshooting
    link rendered `docs.bunkerweb.io//troubleshooting/` (empty version segment, double slash).
    This fallback is what stands between that and a working link until every caller is fixed.
    """
    url = _docs_url()

    assert url.startswith("https://docs.bunkerweb.io/latest/")
    assert "//" not in url.removeprefix("https://")


# --------------------------------------------------------------------------------------
# The footer -- the one caller this lane owns
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize("bw_version", ["1.7.0~alpha", "1.6.14~rc1", "1.7.0~beta", "dev", "testing"])
def test_the_footer_documentation_link_maps_a_pre_release_build_to_latest(bw_version):
    html = _render_footer(bw_version)

    assert "docs.bunkerweb.io/latest/" in html
    assert f"docs.bunkerweb.io/{bw_version}/" not in html


def test_the_footer_documentation_link_uses_the_real_version_for_a_release():
    html = _render_footer("1.7.0")

    assert "docs.bunkerweb.io/1.7.0/" in html


@pytest.mark.parametrize(
    ("bw_version", "expected_tag"),
    [
        ("1.7.0", "v1.7.0"),
        ("1.7.0~alpha", "v1.7.0-alpha"),
        ("1.6.14~rc1", "v1.6.14-rc1"),
        ("dev", "dev"),
        ("testing", "testing"),
    ],
)
def test_the_footer_license_link_uses_the_real_tag_name(bw_version, expected_tag):
    """The license link reads `bw_version` directly from the footer context."""
    html = _render_footer(bw_version)

    assert f"blob/{expected_tag}/LICENSE.md" in html
