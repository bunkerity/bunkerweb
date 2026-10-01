"""The gettext catalogs: they compile, they say the same thing as the JSON, and the two things
gettext can get wrong — plural slots and `%` formatting — are right in locales that differ.

Server-side translation (Lot A) reads `src/ui/translations/`, generated from the same JSON files
i18next loads by `misc/dev/i18n/json_to_po.py`. Two runtimes, one source, so the check that
matters is that the generated half never drifts from the hand-edited half.
"""

import sys
from json import loads
from pathlib import Path
from re import escape as re_escape, findall, search as re_search

import pytest
from babel import Locale
from babel.messages.mofile import read_mo
from babel.messages.pofile import read_po
from babel.support import Translations

REPO = Path(__file__).resolve().parents[3]
LOCALES = REPO / "src" / "ui" / "app" / "static" / "locales"
TRANSLATIONS = REPO / "src" / "ui" / "translations"

sys.path.insert(0, str(REPO / "src" / "ui"))
sys.path.insert(0, str(REPO / "misc" / "dev" / "i18n"))

from app.lang_config import SUPPORTED_LANGUAGES, babel_locale, ui_language  # noqa: E402

from json_to_po import ICU_IN_VALUE, PLURAL_SUFFIX, build, convert, flatten, plural_layout, render  # noqa: E402

CODES = sorted(entry["code"] for entry in SUPPORTED_LANGUAGES)
MUST_LOCALIZE = {"aria.label.plugins_dropzone", "interval.minute"}
CONSISTENT_COPY_GROUPS = (
    ("navigation.redirects", "service.resources.family.redirect"),
    ("dashboard.card.upstreams.title", "navigation.upstreams", "service.resources.family.upstream"),
    ("navigation.workflows", "service.resources.family.workflow"),
    ("redirects.attach", "upstreams.attach", "service.resources.attach"),
    ("reports.card.top_offenders.title", "reports.tab.offenders", "reports.tile.unique_offenders"),
    ("web_cache.reporting_instances", "timings.reporting_instances"),
    ("searchpane.status_code", "table.header.status_code"),
    ("workflows.canvas.exit_title", "workflows.exit_title"),
)
PSEUDO_PLURAL_MARKERS = (
    "(s)",
    "(es)",
    "(i)",
    "(n)",
    "(e)",
    "(y)",
    "(лар)",
    "(лер)",
    "(ы)",
    "(ов)",
    "(ها)",
    "(و)",
    "(ز)",
    "(یں)",
    "(एं)",
    "(एँ)",
    "(ओं)",
    "(याँ)",
    "(গুলি)",
    "(们)",
    "(들)",
    "/i",
)


def _json_keys(code):
    return dict(flatten(loads((LOCALES / f"{code}.json").read_text(encoding="utf-8"))))


def _catalog(code):
    path = TRANSLATIONS / babel_locale(code) / "LC_MESSAGES" / "messages.po"
    with path.open("rb") as handle:
        return read_po(handle, locale=babel_locale(code))


# --------------------------------------------------------------------------------------
# The locale identifiers
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize("code", CODES)
def test_every_language_maps_to_a_locale_babel_understands(code):
    Locale.parse(babel_locale(code))


def test_the_two_codes_that_name_a_different_language_are_mapped():
    """`br` is this UI's Brazilian Portuguese but Breton in CLDR, and `tw` is its Traditional
    Chinese but Twi. Unmapped, Brazilian users would get Breton's four plural forms."""
    assert babel_locale("br") == "pt_BR"
    assert babel_locale("tw") == "zh_Hant"
    assert Locale.parse(babel_locale("br")).english_name == "Portuguese (Brazil)"
    assert Locale.parse(babel_locale("tw")).english_name == "Chinese (Traditional)"
    # And the mapping is invertible, because the UI code is what is stored on the user record.
    assert ui_language("pt_BR") == "br"
    assert ui_language("zh_Hant") == "tw"


