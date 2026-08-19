"""The service list is rendered once per page, not once per picker.

`/certificates` carried five `<select>`s of every service, `/upstreams` three, `/redirects` three —
the same names serialised over and over into one document. At 501 services that was 160 KB of the
314 KB `/certificates` page and 174 KB of `/upstreams`, on pages with **zero** rows to show: the
cost was paid before any certificate or upstream existed. Worse, it grew multiplicatively — services
× pickers — so the next modal with a service picker would silently add another 32 KB.

`components/service-options.html` renders one `<template>` and clones it into every `<select>`
marked `data-bw-service-options`. What these tests defend is the property that makes that work, and
the two ways it fails silently: a picker that goes back to an inline loop (the saving quietly
returns to zero) and a macro imported without context (the nonce is empty, CSP blocks the script,
and every picker on the page is left empty with nothing but one console error to show for it).
"""

import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

TEMPLATES = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "templates"
COMPONENT = TEMPLATES / "components" / "service-options.html"


def _pages_using_the_macro():
    """Every template that calls the macro, found rather than listed.

    A hardcoded tuple is what let `/workflows` ship 95 KB of duplicated options all morning while
    these tests passed: the page was simply not named, so there was nothing to be inconsistent
    with. Deriving the list means a fifth page is covered the moment it is written.
    """
    return sorted(path for path in TEMPLATES.rglob("*.html") if "service_options(" in path.read_text(encoding="utf-8") and path != COMPONENT)


def _service_pickers():
    """Every `<select>` in the tree that offers services, with its position and whether it is
    wired to the shared list. The component's own usage example is excluded — it is a comment."""
    found = []
    for path in sorted(TEMPLATES.rglob("*.html")):
        if path == COMPONENT:
            continue
        source = path.read_text(encoding="utf-8")
        for match in re.finditer(r"<select\b[^>]*>", source):
            tag = match.group(0)
            if 'name="service_ids"' in tag or 'name="service_id"' in tag or "service-filter" in tag:
                found.append((f"{path.relative_to(TEMPLATES)}:{source[: match.start()].count(chr(10)) + 1}", tag, source, match.start()))
    return found


def _render_component(services, script_nonce="test-nonce"):
    """The macro on its own, imported the way a page imports it."""
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True)
    page = env.from_string(
        '{% from "components/service-options.html" import service_options with context %}{{ service_options(services) }}',
    )
    return page.render(services=services, script_nonce=script_nonce)


def test_the_list_is_rendered_once_and_the_pickers_are_empty():
    """The saving itself: N pickers, one copy of the names."""
    services = [{"id": "a.example.com"}, {"id": "b.example.com"}]

    html = _render_component(services)

    assert html.count("<template") == 1
    assert html.count("<option") == 2
    for service in services:
        assert html.count(service["id"]) == 2, "a name appears once as the value and once as the label, and nowhere else"


def test_the_server_type_is_emitted_only_when_it_says_something():
    """`/upstreams` hides the services a chosen protocol cannot serve — a stream service offered
    for an HTTP upstream is an attach the API would refuse.

    `upstreams.js` tests `option.dataset.serverType === "stream"`, so an **absent** attribute
    already reads as http. Writing it on every option cost 26 bytes x 501 services on five pages
    and carried no information; on `/bans`, which has a single picker and therefore no saving to
    begin with, it turned break-even into a 13 KB regression."""
    html = _render_component([{"id": "a.example.com", "server_type": "stream"}, {"id": "b.example.com", "server_type": "http"}, {"id": "c.example.com"}])

    assert '<option value="a.example.com" data-server-type="stream">a.example.com</option>' in html
    assert '<option value="b.example.com">b.example.com</option>' in html, "http is the default the JS already assumes"
    assert '<option value="c.example.com">c.example.com</option>' in html, "an undeclared type is http too"
    assert html.count("data-server-type") == 1


def test_the_macro_accepts_a_plain_list_of_names_as_well_as_service_dicts():
    """`/bans` reads its services out of `SERVER_NAME` and passes plain strings, where every other
    page passes the API's service dicts. `service.id` on a string is undefined in Jinja, so a macro
    written for dicts renders 501 empty options — a picker full of blank rows, no error anywhere.
    """
    html = _render_component(["a.example.com", "b.example.com"])

    assert '<option value="a.example.com">a.example.com</option>' in html
    assert html.count("<option") == 2
    assert 'value=""' not in html, "a string shape must not degrade to empty options"


def test_the_script_is_nonced_or_the_page_silently_ships_empty_pickers():
    """The trap that cost a debugging round: `script_nonce` comes from a context processor, and an
    imported macro does not see those unless the import says `with context`. Without it the script
    renders with an empty nonce, the page's CSP blocks it, no options are ever cloned, and the only
    symptom is one console error on a page that otherwise looks fine."""
    html = _render_component([{"id": "a.example.com"}])

    assert 'nonce="test-nonce"' in html
    assert 'nonce=""' not in html


def test_the_pages_import_the_macro_with_context():
    """Same trap, checked where it actually has to hold. A page that drops `with context` renders
    without error and without options."""
    pages = _pages_using_the_macro()

    assert pages, "no page calls the macro; these tests are looking at the wrong thing"
    for path in pages:
        source = path.read_text(encoding="utf-8")
        assert '{% from "components/service-options.html" import service_options with context %}' in source, path.name


def test_no_page_serialises_the_service_list_into_a_picker_any_more():
    """The regression that undoes the whole thing: one `{% for service in services %}` inside a
    `<select>` puts 32 KB back, and nobody adding a modal would notice."""
    offenders = []

    for path in sorted(TEMPLATES.rglob("*.html")):
        source = path.read_text(encoding="utf-8")
        for match in re.finditer(r"<select\b.*?</select>", source, re.DOTALL):
            if "for service in services" in match.group(0):
                offenders.append(f"{path.relative_to(TEMPLATES)}:{source[: match.start()].count(chr(10)) + 1}")

    assert not offenders, f"these pickers render the service list inline again: {offenders}"


def test_every_service_picker_is_wired_to_the_shared_list():
    """The other direction: a `<select>` named for services that forgot the attribute renders
    empty. Silent, and only on a page nobody opened during the change."""
    pickers = _service_pickers()

    assert len(pickers) >= 12, f"only {len(pickers)} service pickers found; the scan is missing some"
    unwired = [where for where, tag, _, _ in pickers if "data-bw-service-options" not in tag]

    assert not unwired, f"these service pickers are not filled by anything: {unwired}"


def test_a_placeholder_written_in_the_picker_still_comes_first():
    """`certificates-service-filter` opens with "All", `certificate-attach-service` with a "Select
    service" prompt. The clone is appended, so those stay at the top — sort them below 501 services
    and the control reads as though it has no default."""
    source = (TEMPLATES / "certificates.html").read_text(encoding="utf-8")

    for select_id in ("certificates-service-filter", "certificate-attach-service"):
        start = source.index(f'id="{select_id}"')
        block = source[source.rindex("<select", 0, start) : source.index("</select>", start)]  # noqa: E203
        assert "<option" in block, f"{select_id} lost its placeholder"
        assert block.index("data-bw-service-options") < block.index("<option"), f"{select_id}: the clone is appended, so the placeholder has to precede it"
