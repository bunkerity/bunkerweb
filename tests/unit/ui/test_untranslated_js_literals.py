"""First-party JavaScript must not bypass the UI translation catalogs with visible English copy.

The lexical walker deliberately ignores comments, regex literals and template literals, matching
the shared `_jsscan.py` contract. A natural-language string inside a bare `t(...)` call is an
English fallback and is valid. Everything else must either enter the catalog or be listed below
with the concrete reason it is not user copy.
"""

import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _jsscan import (  # noqa: E402
    Source,
    _REGEX_MAY_START,
    _balanced,
    _skip_quoted,
    _skip_regex,
    _starts_an_identifier,
    _template_text,
    string_value,
    track_substitutions,
)

REPO = Path(__file__).resolve().parents[3]
JS = REPO / "src" / "ui" / "app" / "static" / "js"

# `(relative path, literal): catalog key or mechanism that replaces this English default`.
CATALOG_FALLBACKS = {
    ("components/secret-field.js", "Hide value"): "aria.label.hide_value via t() fallback variable",
    ("components/secret-field.js", "Reveal value"): "aria.label.reveal_value via t() fallback variable",
    ("main.js", "No items found."): "status.no_search_results fallback",
    ("modules/setting_controls.js", "Enabled"): "template.editor.setting_toggle_enabled via setContent()",
    ("modules/setting_controls.js", "Select options"): "template.editor.multiselect_placeholder via setContent()",
    ("modules/setting_controls.js", "{{count}} selected"): "template.editor.multiselect_summary via setContent()",
    ("modules/setting_controls.js", "No items found."): "status.no_search_results via setContent()",
    ("modules/setting_controls.js", "One value per line.{{separatorNote}}"): "template.editor.multivalue_helper via setContent()",
    ("modules/setting_controls.js", "Add value"): "template.editor.multivalue_add via setContent()",
    ("pages/bans.js", "The date and time when the Ban was created"): "tooltip.table.bans.date via data-i18n and applyTranslations()",
    ("pages/bans.js", "The banned IP address"): "tooltip.table.bans.ip_address via data-i18n and applyTranslations()",
    ("pages/bans.js", "The banned IP country"): "tooltip.table.bans.country via data-i18n and applyTranslations()",
    ("pages/bans.js", "The reason why the Report was created"): "tooltip.table.bans.reason via data-i18n and applyTranslations()",
    ("pages/bans.js", "The scope of the ban (global or service-specific)"): "tooltip.table.bans.scope via data-i18n and applyTranslations()",
    ("pages/bans.js", "The service that created the ban"): "tooltip.table.bans.service via data-i18n and applyTranslations()",
    ("pages/bans.js", "The end date of the Ban"): "tooltip.table.bans.end_date via data-i18n and applyTranslations()",
    ("pages/bans.js", "The time left until the Ban expires"): "tooltip.table.bans.time_left via data-i18n and applyTranslations()",
    ("pages/bans.js", "Actions that can be performed on the ban"): "tooltip.table.bans.actions via data-i18n and applyTranslations()",
    ("pages/bans.js", "Are you sure you want to unban all {{count}} matching bans?"): "modal.body.unban_filtered_confirmation fallback variable",
    ("pages/bans.js", "Are you sure you want to unban the selected IP address(es)?"): "modal.body.unban_confirmation_alert fallback variable",
    ("pages/bans.js", "Select a new duration for all {{count}} matching bans:"): "modal.body.update_filtered_duration_alert fallback variable",
    ("pages/bans.js", "Select a new duration for the selected bans:"): "modal.body.update_duration_alert fallback variable",
    ("pages/bans.js", "Your account is readonly, action disabled."): "tooltip.readonly_user_action_disabled fallback variable",
    ("pages/bans.js", "The database is in readonly, action disabled."): "tooltip.readonly_db_action_disabled fallback variable",
    ("pages/configs.js", "Your account is readonly, action disabled."): "tooltip.readonly_user_action_disabled fallback variable",
    ("pages/configs.js", "The database is in readonly, action disabled."): "tooltip.readonly_db_action_disabled fallback variable",
    ("pages/home.js", "No data to show"): "status.no_data fallback",
    ("pages/instances.js", "Your account is readonly, action disabled."): "tooltip.readonly_user_action_disabled fallback variable",
    ("pages/instances.js", "The database is in readonly, action disabled."): "tooltip.readonly_db_action_disabled fallback variable",
    ("pages/logs-classify.js", "Critical"): "logs.level_critical via logs.js translator",
    ("pages/logs-classify.js", "Error"): "logs.level_error via logs.js translator",
    ("pages/logs-classify.js", "Warning"): "logs.level_warning via logs.js translator",
    ("pages/logs-classify.js", "Notice"): "logs.level_notice via logs.js translator",
    ("pages/logs-classify.js", "Info"): "logs.level_info via logs.js translator",
    ("pages/logs-classify.js", "Debug"): "logs.level_debug via logs.js translator",
    ("pages/plugin_page.js", "Date"): "searchpane.date fallback",
    ("pages/plugin_page.js", "IP Address"): "searchpane.ip_address fallback",
    ("pages/plugin_page.js", "Country"): "searchpane.country fallback",
    ("pages/plugin_page.js", "Server"): "searchpane.server_name fallback",
    ("pages/plugin_page.js", "Method"): "searchpane.method fallback",
    ("pages/plugin_page.js", "URL"): "searchpane.url fallback",
    ("pages/plugin_page.js", "Status Code"): "searchpane.status_code fallback",
    ("pages/plugin_page.js", "Security Mode"): "searchpane.security_mode fallback",
    ("pages/plugin_page.js", "Ban Scope"): "searchpane.ban_scope fallback",
    ("pages/reports.js", "The date and time when the Report was created"): "tooltip.table.reports.date via data-i18n and applyTranslations()",
    ("pages/reports.js", "The unique identifier for the request"): "tooltip.table.reports.request_id via data-i18n and applyTranslations()",
    ("pages/reports.js", "The reported IP address"): "tooltip.table.reports.ip_address via data-i18n and applyTranslations()",
    ("pages/reports.js", "The country of the reported IP address"): "tooltip.table.reports.country via data-i18n and applyTranslations()",
    ("pages/reports.js", "The method used by the attacker"): "tooltip.table.reports.method via data-i18n and applyTranslations()",
    ("pages/reports.js", "The URL that was targeted by the attacker"): "tooltip.table.reports.url via data-i18n and applyTranslations()",
    ("pages/reports.js", "The HTTP status code returned by BunkerWeb"): "tooltip.table.reports.status_code via data-i18n and applyTranslations()",
    ("pages/reports.js", "The User-Agent of the attacker"): "tooltip.table.reports.user_agent via data-i18n and applyTranslations()",
    ("pages/reports.js", "The reason why the Report was created"): "tooltip.table.reports.reason via data-i18n and applyTranslations()",
    ("pages/reports.js", "The Server name that created the report"): "tooltip.table.reports.server_name via data-i18n and applyTranslations()",
    ("pages/reports.js", "Additional data about the Report"): "tooltip.table.reports.data via data-i18n and applyTranslations()",
    ("pages/reports.js", "Security mode"): "tooltip.table.reports.security_mode via data-i18n and applyTranslations()",
    ("pages/reports.js", "HTTP request, or TCP/UDP stream session"): "tooltip.table.reports.protocol via data-i18n and applyTranslations()",
    ("pages/reports.js", "Stream only: the port the session came in on"): "tooltip.table.reports.listen_port via data-i18n and applyTranslations()",
    ("pages/reports.js", "Stream only: the client's source port"): "tooltip.table.reports.client_port via data-i18n and applyTranslations()",
    ("pages/reports.js", "Stream only: bytes sent to the client during the session"): "tooltip.table.reports.bytes_sent via data-i18n and applyTranslations()",
    (
        "pages/reports.js",
        "Stream only: bytes received from the client during the session",
    ): "tooltip.table.reports.bytes_received via data-i18n and applyTranslations()",
    ("pages/reports.js", "Stream only: how long the session lasted, in seconds"): "tooltip.table.reports.session_time via data-i18n and applyTranslations()",
    ("pages/reports.js", "Actions available for this report"): "tooltip.table.reports.actions via data-i18n and applyTranslations()",
    ("pages/services.js", "Name"): "table.header.name via selected-list translator",
    ("pages/services.js", "Type"): "table.header.type via selected-list translator",
    ("pages/settings-raw.js", "Disclaimer"): "toast.disclaimer_title synchronous replacement",
    ("pages/template_edit.js", "No settings to display."): "template.editor.setting_selector_count_empty fallback",
    ("pages/template_edit.js", "All matching settings have already been added."): "template.editor.setting_selector_count_all_used fallback",
    ("pages/template_edit.js", "1 setting available"): "template.editor.setting_selector_count_only_available fallback",
    ("pages/template_edit.js", "Select a type"): "template.editor.select_config_type_placeholder via runTranslations()",
    ("pages/template_edit.js", "Step"): "template.editor.step_prefix fallback",
    ("pages/template_edit.js", "Untitled step"): "template.editor.step_default_title fallback",
    ("pages/threatmap.js", "Show top "): "threatmap.show_less fallback",
    ("pages/threatmap.js", "Show all "): "threatmap.show_more fallback",
    ("pages/threatmap.js", "Exit fullscreen"): "threatmap.exit_fullscreen fallback",
    ("pages/threatmap.js", "Fullscreen"): "threatmap.fullscreen fallback",
    ("pages/workflow_editor.js", "Challenge"): "workflows.act_challenge via data-i18n and runTranslations()",
    ("pages/workflow_editor.js", "Block"): "workflows.act_block via data-i18n and runTranslations()",
    ("pages/workflow_editor.js", "Redirect"): "workflows.act_redirect via data-i18n and runTranslations()",
    ("pages/workflow_editor.js", "is in"): "workflows.verb.ip fallback metadata",
    ("pages/workflow_editor.js", "is in the group"): "workflows.verb.group fallback metadata",
    ("pages/workflow_editor.js", "All of"): "workflows.tree.all via data-i18n and runTranslations()",
    ("pages/workflow_editor.js", "Any of"): "workflows.tree.any via data-i18n and runTranslations()",
    ("pages/workflow_editor.js", "None of"): "workflows.tree.not via data-i18n and runTranslations()",
    ("pages/workflow_editor.js", "Every request to an attached service"): "workflows.entry_title via data-i18n and runTranslations()",
    ("pages/workflow_editor.js", "no match"): "workflows.link.noMatch via data-i18n and runTranslations()",
    ("pages/workflow_editor.js", "No rule matched"): "workflows.exit_title via data-i18n and runTranslations()",
    (
        "pages/workflow_editor.js",
        "The request continues to the next attached workflow, then to the rest of the security stack.",
    ): "workflows.exit_sub via data-i18n and runTranslations()",
    ("pages/workflow_editor.js", "every request"): "workflows.link.entry via data-i18n and runTranslations()",
    ("pages/workflow_editor.js", "'>Runs at position "): "workflows.canvas.drawerSub fallback markup",
    ("pages/workflow_editor.js", "Every request"): "workflows.canvas.entry_title via data-i18n and runTranslations()",
    ("pages/workflow_editor.js", "Rules run left to right."): "workflows.canvas.entry_sub via data-i18n and runTranslations()",
    ("pages/workflow_editor.js", "Continues to the next attached workflow."): "workflows.canvas.exit_sub via data-i18n and runTranslations()",
    ("pages/workflow_editor.js", " rules · largest rule uses "): "workflows.capacity fallback fragment",
    ("pages/workflow_editor.js", " in this workflow</span>"): "workflows.capacity fallback fragment",
    ("pages/workflow_editor.js", " problem blocks the save."): "workflows.errors.count fallback fragment",
    ("pages/workflow_editor.js", " problems block the save."): "workflows.errors.count fallback fragment",
    ("pages/workflow_editor.js", "Request number {{request_number}} is your input, not a measurement."): "workflows.test.assume_rate_counter fallback metadata",
    ("pages/workflow_editor.js", "Assumes the client is not whitelisted."): "workflows.test.assume_not_whitelisted fallback metadata",
    ("pages/workflow_editor.js", "Assumes the instance's regex budget is not exhausted."): "workflows.test.assume_regex_budget fallback metadata",
}