def test_filipino_is_mapped_to_the_locale_babel_normalizes_it_to():
    """`tl` isn't a wrong-language code the way `br`/`tw` are, but `Locale.parse("tl")`
    normalizes to `fil_PH` in CLDR — so unmapped, Flask-Babel resolves the catalog directory as
    `fil_PH` while `json_to_po.py` (unmapped) would write it to `tl`, and the Filipino UI falls
    back to English for every string, silently."""
    assert babel_locale("tl") == "fil_PH"
    assert str(Locale.parse(babel_locale("tl"))) == "fil_PH"
    assert ui_language("fil_PH") == "tl"


@pytest.mark.parametrize("code", CODES)
def test_every_ui_code_loads_a_non_empty_translations_catalog(code):
    """The exact lookup Flask-Babel performs at runtime (`Locale.parse` the mapped locale, then
    load `messages.mo` from the directory named after it) — not just that a `.mo` file exists
    somewhere, but that gettext finds it under the identifier Babel will actually ask for."""
    translations = Translations.load(str(TRANSLATIONS), [Locale.parse(babel_locale(code))], domain="messages")

    assert translations._catalog, f"{code}: {babel_locale(code)} loaded an empty (Null) catalog"


# --------------------------------------------------------------------------------------
# The catalogs exist, compile, and match the JSON
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize("code", CODES)
def test_the_catalog_compiles_and_is_loadable(code):
    directory = TRANSLATIONS / babel_locale(code) / "LC_MESSAGES"

    assert (directory / "messages.po").is_file(), f"{code}: run misc/dev/i18n/json_to_po.py"
    with (directory / "messages.mo").open("rb") as handle:
        compiled = read_mo(handle)

    assert len(compiled) > 2000, f"{code}: {len(compiled)} messages compiled"


@pytest.mark.parametrize("code", CODES)
def test_the_catalog_is_in_step_with_the_json(code):
    """`--check` in CI form: editing a JSON catalog without regenerating is the whole failure
    mode of keeping two runtimes on one source."""
    path = TRANSLATIONS / babel_locale(code) / "LC_MESSAGES" / "messages.po"

    assert path.read_bytes() == render(build(code)), f"{code} is stale: run misc/dev/i18n/json_to_po.py"


def test_every_catalog_carries_the_same_message_ids():
    """The JSON catalogs are at strict key parity and a test enforces it; the generated ones
    inherit that, and this is what says so."""
    reference = {message.id for message in _catalog("en") if message.id}

    for code in CODES:
        assert {message.id for message in _catalog(code) if message.id} == reference, code


