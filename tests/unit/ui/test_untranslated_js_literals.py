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
    _IDENTIFIER_TAIL,
    _REGEX_MAY_START,
    _balanced,
    _skip_quoted,
    _skip_regex,
    string_value,
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
    ("modules/setting_controls.js", "Show selected only"): "tooltip.button.show_selected_only via injected translator",
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
    ("pages/reports-overview.js", "just now"): "flash.time.just_now fallback",
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
    (
        "pages/service-resources.js",
        "{{service}} already serves {{path}} through its own {{family}} settings. Clear those settings for {{path}}, or use a different path.",
    ): "service.resources.conflict.inline defaultValue",
    (
        "pages/service-resources.js",
        "{{service}} already serves {{path}} through the {{kind}} “{{name}}”. Detach “{{name}}”, or give one of them a different path.",
    ): "service.resources.conflict.resource defaultValue",
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
    ("pages/workflow_editor.js", "This workflow"): "workflows.errors.whole fallback",
    ("pages/workflow_editor.js", " problem blocks the save."): "workflows.errors.count fallback fragment",
    ("pages/workflow_editor.js", " problems block the save."): "workflows.errors.count fallback fragment",
    ("pages/workflow_editor.js", "Whitelisted — the whole workflow is skipped and no rule is evaluated."): "workflows.test.out_whitelisted fallback",
    ("pages/workflow_editor.js", "This workflow is attached to no service, so there is no ladder to evaluate."): "workflows.test.out_not_attached fallback",
    ("pages/workflow_editor.js", "This service is a draft — no workflow is compiled for it yet."): "workflows.test.out_draft fallback",
    ("pages/workflow_editor.js", "No rule matched. The request continues to the rest of the security stack."): "workflows.test.out_no_match fallback",
    ("pages/workflow_editor.js", "{{workflow}} · {{rule}} matched and {{action}} the request."): "workflows.test.out_match fallback",
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
    ("menu.js", "Cannot find `.menu-sub` element for the current `.menu-toggle`"): "developer exception for invalid menu markup",
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

