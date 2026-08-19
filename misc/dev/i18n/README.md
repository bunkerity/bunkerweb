# Native i18n: the gettext catalogs

Every string used to be translated **in the browser**: the page shipped in English, i18next fetched
a 2338-key JSON catalog, then rewrote the DOM. That cost a visible flash of English on every load,
a full-document scan per page, and it made anything rendered afterwards — a table row built on
draw, a toast — responsible for re-translating itself.

Flask-Babel sits underneath now and every template arrives translated. The browser keeps a `t()`
for the strings JavaScript builds itself, over a catalog served as a plain script; the i18next
libraries are gone. Both halves read the same message ids.

## The JSON stays the source of truth

`src/ui/app/static/locales/*.json` is what translators edit; `src/ui/translations/` is generated
from it. One source, so the catalogs cannot disagree.

```bash
tests/unit/.venv-unit/bin/python misc/dev/i18n/json_to_po.py           # regenerate all 18 locales
tests/unit/.venv-unit/bin/python misc/dev/i18n/json_to_po.py --check   # fail if they are stale
```

**Run it with the unit-test venv's interpreter, not the system one.** Babel stamps its own version
into every PO header (`Generated-By: Babel 2.18.0`), and `tests/unit/ui/test_i18n_catalogs.py`
compares the files byte for byte against a fresh generation. A system Python with a different Babel
rewrites all eighteen headers and the suite then reports every catalog as stale — the script's own
`--check` says they are fine, because it agrees with whichever Babel just wrote them.

`tests/unit/ui/test_i18n_catalogs.py` runs the same check, so editing a JSON catalog without
regenerating fails the suite rather than shipping a half-translated page.

The JSON is still the source because the browser reads it directly — `/locales/<lang>.js` serves it
as `window.BW_I18N`. Making the PO files the source means giving the browser a generated JSON, which
is a swap worth making only once translators are actually editing PO.

## Three things that are not obvious

**The message id is the dotted key**, not the English text. 2338 × 18 strings are already
translated against `button.create_service`-style keys and the `data-i18n` attributes name them.
`en` is therefore a real compiled catalog, not a fallback to the id.

**Two language codes name a different language than they are used for.** `br` is the UI's
Brazilian Portuguese but Breton in CLDR; `tw` is its Traditional Chinese but Twi. Unmapped, Babel
gives Brazilian users Breton's plural rules. `app/lang_config.py` maps them to `pt_BR` and
`zh_Hant`; the UI codes stay as they are, because they are stored on user records and drive the
flag lookup.

**A literal `%` has to be escaped exactly where formatting happens, and nowhere else.**
`Domain.gettext` applies `s % variables` *only* when variables are passed, and `Domain.ngettext`
always passes `num`. So:

| Entry | Escaped? | Why |
| --- | --- | --- |
| `'{{percent}}% used'` → `'%(percent)s%% used'` | yes | has interpolation, so it is formatted |
| `'Selected %d Bans'` | no | no variables, never formatted — `%%` would reach the user |
| any plural entry | yes | `ngettext` always formats |

Get it wrong in the first row and the dashboard 500s with `unsupported format character`.

## Plural slots

The number of `msgstr[]` slots comes from the **gettext expression Babel writes into the PO
header**, not from the CLDR rule — they disagree (CLDR gives French 3 forms and Polish 4; the
catalogue says 2 and 3). And the singular is not always slot 0: Arabic's six forms start with
`zero`, so `n == 1` is slot 1. `gettext.c2py` resolves it, which is the same parser the runtime
uses.

The JSON only holds a singular and a plural, so richer locales get the singular in the `n == 1`
slot and the plural everywhere else. That is the honest limit of the source data, not a bug to fix
here — a translator wanting Polish's three real forms edits the PO after Lot D.

## Known gap: one ICU-in-value key

`template.editor.setting_selector_count_only_available` holds
`{{count, plural, one {# setting available} other {# settings available}}}` — i18next's ICU syntax
inside the value. gettext has no equivalent, so the converter copies it through untouched and it
is migrated by hand when `models/template_steps_body.html` is converted.

