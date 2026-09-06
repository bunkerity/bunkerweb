/**
 * One user-readable sentence for a security report / ban reason.
 *
 * The Reports and Bans tables show the raw reason token ("crowdsec", "blacklist", …) and, for
 * the detail, a JSON blob. That is fine for an operator reading a ModSecurity rule id and
 * useless for everyone else: a CrowdSec row says "crowdsec" whether the request was blocked by
 * a LAPI decision, challenged by AppSec's bot detection, or sent a captcha, and the three call
 * for completely different reactions.
 *
 * This turns the `reason_data` a plugin records into a sentence a non-expert understands --
 * "CrowdSec AppSec: bot-detection challenge",
 * "CrowdSec LAPI: request blocked (scenario: crowdsecurity/http-probing)",
 * "Antibot challenge (captcha) served", "Security workflow api-shield: redirect" -- and returns
 * null for every reason it has nothing better to say about, so the caller keeps its current
 * rendering untouched.
 *
 * Three reasons are handled, and they are exactly the three the report filter admits on the
 * reason rather than on the status (`is_report()` in src/common/core/metrics/metrics.lua,
 * `_SELF_SERVED_REASONS` in src/common/db/db_methods/metrics.py): a plugin that answers the
 * request itself is the case where the raw token tells the reader nothing at all.
 *
 * The returned string is HTML-escaped and meant to be inserted as HTML: every value that comes
 * from the verdict (the scenario name is CrowdSec's, not ours) is escaped here, and the two
 * sentence templates are then interpolated with escaping OFF so nothing is escaped twice.
 */