# Reasoned allowlists for source that cannot render user copy and for shared code tokens.
NON_COPY_FILES = {
    "config.js": "theme color constants, never rendered as copy",
    "mode-modsecurity.js": "ACE syntax-highlighting grammar tokens",
    "pages/ace-mode-bunkerweb_log.js": "ACE syntax-highlighting grammar tokens",
    "pages/ace-mode-bunkerweb_settings.js": "ACE syntax-highlighting grammar tokens",
}
NON_COPY_VALUES = {
    "(prefers-reduced-motion: reduce)": "CSS media query",
    "AbortError": "WebAuthn exception name",
    "ArrowDown": "keyboard key value",
    "ArrowLeft": "keyboard key value",
    "ArrowRight": "keyboard key value",
    "ArrowUp": "keyboard key value",
    "BODY": "DOM tag name",
    "BUTTON": "DOM tag name",
    "BunkerWeb UI": "product name",
    "BunkerWebGeoData": "global data-object identifier",
    "Command-S": "aria-keyshortcuts token",
    "Content-Type": "HTTP header name",
    "Ctrl-S": "aria-keyshortcuts token",
    "DELETE": "HTTP method token",
    "DOMContentLoaded": "browser lifecycle event name",
    "Enter": "keyboard key value",
    "English": "English language endonym",
    "Escape": "keyboard key value",
    "False": "serialized boolean sentinel",
    "F j, Y h:i K": "Flatpickr date-format expression",
    "GET": "HTTP method token",
    "HTTP": "configuration type token",
    "Location": "HTTP header name",
    "MODSEC": "configuration type token",
    "MozTransition": "browser transition property name",
    "MultiPolygon": "GeoJSON geometry type",
    "NGINX": "product and configuration type name",
    "NotAllowedError": "WebAuthn exception name",
    "OPTIONS": "HTTP method token",
    "OTransition": "browser transition property name",
    "PATCH": "HTTP method token",
    "POST": "HTTP method token",
    "PUT": "HTTP method token",
    "Polygon": "GeoJSON geometry type",
    "Public Sans": "font-family name",
    "Public Sans, sans-serif": "CSS font-family value",
    "STREAM": "configuration type token",
    "Spacebar": "keyboard key value",
    "True": "serialized boolean sentinel",
    "WebkitTransition": "browser transition property name",
    "X-CSRFToken": "HTTP header name",
    "X-Requested-With": "HTTP header name",
    "XMLHttpRequest": "HTTP header value",
    "active show": "Bootstrap state classes",
    "Are you sure you want to leave? Changes you made may not be saved.": "custom beforeunload text is ignored; browsers show their own localized prompt",
    "DataTables AJAX error:": "console-only diagnostic prefix",
    "Failed to copy text: ": "console-only diagnostic prefix",
    "Network response was not ok": "internal fetch error used only for diagnostics",
    "There was a problem with the fetch operation:": "console-only diagnostic prefix",
    "beforeunload pagehide": "browser lifecycle event names",
    "button, a, input, select": "focusable-element selector",
    "button, input, select, a, .bw-flow-act": "focusable-element selector",
    "collapse show": "Bootstrap state classes",
    "focus blur": "DOM event names",
    "input change": "DOM event names",
    "input, select": "form-control selector",
    "input, select, textarea": "form-control selector",
    "keydown keyup": "DOM event names",
    "noopener noreferrer": "anchor rel attribute value",
    "select deselect draw page length search": "DataTables event names",
    "select.dt deselect.dt": "DataTables event names",
    "show active": "Bootstrap state classes",
    "Shift+ArrowUp Shift+ArrowDown": "aria-keyshortcuts token list",
    "thead th": "table-header selector",
    "textarea, input": "form-control selector",
    "toast show": "Bootstrap toast state classes",
    "use strict": "JavaScript strict-mode directive",
    "wheel touchmove": "DOM event names",
}