It is pinned rather than fixed because the source data already disagrees with itself: five of the
eighteen catalogs (ar, ko, tr, tw, zh) flattened it to a plain `{{count}}` long ago, so those five
translations are structurally different from the English *today*. A second such key fails
`test_only_one_key_still_carries_an_icu_plural`.

## Locale selection

`app/i18n.resolve_locale`, in order: the signed-in user's saved language → the session language
(what `/set_language` sets, and an anonymous visitor's only source) → `Accept-Language` matched
against the locales that have a catalog → English. It never raises, including outside a request
context, because Flask-Babel calls it from places that are not always one.

## Packaging

`src/ui/translations/` sits next to `main.py`, and every image copies the tree wholesale with
`COPY src/ui ui` — so no packaging target can ship without the catalogs. That is deliberate: the
alternative, compiling in each Dockerfile, is thirteen edits and one of them gets forgotten.

**The UI's requirements are not independent.** `src/ui/Dockerfile` installs `src/ui`,
`src/common/gen` and `src/common/db` requirements into one `pip install --require-hashes`, so a
package pinned twice at two versions fails the build outright. Adding Flask-Babel did this: Babel
pulls `pytz`, and `src/common/gen` was already pinning a different version.
`tests/unit/integrations/test_requirements_coinstall.py` now catches it before a build does.

## Lot B: the shared socle is converted

The layout, navigation, auth pages, error pages and the whole of `components/` now render through
`_()`. `tests/unit/ui/test_i18n_migration.py` holds the registry: a template listed there may not
contain a single `data-i18n*` attribute, and must call `_()`. Page templates are Lot C and still
carry `data-i18n`, which is fine — translation is per element, so a converted macro arrives
translated on an unconverted page.

Two things a conversion has to check, both learned the hard way here:

**Does any JavaScript read the key out of the rendered markup?** Twenty-two DataTables SearchPane
filters did: `rowData[4].includes("interval.day")` worked only because the key sat in the cell
waiting for the DOM pass. Converted macros do not emit it, so those filters silently matched
nothing — an empty table, no error. They now match `data-value`, which `badge.html` and
`status.html` already carried for exactly this, and `tests/unit/ui/test_searchpane_filters.py`
bans the old form so the next conversion cannot reintroduce it.

**Does the key exist?** gettext answers a missing key with the key itself, so a key that is not
in the catalog — a rename that missed a call site, a `button.save_all` where only `button.save`
exists — ships to the user as that literal dotted string, and nothing fails. `test_every_data_i18n_key_resolves_in_en_json` now
scans `_("...")` calls as well as `data-i18n` attributes.

## Lot C: every template, and Lot D: no client library

Lot C converted the page templates; Lot D removed the runtime that used to translate them.

Gone: the three i18next scripts (57 KB), the XHR that fetched the catalog, `window.i18nextReady`
and the nine page scripts that polled it every 50 ms before drawing a table, and the
full-document `data-i18n` scan on load.

In their place, `/locales/<lang>.js` (`src/ui/main.py`, body in `app/i18n.browser_catalog`) serves
the locale's catalog as `window.BW_I18N`, loaded by a plain `<script>` ahead of every page script.
`t()` in `i18n.js` reads it synchronously, so there is nothing to wait for. `window.i18next` stays
as a shim — `t`, `language`, `isInitialized`, `on`/`off` — because plugin front-ends call it and a
dozen call sites in this tree still guard on it.

`applyTranslations()` survives, but only as something a caller invokes on markup **it just built**
from a string: DataTables column titles, the template editor's panes, the workflow canvas. Those
have no server render to attach to. It no longer runs on load, and nothing should make it.

Two consequences worth knowing:

- **A language switch reloads the page.** It has to — the catalog, the chrome and the copy are all
  served for one locale. `changeLanguage` posts to `/set_language` and reloads only once the server
  confirms; there is no client-side half left to switch if the request fails.
- **`t()` escapes interpolated values by default**, exactly as i18next did, because several call
  sites drop the result into HTML. `{ interpolation: { escapeValue: false } }` is the opt-out.
  `tests/unit/ui/test_i18n_attributes.py` runs the real function under node and covers this.