(function (window) {
  "use strict";

  const ESCAPES = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  };

  function esc(value) {
    return String(value).replace(/[&<>"']/g, (c) => ESCAPES[c]);
  }

  // Own-property test, never a bare `TABLE[key]` truthiness check. `source` and `action` come out
  // of `reason_data`, a free-text column a caller fills through the ban API
  // (`src/bw/lua/bunkerweb/api.lua`), so "__proto__" and "constructor" reach here. Indexed
  // directly they resolve to an inherited member: `SOURCES["__proto__"]` is truthy and not
  // callable, which raises, and `SOURCES["constructor"]` prints "[object Object]" as a security
  // verdict. This makes those shapes render correctly; the try/catch at the bottom is what keeps
  // any *other* hostile shape from aborting the DataTables draw.
  function known(table, key) {
    return Object.prototype.hasOwnProperty.call(table, key);
  }

  // Local alias so every call below reads as a bare `t(key, fallback)` — which is what
  // tests/unit/ui/test_untranslated_js_literals.py's walker recognises as a translation call
  // site, and it deliberately will not cross the `.` in `window.t(`. i18n.js loads before this
  // file, but a `defer` script that threw inside a DataTables render callback would take the
  // whole table down, so the absence of the catalog is handled rather than assumed.
  function t(key, fallback, options) {
    if (typeof window.t !== "function") return fallback;
    return window.t(key, fallback, options);
  }

  // `t()` hands its fallback back un-interpolated when i18n.js never loaded, so a source string
  // with {{placeholders}} would reach the user as literal text. Filling them here keeps the
  // English in exactly one place: the alternative -- a second, concatenated copy for the
  // no-catalog path -- is a literal outside any t() call site, which
  // tests/unit/ui/test_untranslated_js_literals.py flags, and rightly, because the two copies
  // drift. A no-op on the normal path, where t() already substituted. The CrowdSec branch below
  // needs none of this: its fallback is composed from labels that are themselves t() results.
  function fill(text, values) {
    // Only on the no-catalog path. When window.t exists it has already substituted, and a second
    // pass would re-interpolate a *value* that happens to contain a placeholder -- a workflow
    // literally named "{{action}}" rendered as "Security workflow redirect: redirect".
    if (typeof window.t === "function") return text;
    return String(text).replace(
      /{{\s*([\w.]+)\s*}}/g,
      function (placeholder, name) {
        // known() and not a bare values[name], for the reason given on known() itself: a catalog
        // string carrying {{constructor}} would otherwise print "function Object() { … }".
        return known(values, name) ? values[name] : placeholder;
      },
    );
  }

  // The second argument of each call is the English source string: the catalog is the authority,
  // this is what shows while a key is untranslated. Wrapped in thunks so the literal sits at the
  // call site instead of in a lookup table read somewhere else.
  const SOURCES = {
    appsec: () => t("crowdsec.reason.source.appsec", "CrowdSec AppSec"),
    lapi: () => t("crowdsec.reason.source.lapi", "CrowdSec LAPI"),
  };
  const ACTIONS = {
    ban: () => t("crowdsec.reason.action.ban", "request blocked"),
    captcha: () => t("crowdsec.reason.action.captcha", "captcha challenge"),
    challenge: () =>
      t("crowdsec.reason.action.challenge", "bot-detection challenge"),
  };

  function crowdsec(verdict) {
    // `source` and `action` are what the bouncer always records on a remediation; without them
    // this is some other payload shape and guessing would be worse than saying nothing.
    const source = String(verdict.source || "").toLowerCase();
    const action = String(verdict.action || "").toLowerCase();
    if (!known(SOURCES, source) || !action) return null;

    const sourceLabel = esc(SOURCES[source]());
    // An action this build does not know about degrades to its own name rather than to nothing:
    // a future CrowdSec remediation should still read as a sentence. Its own name and not a
    // catalog lookup on `"crowdsec.reason.action." + action`: a key built by concatenation can
    // never be in `en.json` -- the catalog scanner refuses to resolve one, so nobody would ever
    // add it -- and the lookup could therefore only ever miss and fall back to this same string.
    const actionLabel = esc(
      known(ACTIONS, action) ? ACTIONS[action]() : String(verdict.action),
    );
    const scenario = verdict.scenario ? esc(String(verdict.scenario)) : "";

    // escapeValue off: every value interpolated below was escaped once above, and the two
    // templates are ours. Without this the scenario would come out as `&amp;lt;`.
    const options = {
      source: sourceLabel,
      action: actionLabel,
      scenario: scenario,
      interpolation: { escapeValue: false },
    };
    if (typeof window.t !== "function") {
      return scenario
        ? sourceLabel + ": " + actionLabel + " (scenario: " + scenario + ")"
        : sourceLabel + ": " + actionLabel;
    }
    return scenario
      ? t(
          "crowdsec.reason.sentence_scenario",
          "{{source}}: {{action}} (scenario: {{scenario}})",
          options,
        )
      : t("crowdsec.reason.sentence", "{{source}}: {{action}}", options);
  }

  // antibot records `{source, provider, action, http_status}` when it serves its challenge page
  // (`antibot:set_challenge_reason`). Gated on all three of source/action/provider rather than
  // rendering whatever is there: `reason_data` is a free-text column any caller of the ban API
  // can fill, and "Antibot challenge () served" is worse than the raw blob.
  function antibot(verdict) {
    if (String(verdict.source || "").toLowerCase() !== "antibot") return null;
    if (String(verdict.action || "").toLowerCase() !== "challenge") return null;
    const provider = verdict.provider ? esc(String(verdict.provider)) : "";
    if (!provider) return null;
    // escapeValue off: `provider` was escaped once above and the template is ours.
    const values = {
      provider: provider,
      interpolation: { escapeValue: false },
    };
    return fill(
      t(
        "antibot.reason.sentence",
        "Antibot challenge ({{provider}}) served",
        values,
      ),
      values,
    );
  }

  // workflows records `{workflow, rule, action}` on its detect and redirect branches
  // (`workflows:apply`). The action type is interpolated raw, the way the CrowdSec scenario is:
  // it is config vocabulary out of the rule the operator wrote ("challenge", "block",
  // "redirect"), and a key built by concatenation could never be in en.json anyway.
  function workflows(verdict) {
    // A CrowdSec verdict the engine enforced because no rule overrode it
    // (`CROWDSEC_DEFER_TO_WORKFLOWS`, `workflows:enforce_deferred`). The row's reason is
    // `workflows` -- the dispatcher keys it on the plugin that returned the status
    // (access-lua.conf:164) and a plugin cannot override that -- but the fact is CrowdSec's and
    // the payload is the bouncer's own verdict, so it renders with the CrowdSec sentence instead
    // of a workflow name it does not have. Any other payload shape falls through `crowdsec()`'s
    // own source/action gate and still returns null, exactly as before.
    if (!verdict.workflow) return crowdsec(verdict);
    const name = verdict.workflow ? esc(String(verdict.workflow)) : "";
    const action = verdict.action ? esc(String(verdict.action)) : "";
    if (!name || !action) return null;
    const values = {
      workflow: name,
      action: action,
      interpolation: { escapeValue: false },
    };
    return fill(
      t(
        "workflows.reason.sentence",
        "Security workflow {{workflow}}: {{action}}",
        values,
      ),
      values,
    );
  }

  const FORMATTERS = {
    antibot: antibot,
    crowdsec: crowdsec,
    workflows: workflows,
  };

  /**
   * @param {string} reason the report/ban reason token, e.g. "crowdsec"
   * @param {object|string} data the reason_data payload (an object, or its JSON text)
   * @returns {string|null} an HTML-safe sentence, or null when there is nothing better to show
   */
  function format(reason, data) {
    // Lowercased, like both halves of the report filter: the reason is stored in a plain string
    // column and read back by whatever collation the engine has.
    const key = String(reason || "").toLowerCase();
    if (!known(FORMATTERS, key)) return null;

    let verdict = data;
    if (typeof verdict === "string") {
      try {
        verdict = JSON.parse(verdict);
      } catch (e) {
        return null;
      }
    }
    if (!verdict || typeof verdict !== "object") return null;
    return FORMATTERS[key](verdict);
  }

  // Nothing this returns is worth a broken page. `verdict` is a decoded free-text column
  // (`reason_data`, filled by any caller of the ban API), so its fields can be any JSON value --
  // and `String({ toString: "not a function" })` throws `TypeError: Cannot convert object to
  // primitive value` before the own-property guards above ever run. This is called from a
  // DataTables `render` callback on both pages; a throw there aborts the whole table draw. The
  // guards make the common shapes render correctly, this makes every other shape harmless.
  function formatSecurityReason(reason, data) {
    try {
      return format(reason, data);
    } catch (e) {
      return null;
    }
  }

  window.formatSecurityReason = formatSecurityReason;
})(window);