def test_the_json_to_gettext_count_delta_is_only_plural_folding():
    english = _json_keys("en")
    pairs = {(key, f"{key}{PLURAL_SUFFIX}") for key in english if f"{key}{PLURAL_SUFFIX}" in english}

    assert pairs == {
        ("modal.body.confirm_cache_deletion_alert", "modal.body.confirm_cache_deletion_alert_plural"),
        ("modal.body.confirm_configs_deletion_alert", "modal.body.confirm_configs_deletion_alert_plural"),
        ("modal.body.confirm_plugin_deletion", "modal.body.confirm_plugin_deletion_plural"),
        ("modal.body.confirm_templates_deletion_alert", "modal.body.confirm_templates_deletion_alert_plural"),
        ("modal.body.delete_confirmation_alert", "modal.body.delete_confirmation_alert_plural"),
        ("modal.body.unban_confirmation_alert", "modal.body.unban_confirmation_alert_plural"),
        ("resource_groups.meta_kinds", "resource_groups.meta_kinds_plural"),
        ("resource_groups.meta_usages", "resource_groups.meta_usages_plural"),
        ("resource_groups.meta_values", "resource_groups.meta_values_plural"),
        ("resource_groups.reference_count", "resource_groups.reference_count_plural"),
    }
    # A deliberate tripwire, not a fact about gettext: the number only moves when someone adds or
    # removes keys, and it forces them to look at what they added. Was 2433, then 2471 (the 32
    # `settings.antibot.*` keys of the antibot settings body, 3 catalogue keys and 3 apply-failure
    # keys); 2549 adds the 36 `settings.access_control.*` keys and the 42
    # `settings.modsecurity.*` / `settings.headers.*` keys of the wave 8 configuration pages;
    # 2565 adds the 16 `settings.access_control.rules.*` keys of the composite-rule editor.
    # 2619 adds the 54 wave-12 keys of the instance-enrollment/credential lifecycle, the
    # default-server certificate copy, and the CrowdSec-verdict workflow-condition family.
    # 2632 adds the 13 `bans.flash.*` keys of the bans page flash messages routed through translated().
    # 2634 adds the 2 `settings.header_rules.*` keys of the header-criterion cloner section, shared
    # by the antibot, blacklist, country, greylist and whitelist settings bodies.
    # 2645 adds the 11 keys of the explicit redirect-only declaration (roadmap row 41, lot D): the
    # services-list candidate badge and its tooltip, the `service.mode.*` card on the service
    # settings page, its two action labels and confirm button, and the confirmation modal.
    # CS-2's original 2,786 count included 141 CrowdSec messages. The final 2,779 removes eight
    # unused report/connection keys and adds one distinct failure-policy source label.
    # I18N-FINAL's 3,019 adds the wave-23 fix lanes' 108 new UI keys, the 138 `general.settings.*`
    # keys (label+help for the 69 newly-exposed global settings), and folds one new plural pair
    # (`modal.body.confirm_templates_deletion_alert`) plus three new `resource_groups.meta_*`
    # pairs and `resource_groups.reference_count` into the pair set above (10 pairs, was 5).
    # STAGING A SUBSET OF THOSE MEANS RECOMPUTING THIS.
    # 3,422 adds the FIX-QA5 lanes' 403 keys: every flash / handle_error / TO_FLASH message routed
    # through translated() (page-scoped `*.flash.*` and the shared `flash.*`), tab titles, aria
    # labels, and `tooltip.disabled_by_plugin`. 3,475 adds FIX-QA6's 53: the keys 35 translated()
    # calls named without a catalog entry, the navbar and row-action aria labels, and the
    # services delete modal.
    # 3,486 adds `legend.raw_setting_drafts`, the RAW editor's setting-draft hint (port of dev f8b314a93).
    # 3,497 adds the 11 `raw_drafts.*` flash/validation messages of the port (English only until I18N-SYNC).
    # 3,511 adds FIX-Q8-UI's 15 keys (aria/menu/convert/modal/searchpane/delete-flash) and drops
    # `services.flash.deleted_service`, translated by I18N-T9.
    # 3,610 (+99 net) is FIX-SMOKE-UI and FIX-I18N-NOUNS: whole-sentence `_one`/`_other` and per-noun keys
    # (bulk-select banners, plugin/instance/config/service flashes, workflow announcements) replacing
    # the interpolated-word keys they retired.
    assert len(_catalog("en")) == len(english) - len(pairs) == 3610


@pytest.mark.parametrize("code", CODES)
def test_every_translation_is_non_empty_text(code):
    for key, value in _json_keys(code).items():
        assert isinstance(value, str) and value, key


@pytest.mark.parametrize("code", [code for code in CODES if code != "en"])
def test_required_natural_language_copy_is_localized(code):
    english = _json_keys("en")
    translated = _json_keys(code)

    for key in MUST_LOCALIZE:
        assert translated[key] != english[key], f"{code}/{key} is still English"


@pytest.mark.parametrize("code", CODES)
def test_the_same_ui_concept_uses_consistent_copy(code):
    translated = _json_keys(code)

    for keys in CONSISTENT_COPY_GROUPS:
        values = {translated[key] for key in keys}
        assert len(values) == 1, f"{code}/{keys}: {sorted(values)}"