# Genuine untranslated occurrences awaiting the UI owner's call-site migration. This list starts
# at 123 entries and is meant to reach zero. Each entry must still resolve to the exact literal at
# the stated line; once a call site enters `t()`, its stale entry fails until it is deleted.
PENDING = {
    ("buttons.js", 420, " on GitHub"): "aria.label.github_{followers,stars,watchers,forks,open_issues}",
    ("components/secret-field.js", 45, "Secret value"): "aria.label.secret_value + aria.label.value_hidden",
    ("components/settings-widgets.js", 235, "No file selected"): "status.no_file_selected",
    ("components/settings-widgets.js", 304, "Switch to text editor"): "tooltip.button.switch_to_text_editor",
    ("components/settings-widgets.js", 305, "Back to file upload"): "tooltip.button.back_to_file_upload",
    ("components/settings-widgets.js", 898, "Unable to read the selected file."): "template.editor.raw_editor_upload_failed",
    ("components/webauthn.js", 62, "Request failed"): "error.webauthn_request_failed",
    ("main.js", 293, "Invalid date"): "validation.invalid_date",
    ("modules/setting_controls.js", 646, "No file selected"): "status.no_file_selected",
    ("modules/setting_controls.js", 653, "No file selected"): "status.no_file_selected",
    ("pages/config_edit.js", 166, "Global"): "scope.global",
    ("pages/config_edit.js", 193, "Warning"): "flash.warning",
    ("pages/config_edit.js", 248, "You can now select global types for your custom config."): "tooltip.config_global_types_available",
    ("pages/config_edit.js", 289, "Draft"): "status.draft",
    ("pages/config_edit.js", 292, "Online"): "status.online",
    ("pages/config_edit.js", 308, "This action is not allowed in read-only mode."): "alert.readonly_mode",
    ("pages/config_edit.js", 321, "No changes detected."): "alert.no_changes_detected",
    ("pages/config_edit.js", 332, "A custom configuration name is required."): "validation.required",
    ("pages/config_edit.js", 341, "Please enter a valid configuration name."): "validation.pattern",
    ("pages/configs.js", 490, "Conversion failed"): "toast.header.conversion_failed",
    ("pages/configs.js", 493, "The selected configs are already in the desired state."): "toast.body.selected_items_already_in_state",
    ("pages/home.js", 720, "304 Not Modified"): "dashboard.chart.request_status.http_304",
    ("pages/home.js", 723, "404 Not Found"): "dashboard.chart.request_status.http_404",
    ("pages/home.js", 724, "429 Rate Limited"): "dashboard.chart.request_status.http_429",
    ("pages/home.js", 892, "Status"): "table.header.status",
    ("pages/home.js", 1091, "Unknown"): "status.unknown",
    ("pages/login.js", 56, "Couldn't sign you in with a passkey, please try again"): "error.passkey_sign_in_failed",
    ("pages/plugins-grid.js", 183, "File size exceeds 50 MB limit."): "alert.plugin_file_too_large",
    ("pages/plugins-grid.js", 238, "An error occurred while uploading the file. Please try again."): "alert.plugin_upload_failed",
    ("pages/plugins-grid.js", 267, "Please upload a valid plugin file (.zip, .tar.gz, .tar.xz)."): "alert.plugin_file_invalid",
    ("pages/plugins.js", 93, "File size exceeds 50 MB limit."): "alert.plugin_file_too_large",
    ("pages/plugins.js", 152, "An error occurred while uploading the file. Please try again."): "alert.plugin_upload_failed",
    ("pages/plugins.js", 576, "Please upload a valid plugin file (.zip, .tar.gz, .tar.xz)."): "alert.plugin_file_invalid",
    ("pages/profile-passkeys.js", 33, "Enter your current password to add a passkey."): "validation.current_password_required_for_passkey",
    ("pages/profile-passkeys.js", 61, "Couldn't register this passkey, please try again"): "error.passkey_registration_failed",
    ("pages/profile.js", 210, "Browser"): "profile.session.browser",
    ("pages/profile.js", 212, "Operating System"): "profile.session.os",
    ("pages/profile.js", 214, "Device"): "profile.session.device",
    ("pages/profile.js", 216, "IP Address"): "profile.session.ip_address",
    ("pages/profile.js", 218, "Creation date"): "profile.session.creation_date",
    ("pages/profile.js", 220, "Last Activity"): "profile.session.last_activity",
    ("pages/profile.js", 357, "Browser"): "profile.session.browser",
    ("pages/profile.js", 358, "Operating System"): "profile.session.os",
    ("pages/profile.js", 359, "Device"): "profile.session.device",
    ("pages/profile.js", 369, "Creation date"): "profile.session.creation_date",
    ("pages/profile.js", 375, "Last Activity"): "profile.session.last_activity",
    ("pages/reports.js", 971, "No data available"): "status.no_data",
    ("pages/reports.js", 990, "Failed to copy to clipboard. Please try using the raw data copy button below."): "error.report_copy_failed",
    ("pages/reports.js", 996, "Error accessing data for copying. Please try refreshing the page."): "error.report_copy_access_failed",
    ("pages/reports.js", 1006, "No URL available"): "status.no_url_available",
    ("pages/reports.js", 1019, "Unknown"): "status.unknown",
    ("pages/reports.js", 1042, "Missing report identifier"): "error.report_identifier_missing",
    ("pages/reports.js", 1135, "Failed to load report details from server"): "error.report_details_load_failed",
    ("pages/reports.js", 1152, "Failed to load report details."): "error.report_details_load_failed",
    ("pages/reports.js", 1255, "No data available"): "status.no_data",
    ("pages/service-resources.js", 261, "Nothing available to attach"): "service.resources.nothing_available",
    ("pages/services.js", 518, "Conversion failed"): "toast.header.conversion_failed",
    ("pages/services.js", 521, "The selected services are already in the desired state."): "toast.body.selected_items_already_in_state",
    ("pages/services.js", 881, "Please upload a valid services export file (.env or .zip)."): "alert.services_import_invalid_file",
    ("pages/setup.js", 153, "Server name check failed"): "validation.server_name_check_failed",
    ("pages/setup.js", 172, "Invalid server name."): "validation.server_name_invalid",
    ("pages/setup.js", 194, "Server name is not unique."): "validation.server_name_not_unique",
    ("pages/setup.js", 197, "Server name is not unique."): "validation.server_name_not_unique",
    ("pages/setup.js", 200, "Please choose a different server name."): "validation.server_name_choose_different",
    ("pages/setup.js", 213, "Server name is unique."): "validation.server_name_unique",
    ("pages/setup.js", 216, "You can proceed with the setup."): "validation.server_name_proceed",
    ("pages/setup.js", 311, "This field"): "validation.default_field_name",
    ("pages/setup.js", 467, "Passwords do not match."): "form.validation.confirm_password_match",
    ("pages/setup.js", 483, "This field is required if you want to subscribe to the newsletter."): "validation.newsletter_email_required",
    ("pages/setup.js", 510, "This field is required when using DNS challenge."): "validation.dns_challenge_field_required",
    (
        "pages/setup.js",
        541,
        "When using custom SSL, you must set both the certificate and the key (via file path or data upload).",
    ): "validation.custom_ssl_pair_required",
    ("pages/setup.js", 562, "Error"): "flash.error",
    ("pages/setup.js", 568, "Server name is not unique"): "modal.title.server_name_not_unique",
    ("pages/setup.js", 641, "Newsletter Subscription"): "newsletter.title",
    ("pages/setup.js", 645, "Please enter a valid email address to subscribe to the newsletter."): "validation.newsletter_email_invalid",
    ("pages/setup.js", 812, "Error"): "flash.error",
    ("pages/setup.js", 815, "Error while setting up web UI. Please try again."): "setup.error.web_ui_setup_failed",
    ("pages/setup.js", 923, "Wildcard certificates are only supported with DNS challenges."): "tooltip.wildcard_dns_only",
    ("pages/setup.js", 930, "DNS provider is only supported with DNS challenges."): "tooltip.dns_provider_dns_only",
    ("pages/setup.js", 937, "DNS propagation is only supported with DNS challenges."): "tooltip.dns_propagation_dns_only",
    ("pages/setup.js", 944, "Credentials are only supported with DNS challenges."): "tooltip.dns_credentials_dns_only",
    ("pages/setup.js", 1038, "Loaded from "): "setup.file.loaded_from",
    ("pages/setup.js", 1047, "Error reading file"): "setup.file.read_error",
    ("pages/setup.js", 1095, "Content entered ("): "setup.file.content_entered",
    ("pages/setup.js", 1096, "No file selected"): "status.no_file_selected",
    ("pages/template-settings-page.js", 398, "Unable to read the selected file."): "template.editor.raw_editor_upload_failed",
    ("pages/template-settings-page.js", 962, "Success"): "status.success",
    ("pages/template-settings-page.js", 965, "Global settings applied"): "toast.global_settings_applied_title",
    (
        "pages/template-settings-page.js",
        970,
        "Global settings have been successfully fetched and applied to the current form.",
    ): "toast.global_settings_applied_body",
    ("pages/template-settings-page.js", 984, "Error"): "flash.error",
    ("pages/template-settings-page.js", 987, "Failed to fetch global settings"): "toast.global_settings_failed_title",
    ("pages/template-settings-page.js", 991, "An error occurred while fetching global settings."): "toast.global_settings_failed_body",
    ("pages/template_edit.js", 447, "Uploaded"): "template.editor.missing_config_status_uploaded",
    ("pages/template_edit.js", 450, "Missing"): "template.editor.missing_config_status_missing",
    ("pages/threatmap.js", 409, "not localised"): "threatmap.not_localised",
    ("pages/threatmap.js", 468, " more not shown"): "threatmap.more_hidden",
    ("pages/threatmap.js", 479, "No data"): "status.no_data",
    ("pages/threatmap.js", 808, " blocked request"): "threatmap.blocked_request",
    ("pages/threatmap.js", 808, " blocked requests"): "threatmap.blocked_requests",
    ("pages/totp.js", 49, "Couldn't verify your security key, please try again"): "error.security_key_verification_failed",
    ("pages/totp.js", 114, "Use an authenticator code"): "link.use_authenticator_code",
    ("pages/totp.js", 118, "Use a recovery code"): "link.use_recovery_code",
    ("pages/workflow_editor.js", 35, "IP / CIDR"): "workflows.condition.ip",
    ("pages/workflow_editor.js", 39, "Country"): "workflows.test.country",
    ("pages/workflow_editor.js", 40, "ASN"): "workflows.test.asn",
    ("pages/workflow_editor.js", 41, "HTTP method"): "workflows.condition.method",
    ("pages/workflow_editor.js", 42, "URI"): "workflows.condition.uri",
    ("pages/workflow_editor.js", 50, "Prove it is human"): "workflows.action_help.challenge",
    ("pages/workflow_editor.js", 51, "Deny the request"): "workflows.action_help.block",
    ("pages/workflow_editor.js", 52, "Send it elsewhere"): "workflows.action_help.redirect",
    ("pages/workflow_editor.js", 77, "is exactly"): "workflows.uri_match.exact",
    ("pages/workflow_editor.js", 78, "starts with"): "workflows.uri_match.prefix",
    ("pages/workflow_editor.js", 79, "matches the regex"): "workflows.uri_match.regex",
    ("pages/workflow_editor.js", 96, "All of"): "workflows.tree.all",
    ("pages/workflow_editor.js", 96, "Any of"): "workflows.tree.any",
    ("pages/workflow_editor.js", 96, "None of"): "workflows.tree.not",
    ("pages/workflow_editor.js", 1165, "Not validated yet"): "workflows.not_validated",
    ("pages/workflow_editor.js", 1279, ' — click to move"'): "workflows.aria.positionMove",
    ("pages/workflow_editor.js", 1284, ', change position">'): "workflows.aria.changePosition",
    ("pages/workflow_editor.js", 1393, ', change position">'): "workflows.aria.changePosition",
    ("pages/workflow_editor.js", 2238, "Stays at"): "workflows.menu.staysAt",
    ("pages/workflow_editor.js", 2238, "Move to"): "workflows.menu.moveTo",
    ("pages/workflow_editor.js", 2349, "New value"): "workflows.aria.newValue",
}