# `(relative path, literal): why this is intentionally not translated`.
NON_COPY = {
    ("components/recovery-code.js", "Failed to copy recovery codes: "): "console-only diagnostic prefix",
    ("components/settings-widgets.js", "Unable to read the selected file."): "discarded Error message; callers render their own feedback",
    ("i18n.js", "Error parsing data-i18n-options:"): "console-only diagnostic prefix",
    ("i18n.js", "Failed to parse supported languages JSON:"): "console-only diagnostic prefix",
    ("i18n.js", "CSRF token not found, cannot save language preference to server"): "console-only diagnostic",
    ("i18n.js", "Error saving language preference to server:"): "console-only diagnostic prefix",
    ("helpers.js", "HTML"): "a DOM tagName compared against `el.tagName.toUpperCase()`, not copy",
    ("helpers.js", "Event"): "the DOM interface name passed to `document.createEvent`",
    ("helpers.js", "IEMobile"): "a user-agent token matched with `indexOf`",
    ("menu.js", "Cannot find `.menu-sub` element for the current `.menu-toggle`"): "developer exception for invalid menu markup",
    ("menu.js", "Toggable "): "interpolated into a developer `Error()` about missing `.menu-item` markup",
    ("pages/bans.js", "Date"): "unused headers metadata",
    ("pages/bans.js", "IP Address"): "unused headers metadata",
    ("pages/bans.js", "Country"): "unused headers metadata",
    ("pages/bans.js", "Reason"): "unused headers metadata",
    ("pages/bans.js", "Scope"): "unused headers metadata",
    ("pages/bans.js", "Service"): "unused headers metadata",
    ("pages/bans.js", "End date"): "unused headers metadata",
    ("pages/bans.js", "Time left"): "unused headers metadata",
    ("pages/bans.js", "Actions"): "unused headers metadata",
    ("pages/home.js", "IndexedDB get failed:"): "console-only diagnostic prefix",
    ("pages/home.js", "IndexedDB set failed:"): "console-only diagnostic prefix",
    ("pages/home.js", "localStorage get failed, trying IndexedDB:"): "console-only diagnostic prefix",
    ("pages/home.js", "localStorage quota exceeded, using IndexedDB:"): "console-only diagnostic prefix",
    ("pages/home.js", "Failed to load TopoJSON, falling back to GeoJSON"): "console-only diagnostic",
    ("pages/home.js", "Error updating requests chart:"): "console-only diagnostic prefix",
    ("pages/home.js", "Error updating IPs chart:"): "console-only diagnostic prefix",
    ("pages/home.js", "Error updating blocking chart:"): "console-only diagnostic prefix",
    ("pages/home.js", "Error updating map labels:"): "console-only diagnostic prefix",
    ("pages/instances.js", "AJAX request failed:"): "console-only diagnostic prefix",
    ("pages/instances.js", "Could not determine action for exec_form button."): "console-only diagnostic",
    ("pages/loading.js", "Invalid URL detected:"): "console-only diagnostic prefix",
    ("pages/loading.js", "Invalid or missing nextEndpoint. Redirect aborted."): "internal rejected Error, not rendered",
    ("pages/loading.js", "Request timed out."): "internal rejected Error, not rendered",
    ("pages/loading.js", "AJAX request failed:"): "console-only diagnostic prefix",
    ("pages/profile.js", "Fetch error:"): "console-only diagnostic prefix",
    ("pages/reports.js", "Date"): "unused headers metadata",
    ("pages/reports.js", "Request ID"): "unused headers metadata",
    ("pages/reports.js", "IP Address"): "unused headers metadata",
    ("pages/reports.js", "Country"): "unused headers metadata",
    ("pages/reports.js", "Method"): "unused headers metadata",
    ("pages/reports.js", "URL"): "unused headers metadata",
    ("pages/reports.js", "Status Code"): "unused headers metadata",
    ("pages/reports.js", "User-Agent"): "unused headers metadata",
    ("pages/reports.js", "Reason"): "unused headers metadata",
    ("pages/reports.js", "Server name"): "unused headers metadata",
    ("pages/reports.js", "Data"): "unused headers metadata",
    ("pages/reports.js", "Protocol"): "unused headers metadata",
    ("pages/reports.js", "Listen port"): "unused headers metadata",
    ("pages/reports.js", "Client port"): "unused headers metadata",
    ("pages/reports.js", "Bytes sent"): "unused headers metadata",
    ("pages/reports.js", "Bytes received"): "unused headers metadata",
    ("pages/reports.js", "Session time"): "unused headers metadata",
    ("pages/reports.js", "Actions"): "unused headers metadata",
    ("pages/reports.js", "Failed to load reports filters:"): "console-only diagnostic prefix",
    ("pages/reports.js", "Failed to stringify raw data, using string conversion:"): "console-only diagnostic prefix",
    ("pages/reports.js", "No raw data available in modal"): "console-only diagnostic",
    ("pages/reports.js", "Failed to copy to clipboard:"): "console-only diagnostic prefix",
    ("pages/reports.js", "Critical error in copy data functionality:"): "console-only diagnostic prefix",
    ("pages/reports.js", "Error formatting report data:"): "console-only diagnostic prefix",
    ("pages/reports.js", "Error copying raw data:"): "console-only diagnostic prefix",
    ("pages/reports.js", "bad behavior"): "normalized API reason token",
    ("pages/service-resources.js", "reverse proxy"): "internal resource-kind token used in comparison",
    ("pages/service-resources.js", "change input"): "DOM event names",
    ("pages/setup.js", "No confetti source URL"): "internal decorative-effect Error",
    ("pages/setup.js", "Failed to load confetti"): "internal decorative-effect Error",
    ("pages/setup.js", "Confetti effect unavailable:"): "console-only diagnostic prefix",
    ("pages/template-settings-page.js", "template-settings-page.js: js/components/settings-widgets.js must load first "): "console-only dependency diagnostic",
    ("pages/template-settings-page.js", "(window.BWSettingsWidgets is missing). Stepper disabled."): "console-only dependency diagnostic",
    ("pages/template-settings-page.js", "Invalid regex pattern:"): "console-only diagnostic prefix",
    ("pages/template-settings-page.js", "for input:"): "console-only diagnostic fragment",
    ("pages/template_edit.js", "input.form-check-input, select, textarea"): "form-control selector",
    ("pages/threatmap.js", "threatmap-ticker__reason badge bg-label-danger"): "CSS class list",
    ("pages/threatmap.js", "threatmap-ticker__target text-muted"): "CSS class list",
    ("pages/threatmap.js", "session expired"): "internal thrown sentinel",
    ("pages/threatmap.js", "HTTP "): "protocol label prefix",
    ("pages/workflow_editor.js", "Matches only when every condition inside is true."): "unused third array element",
    ("pages/workflow_editor.js", "Matches as soon as one condition inside is true."): "unused third array element",
    ("pages/workflow_editor.js", "Matches when none of the conditions inside are true."): "unused third array element",
    ("utils.js", "Failed to fetch news:"): "console-only diagnostic prefix",
    ("utils.js", "There was a problem with the clear notifications operation:"): "console-only diagnostic prefix",
}