@pytest.mark.parametrize("code", CODES)
def test_breadcrumb_and_navigation_copy_stays_in_step(code):
    english = _json_keys("en")
    translated = _json_keys(code)
    suffixes = {key.removeprefix("breadcrumb.") for key in english if key.startswith("breadcrumb.")}

    for suffix in suffixes:
        breadcrumb = f"breadcrumb.{suffix}"
        navigation = f"navigation.{suffix}"
        if navigation in english and english[breadcrumb] == english[navigation]:
            assert translated[breadcrumb] == translated[navigation], f"{code}/{suffix}: {translated[breadcrumb]!r} != {translated[navigation]!r}"


@pytest.mark.parametrize("code", CODES)
def test_translations_do_not_fake_plural_morphology_with_parenthetical_suffixes(code):
    """A marker mid-word (`selection/issuance`) is ordinary prose, not a pseudo-plural suffix — the
    lookahead requires the marker not be followed by another word character, same as every
    parenthetical marker here already is by construction (the `)` itself isn't a word char)."""
    for key, value in _json_keys(code).items():
        for marker in PSEUDO_PLURAL_MARKERS:
            assert not re_search(rf"{re_escape(marker)}(?!\w)", value), f"{code}/{key}: {value!r} (marker {marker!r})"


@pytest.mark.parametrize("code", CODES)
def test_translations_preserve_embedded_html(code):
    english = _json_keys("en")
    translated = _json_keys(code)

    for key, source in english.items():
        assert findall(r"</?[^>]+>", translated[key]) == findall(r"</?[^>]+>", source), key


@pytest.mark.parametrize("code", CODES)
def test_translations_preserve_link_targets(code):
    english = _json_keys("en")
    translated = _json_keys(code)

    for key, source in english.items():
        assert findall(r'href=["\']([^"\']+)["\']', translated[key]) == findall(r'href=["\']([^"\']+)["\']', source), key


@pytest.mark.parametrize("code", CODES)
def test_translations_do_not_invent_edge_whitespace(code):
    english = _json_keys("en")
    translated = _json_keys(code)

    for key, source in english.items():
        target = translated[key]
        assert not target[:1].isspace() or source[:1].isspace(), f"{code}/{key}: leading whitespace"
        assert not target[-1:].isspace() or source[-1:].isspace(), f"{code}/{key}: trailing whitespace"


# --------------------------------------------------------------------------------------
# Plurals — in English, French, and locales whose rules differ
# --------------------------------------------------------------------------------------
def test_plural_slot_counts_come_from_the_header_gettext_will_read():
    """Not from the CLDR rule: CLDR gives French three forms and Polish four, while the catalogue
    Babel writes into the PO header — the one `gettext` evaluates — says two and three. Sizing
    the slots from CLDR leaves the extra ones empty and gettext then prints the message id."""
    counts = {code: plural_layout(babel_locale(code))[0] for code in CODES}

    assert counts["en"] == 2
    assert counts["fr"] == 2
    assert counts["pl"] == 3
    assert counts["ar"] == 6
    assert counts["tw"] == 1  # Traditional Chinese does not inflect for number
    assert counts["ru"] == 3


def test_the_singular_slot_is_not_always_slot_zero():
    """Arabic's six forms begin with `zero`, so `n == 1` lands in slot 1. A converter that
    assumed singular-first would put the singular text on n == 0."""
    assert plural_layout("ar")[1] == 1
    assert plural_layout("en")[1] == 0
    assert plural_layout("pl")[1] == 0


@pytest.mark.parametrize("code", ["en", "fr", "pl", "ar", "tw"])
def test_every_plural_entry_fills_every_slot_of_its_locale(code):
    catalog = _catalog(code)
    expected = plural_layout(babel_locale(code))[0]
    plurals = [message for message in catalog if message.pluralizable and message.id]

    assert plurals, f"{code}: no plural entries found at all"
    for message in plurals:
        assert len(message.string) == expected, f"{code}/{message.id}: {len(message.string)} of {expected} slots"
        assert all(form for form in message.string), f"{code}/{message.id} has an empty slot"


