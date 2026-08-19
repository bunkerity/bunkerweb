#!/usr/bin/env python3
"""Convert the i18next JSON catalogs into gettext PO/MO catalogs.

    python3 misc/dev/i18n/json_to_po.py            # regenerate every locale
    python3 misc/dev/i18n/json_to_po.py --check    # fail if the output would differ

Lot A of the native-i18n work. The 18 JSON catalogs in `src/ui/app/static/locales/` stay the
source of truth until the last template stops using `data-i18n` (Lot D); this script is what
keeps `src/ui/translations/` in step with them, so a translator keeps editing one thing.

Three decisions worth knowing before reading the code:

**The message id is the dotted key, not the English text.** The catalogs have always been keyed
(`button.create_service`), the `data-i18n` attributes name those keys, and 2338 × 18 strings are
already translated against them. Using the English text as the id — the usual gettext convention —
would mean re-keying every catalog for no gain. `en` is therefore a real compiled catalog rather
than a fallback to the id.

**Interpolation becomes `%(name)s`, and literal `%` needs care.** `Domain.gettext` applies
`s % variables` *only when variables are passed*, and `Domain.ngettext` always passes at least
`num`. So a literal `%` has to be doubled exactly when the entry is one that gets formatted:
anything with interpolation, and every plural entry. Doubling it anywhere else would print `%%`
at the user. Two keys make this real — `'{{percent}}% used'` and `'{{percent}}% blocked'`.

**Two of the UI's language codes are not the locale they name.** `br` is the UI's Brazilian
Portuguese but Breton in CLDR, and `tw` is its Traditional Chinese but Twi. Left alone, Babel
would give Brazilian users Breton's four plural forms. `app/lang_config.py` maps them.
"""

from argparse import ArgumentParser
from json import loads
from pathlib import Path
from re import compile as re_compile
from sys import exit as sys_exit, path as sys_path

from gettext import c2py

from babel.messages.catalog import Catalog
from babel.messages.mofile import write_mo
from babel.messages.plurals import get_plural
from babel.messages.pofile import read_po, write_po

REPO = Path(__file__).resolve().parents[3]
LOCALES = REPO / "src" / "ui" / "app" / "static" / "locales"
# Flask-Babel's default, resolved against the app root (`src/ui`), and inside what every image
# already copies with `COPY src/ui ui` — so no packaging target can forget it.
TRANSLATIONS = REPO / "src" / "ui" / "translations"

sys_path.insert(0, str(REPO / "src" / "ui"))
from app.lang_config import babel_locale  # noqa: E402

PLURAL_SUFFIX = "_plural"
INTERPOLATION = re_compile(r"\{\{\s*(\w+)\s*\}\}")

# One key carries i18next's ICU-style plural *inside* its value
# (`{{count, plural, one {# setting available} other {# settings available}}}`) rather than as a
# `_plural` sibling. It is copied through untouched: five of the eighteen catalogs already
# flattened it to a plain `{{count}}` on their own, so the source data does not agree with itself
# about it, and one key does not justify an ICU parser. Whoever converts its template
# (models/template_steps_body.html) turns it into a real `ngettext` call and splits the key then.
# `tests/unit/ui/test_i18n_catalogs.py` fails if a second such key appears.
ICU_IN_VALUE = re_compile(r"\{\{\s*\w+\s*,")


def flatten(node, prefix=""):
    """The catalogs are nested; the keys the app uses are dotted."""
    for key, value in node.items():
        if isinstance(value, dict):
            yield from flatten(value, f"{prefix}{key}.")
        else:
            yield f"{prefix}{key}", value


def convert(value: str, *, formatted: bool) -> str:
    """`{{name}}` -> `%(name)s`, escaping literal `%` only where `%`-formatting will happen.

    The escape has to come first, or the `%(` this function inserts would be escaped too.
    """
    if formatted:
        value = value.replace("%", "%%")
    return INTERPOLATION.sub(r"%(\1)s", value)