# Genuine untranslated occurrences awaiting the UI owner's call-site migration. This list started
# at 123 entries and has reached zero. Each entry must still resolve to the exact literal at the
# stated line; once a call site enters `t()`, its stale entry fails until it is deleted.
#
# The final entry was `buttons.js` (vendored github-buttons v2.29.0, BSD-2-Clause, forked at
# c0d29cfb3), and it was the one entry marked *unmigratable* rather than merely unmigrated: its
# line 10 is `t = window.Math`, so a bare `t("...")` there calls Math and throws, while
# `window.t(...)` runs but hides behind a `.` the walker deliberately will not cross. No expression
# both ran and satisfied the scan.
#
# It was not migrated in the end — it was removed. The widget is now a server-rendered link in
# `about.html` reading `aria.label.github_stars`, with a star count from the hourly refresh in
# `main.py`. The dict stays so a future untranslated call site is recorded deliberately rather
# than slipping in silently.
PENDING = {}

TRANSLATION_KEY = re.compile(r"^[a-z][\w-]*(?:\.[\w-]+)+$")
WORD = re.compile(r"[A-Za-z][A-Za-z'-]*")


@dataclass(frozen=True)
class Literal:
    path: str
    line: int
    value: str


def _scripts():
    return sorted(path for path in JS.rglob("*.js") if "libs" not in path.parts)