TRANSLATION_KEY = re.compile(r"^[a-z][\w-]*(?:\.[\w-]+)+$")
WORD = re.compile(r"[A-Za-z][A-Za-z'-]*")


@dataclass(frozen=True)
class Literal:
    path: str
    line: int
    value: str


def _scripts():
    return sorted(path for path in JS.rglob("*.js") if "libs" not in path.parts)


def _translation_ranges(text):
    """Return local translation-helper ranges and prove bare `t()` matches the shared walker."""
    ranges, bare_t = [], []
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
        if char in "\"'`":
            index, line = _skip_quoted(text, index, line)
            previous = char
            continue
        if char == "/" and previous in _REGEX_MAY_START:
            index = _skip_regex(text, index)
            previous = "/"
            continue
        helper = next((name for name in ("translate", "t") if text.startswith(f"{name}(", index)), None)
        if helper and not (previous.isalnum() or previous in _IDENTIFIER_TAIL):
            start = index + len(helper) + 1
            arguments = _balanced(text, start)
            ranges.append((index, start + len(arguments) + 1, line, arguments))
            if helper == "t":
                bare_t.append((line, arguments))
        if not char.isspace():
            previous = char
        index += 1

    assert bare_t == Source(text).t_calls
    return ranges


def _quoted_literals(path, text):
    """Yield ordinary quoted strings; template literals follow `_jsscan.py` and are skipped."""
    relative = str(path.relative_to(JS))
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
        if char in "\"'`":
            start, start_line = index, line
            index, line = _skip_quoted(text, index, line)
            if char != "`":
                value = string_value(text[start:index])
                if value is not None:
                    yield start, Literal(relative, start_line, value)
            previous = char
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

    assert len(PENDING) == 123, "the measured pending count changed; update the docstring and this assertion"
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