def plural_layout(locale_id: str):
    """`(number of slots, which slot means n == 1)` for a locale.

    Read from the *gettext* expression Babel writes into the PO header and `gettext` evaluates at
    runtime — not from the CLDR rule, which disagrees: CLDR gives French three forms and Polish
    four, Babel's catalogue two and three. Slots sized by the wrong one leave the last form empty,
    and gettext then falls back to printing the message id.

    Nor is the singular always slot 0: Arabic's six forms start with `zero`, so `n == 1` is slot 1.
    `gettext.c2py` is the standard library's own parser for that expression, which makes this the
    same answer the runtime will reach.

    The JSON only ever holds a singular and a plural, so the `n == 1` slot takes the singular and
    every other slot takes the plural — the honest limit of what the source catalogs express.
    """
    spec = get_plural(locale_id)
    return spec.num_plurals, c2py(spec.plural_expr)(1)


def build(code: str) -> Catalog:
    locale_id = babel_locale(code)
    messages = dict(flatten(loads((LOCALES / f"{code}.json").read_text(encoding="utf-8"))))
    english = dict(flatten(loads((LOCALES / "en.json").read_text(encoding="utf-8"))))

    # The *English* catalog decides what is a plural pair, so every locale ends up with the same
    # message set even if a translation is missing one half.
    pairs = {key for key in english if f"{key}{PLURAL_SUFFIX}" in english}
    folded = {f"{key}{PLURAL_SUFFIX}" for key in pairs}

    catalog = Catalog(
        locale=locale_id,
        domain="messages",
        project="BunkerWeb UI",
        fuzzy=False,
        charset="utf-8",
    )
    num_plurals, singular_slot = plural_layout(locale_id)

    for key in english:
        if key in folded:
            continue
        value = messages.get(key)
        if value is None or not isinstance(value, str):
            continue

        if key in pairs:
            plural_value = messages.get(f"{key}{PLURAL_SUFFIX}", value)
            # Always formatted: ngettext passes `num` whether the string uses it or not.
            singular = convert(value, formatted=True)
            plural = convert(plural_value, formatted=True)
            catalog.add(
                (key, f"{key}{PLURAL_SUFFIX}"),
                tuple(singular if slot == singular_slot else plural for slot in range(num_plurals)),
                auto_comments=[f"plural pair; {num_plurals} form(s) for {locale_id}, singular in slot {singular_slot}"],
            )
            continue

        # An ICU-in-value entry is copied through verbatim: it is not a placeholder this
        # converter understands, and `%`-escaping it would corrupt text nothing formats.
        if ICU_IN_VALUE.search(value):
            catalog.add(key, value, auto_comments=["ICU plural left as-is; split when its template is converted"])
            continue

        catalog.add(key, convert(value, formatted=bool(INTERPOLATION.search(value))))

    return catalog


def render(catalog: Catalog) -> bytes:
    from io import BytesIO

    buffer = BytesIO()
    write_po(buffer, catalog, width=0, sort_output=True, omit_header=False)
    # The header carries a generation date, which would make every run a diff.
    return b"\n".join(line for line in buffer.getvalue().split(b"\n") if not line.startswith((b'"POT-Creation-Date', b'"PO-Revision-Date')))


def main() -> int:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if the catalogs are out of date instead of writing them")
    args = parser.parse_args()

    codes = sorted(path.stem for path in LOCALES.glob("*.json"))
    stale = []

    for code in codes:
        catalog = build(code)
        target = TRANSLATIONS / babel_locale(code) / "LC_MESSAGES"
        po_path, mo_path = target / "messages.po", target / "messages.mo"
        rendered = render(catalog)

        if args.check:
            if not po_path.is_file() or po_path.read_bytes() != rendered:
                stale.append(code)
            continue

        target.mkdir(parents=True, exist_ok=True)
        po_path.write_bytes(rendered)
        with po_path.open("rb") as handle, mo_path.open("wb") as out:
            write_mo(out, read_po(handle, locale=babel_locale(code)))
        print(f"{code:5} -> {po_path.relative_to(REPO)}  ({len(catalog)} messages)")

    if args.check:
        if stale:
            print(f"out of date: {', '.join(stale)}\nrun: python3 misc/dev/i18n/json_to_po.py")
            return 1
        print(f"{len(codes)} catalogs up to date")
    return 0


if __name__ == "__main__":
    sys_exit(main())