def _resume_after_template(text, index, line, substitutions):
    """Read template text from `index`; report where code resumes and what precedes it.

    Both walkers below descend into `${...}` for the same reason `_jsscan` does: a
    `${t("button.export", "Export")}` is a call site, and the fallback beside the key is a translated
    default rather than untranslated copy. They keep their own loops on purpose — the assertion
    at the end of `_translation_ranges` is only worth something while this file finds `t()`
    independently of the shared walker.
    """
    index, line, opened = _template_text(text, index, line)
    if opened:
        substitutions.append(0)
    return index, line, "{" if opened else "`"


def _translation_ranges(text):
    """Return local translation-helper ranges and prove bare `t()` matches the shared walker."""
    ranges, bare_t = [], []
    substitutions = []
    index, size, line, previous = 0, len(text), 1, "\n"
    while index < size:
        char = text[index]
        if char == "\n":
            line += 1
            index += 1
            continue
        if char == "/" and text[index + 1 : index + 2] == "/":  # noqa: E203
            while index < size and text[index] != "\n":
                index += 1
            continue
        if char == "/" and text[index + 1 : index + 2] == "*":  # noqa: E203
            index += 2
            while index + 1 < size and not (text[index] == "*" and text[index + 1] == "/"):
                line += text[index] == "\n"
                index += 1
            index += 2
            continue
        if char == "`":
            index, line, previous = _resume_after_template(text, index + 1, line, substitutions)
            continue
        if char in "\"'":
            index, line = _skip_quoted(text, index, line)
            previous = char
            continue
        if char in "{}" and track_substitutions(substitutions, char):
            index, line, previous = _resume_after_template(text, index + 1, line, substitutions)
            continue
        if char == "/" and previous in _REGEX_MAY_START:
            index = _skip_regex(text, index)
            previous = "/"
            continue
        # `this.t(` is the same helper reached through an injection — `class News { constructor(t) }`
        # in `utils.js` stores the translator on the instance. The shared walker still refuses it,
        # on the correct ground that `obj.t(` in general is not this function; here the definition
        # is in the file and the fallback beside the key is a translated default, not loose copy.
        helper = next((name for name in (".translate", "translate", "this.t", "t") if text.startswith(f"{name}(", index)), None)
        # Same rule as `_jsscan._starts_an_identifier`, and it has to stay the same rule: the
        # assertion below pins this walker against that one.
        # A dotted helper is matched at its `.`, where the identifier rule would reject it — that is
        # the whole reason the shared walker could not see these calls in the first place.
        if helper and (helper.startswith(".") or _starts_an_identifier(text, index)):
            start = index + len(helper) + 1
            arguments = _balanced(text, start)
            ranges.append((index, start + len(arguments) + 1, line, arguments))
            if helper in ("t", ".translate"):
                bare_t.append((line, arguments))
        if not char.isspace():
            previous = char
        index += 1

    assert bare_t == Source(text).t_calls
    return ranges