@pytest.mark.parametrize("code", ["pl", "ar", "fr"])
def test_the_singular_lands_in_the_slot_that_means_one(code):
    """The check that a mis-sloted converter fails: Polish would show "1 file" wording on 2-4
    items, Arabic on zero items."""
    catalog = _catalog(code)
    message = catalog.get(("modal.body.confirm_cache_deletion_alert", "modal.body.confirm_cache_deletion_alert_plural"))
    source = _json_keys(code)
    num_plurals, singular_slot = plural_layout(babel_locale(code))

    assert message is not None
    assert message.string[singular_slot] == source["modal.body.confirm_cache_deletion_alert"]
    for slot in range(num_plurals):
        if slot != singular_slot:
            assert message.string[slot] == source["modal.body.confirm_cache_deletion_alert_plural"], slot


# --------------------------------------------------------------------------------------
# Placeholders — the `%` rule, which is the one that raises at runtime
# --------------------------------------------------------------------------------------
def test_interpolation_becomes_a_python_placeholder():
    assert convert("Export {{service}} now", formatted=True) == "Export %(service)s now"
    assert convert("{{ spaced }}", formatted=True) == "%(spaced)s"


def test_a_literal_percent_is_escaped_only_where_formatting_happens():
    """`Domain.gettext` applies `s % variables` *only* when variables are passed. Escaping a
    string that is never formatted would print `%%` at the user; not escaping one that is
    formatted raises `ValueError: unsupported format character`."""
    assert convert("{{percent}}% used", formatted=True) == "%(percent)s%% used"
    assert convert("Selected %d Bans", formatted=False) == "Selected %d Bans"


@pytest.mark.parametrize("code", CODES)
def test_no_formatted_message_carries_an_unescaped_percent(code):
    """The runtime failure this prevents is a 500 on whichever page renders that string."""
    for message in _catalog(code):
        if not message.id:
            continue
        forms = message.string if isinstance(message.string, tuple) else (message.string,)
        for form in forms:
            if not form or "%(" not in form:
                continue
            # Every `%` must open either a named placeholder or an escape.
            stripped = form.replace("%(", "\x00").replace("%%", "")
            assert "%" not in stripped, f"{code}/{message.id}: unescaped % in {form!r}"


@pytest.mark.parametrize("code", CODES)
def test_a_translation_never_invents_or_drops_a_placeholder(code):
    """A missing placeholder is a KeyError at render time in the locale nobody tested."""
    english = _catalog("en")
    catalog = _catalog(code)

    for message in english:
        if not message.id:
            continue
        translated = catalog.get(message.id, context=message.context)
        if translated is None:
            continue
        source_forms = message.string if isinstance(message.string, tuple) else (message.string,)
        target_forms = translated.string if isinstance(translated.string, tuple) else (translated.string,)
        if any(form and ICU_IN_VALUE.search(form) for form in source_forms):
            continue  # see test_only_one_key_still_carries_an_icu_plural
        expected = {name for form in source_forms if form for name in _placeholders(form)}
        for form in target_forms:
            if not form:
                continue
            assert _placeholders(form) == expected, f"{code}/{message.id}: placeholder mismatch in {form!r}"


def _placeholders(text):
    from re import findall

    return set(findall(r"%\((\w+)\)", text))


def test_catalog_values_do_not_embed_icu_syntax_the_browser_cannot_render():
    """The browser helper interpolates simple `{{name}}` placeholders, not ICU expressions.

    Count-heavy copy uses invariant labels instead, so every locale renders a number rather than
    exposing `{{count, plural, ...}}` as literal UI text.
    """
    icu = {key for key, value in _json_keys("en").items() if isinstance(value, str) and ICU_IN_VALUE.search(value)}

    assert not icu