def _quoted_literals(path, text):
    """Yield ordinary quoted strings; template literals follow `_jsscan.py` and are skipped."""
    relative = str(path.relative_to(JS))
    substitutions = []
    index, size, line, previous = 0, len(text), 1, "\n"
    while index < size:
        char = text[index]
        if char == "\n":
            line += 1
            index += 1
            continue
        if char == "/" and text[index + 1 : index + 2] == "/":  # noqa: E203
            while index < size and text[index] != "\n":
                index += 1
            continue
        if char == "/" and text[index + 1 : index + 2] == "*":  # noqa: E203
            index += 2
            while index + 1 < size and not (text[index] == "*" and text[index + 1] == "/"):
                line += text[index] == "\n"
                index += 1
            index += 2
            continue
        if char == "`":
            index, line, previous = _resume_after_template(text, index + 1, line, substitutions)
            continue
        if char in "\"'":
            start, start_line = index, line
            index, line = _skip_quoted(text, index, line)
            value = string_value(text[start:index])
            if value is not None:
                yield start, Literal(relative, start_line, value)
            previous = char
            continue
        if char in "{}" and track_substitutions(substitutions, char):
            index, line, previous = _resume_after_template(text, index + 1, line, substitutions)
            continue
        if char == "/" and previous in _REGEX_MAY_START:
            index = _skip_regex(text, index)
            previous = "/"
            continue
        if not char.isspace():
            previous = char
        index += 1


def _looks_like_copy(value):
    if not value or TRANSLATION_KEY.fullmatch(value):
        return False
    plain = re.sub(r"\{\{[^{}]+\}\}", " value ", value).strip()
    if plain.startswith((".", "#", "[", "<", "/", "http://", "https://")):
        return False
    if any(char in plain for char in "{}[]=;"):
        return False
    words = WORD.findall(plain.replace("\\n", " ").replace("\\t", " "))
    if len(words) == 1:
        return len(words[0]) >= 3 and plain == words[0] and plain[:1].isupper()
    if not words:
        return False
    if not any(char.isspace() for char in plain):
        return False
    tokens = plain.split()
    if any("-" in token for token in tokens) and all(re.fullmatch(r"[.#]?[a-z0-9-]+", token) for token in tokens):
        return False  # a CSS class list, not prose
    return True


def _classification():
    fallbacks, non_copy, pending, untranslated, candidates = [], [], [], [], []
    used_fallbacks, used_files, used_values, used_non_copy, used_pending = set(), set(), set(), set(), set()
    for path in _scripts():
        text = path.read_text(encoding="utf-8")
        ranges = _translation_ranges(text)
        for offset, literal in _quoted_literals(path, text):
            if not _looks_like_copy(literal.value):
                continue
            candidates.append(literal)
            if any(start <= offset < end for start, end, _, _ in ranges):
                fallbacks.append(literal)
                continue
            item = (literal.path, literal.value)
            pending_item = (literal.path, literal.line, literal.value)
            if pending_item in PENDING:
                used_pending.add(pending_item)
                pending.append(literal)
            elif item in CATALOG_FALLBACKS:
                used_fallbacks.add(item)
                fallbacks.append(literal)
            elif literal.path in NON_COPY_FILES:
                used_files.add(literal.path)
                non_copy.append(literal)
            elif literal.value in NON_COPY_VALUES:
                used_values.add(literal.value)
                non_copy.append(literal)
            elif item in NON_COPY:
                used_non_copy.add(item)
                non_copy.append(literal)
            else:
                untranslated.append(literal)
    used = used_fallbacks, used_files, used_values, used_non_copy, used_pending
    return candidates, fallbacks, non_copy, pending, untranslated, used


def test_user_visible_javascript_copy_enters_the_translation_catalog():
    _, _, _, _, untranslated, _ = _classification()

    assert not untranslated, "\n".join(f"{item.path}:{item.line}: {item.value!r}" for item in untranslated)


def test_the_pending_migration_list_only_shrinks():
    """A migrated call site makes its pending entry stale; delete the entry instead of tolerating it."""
    *_, used = _classification()
    used_pending = used[-1]

    assert len(PENDING) == 0, "the pending list reached zero and is a ratchet now; migrate the call site instead of re-adding an entry"
    assert used_pending == set(PENDING), f"stale pending entries: {sorted(set(PENDING) - used_pending)}"


def test_the_literal_scan_is_anti_vacuous_and_the_allowlist_is_explained():
    candidates, fallbacks, _, _, _, used = _classification()
    used_fallbacks, used_files, used_values, used_non_copy, _ = used

    assert len(_scripts()) > 60, "the first-party JavaScript tree is no longer being scanned"
    assert len(candidates) > 150, "too few natural-language literals found; the lexer likely stopped matching"
    assert len(fallbacks) > 100, "too few t() fallbacks found; translation calls are likely being misclassified"
    reasoned = CATALOG_FALLBACKS | NON_COPY_FILES | NON_COPY_VALUES | NON_COPY
    assert all(reason.strip() for reason in reasoned.values()), "every allowlist entry needs a reason"
    assert used_fallbacks == set(CATALOG_FALLBACKS), f"stale catalog fallbacks: {sorted(set(CATALOG_FALLBACKS) - used_fallbacks)}"
    assert used_files == set(NON_COPY_FILES), f"stale non-copy files: {sorted(set(NON_COPY_FILES) - used_files)}"
    assert used_values == set(NON_COPY_VALUES), f"stale non-copy values: {sorted(set(NON_COPY_VALUES) - used_values)}"
    assert used_non_copy == set(NON_COPY), f"stale non-copy literals: {sorted(set(NON_COPY) - used_non_copy)}"
