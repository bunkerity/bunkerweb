/**
 * Custom ACE syntax-highlighting mode for the BunkerWeb logs viewer.
 *
 * Tokenizes the log shapes the /logs page surfaces, with a plain-text fallback
 * for anything unrecognized:
 *   1. BunkerWeb app log, bracketed ts : [ts] [name] [pid] [LEVEL] - message
 *   2. BunkerWeb app log, plain ts      : ts [name] [pid] [LEVEL] - message
 *   3. certbot / Let's Encrypt          : ts,millis:LEVEL:dotted.logger:message
 *   4. NGINX error log                  : YYYY/MM/DD HH:MM:SS [level] pid#tid: message
 *   5. NGINX access log                 : host ip - reqid user [ts] "REQ" status bytes "ref" "ua"
 *
 * LEVEL appears either as a word (ERROR/WARNING/INFO/DEBUG/...) OR as the emoji
 * the BunkerWeb logger emits (🚨 CRITICAL, ❌ ERROR, ⚠️ WARNING, ℹ️ INFO,
 * 🐛 DEBUG) — both are matched. Emoji carry an optional U+FE0F variation
 * selector and trailing padding, so the matcher tolerates surrounding space.
 *
 * Coloring is pure tokenizer output (content-addressed), so it survives the
 * live-follow append + 5000-line trim with zero JS bookkeeping. ERROR / WARNING
 * lines collapse their non-level fields to a single `log.line.error|warning`
 * scope (log.row.* — NOT log.line.*, which would collide with ACE's reserved
 * ace_line renderer class) so the WHOLE line tints (see static/css/pages/logs.css), while the LEVEL
 * keyword keeps its own bold scope as the primary, colorblind-safe text cue.
 *
 * Registered as "ace/mode/bunkerweb_log" and selected from logs.js. Loaded as a
 * classic deferred script AFTER ace.js and BEFORE the logs.js module, so the
 * mode is in ACE's registry before session.setMode() runs.
 *
 * Regexes are anchored at ^ and use bounded character classes (never nested
 * quantifiers, never `.*` inside quoted fields) — access-log fields (URL, UA,
 * referer) are attacker-influenced, so this avoids catastrophic backtracking.
 */
ace.define(
  "ace/mode/bunkerweb_log_highlight_rules",
  [
    "require",
    "exports",
    "module",
    "ace/lib/oop",
    "ace/mode/text_highlight_rules",
  ],
  function (require, exports, module) {
    "use strict";

    var oop = require("../lib/oop");
    var TextHighlightRules =
      require("./text_highlight_rules").TextHighlightRules;

    var BunkerWebLogHighlightRules = function () {
      var dup = function (s, n) {
        var a = [];
        for (var i = 0; i < n; i++) a.push(s);
        return a;
      };

      // Level matchers: word forms + the emoji the BunkerWeb logger emits.
      // (literal emoji chars; ️ = optional variation selector)
      var LV = {
        error: "(?:ERROR|CRITICAL|❌|🚨)",
        warning: "(?:WARNING|⚠\\uFE0F?)",
        info: "(?:INFO|NOTICE|ℹ\\uFE0F?)",
        debug: "(?:DEBUG|🐛)",
      };
      var isSevere = function (cls) {
        return cls === "error" || cls === "warning";
      };

      // ---- BunkerWeb app log: <ts> [name] [pid] [LEVEL] - message ----
      // tsRe captures the timestamp (bracketed or plain comma form).
      var appRule = function (tsRe, cls) {
        var lvl = "(\\[\\s*" + LV[cls] + "\\s*\\])";
        var regex =
          "^" +
          tsRe +
          "( )(\\[[^\\]]*\\])( )(\\[\\d+\\])( )" +
          lvl +
          "( - )(.*)$";
        if (isSevere(cls)) {
          return {
            regex: regex,
            token: dup("log.row." + cls, 6)
              .concat(["log.level." + cls])
              .concat(dup("log.row." + cls, 2)),
          };
        }
        return {
          regex: regex,
          token: [
            "log.timestamp",
            "text",
            "log.logger",
            "text",
            "log.pid",
            "text",
            "log.level." + cls,
            "text",
            "log.message",
          ],
        };
      };
      var TS_BRACKET = "(\\[[^\\]]*\\])"; // [2026-05-19 11:38:11 +0000]
      var TS_PLAIN = "([\\d-]+ [\\d:,]+)"; // 2026-05-19 11:38:11,337
      var appRules = [];
      ["error", "warning", "info", "debug"].forEach(function (cls) {
        appRules.push(appRule(TS_BRACKET, cls));
        appRules.push(appRule(TS_PLAIN, cls));
      });

      // ---- certbot / Let's Encrypt: ts,millis:LEVEL:logger:message ----
      var CB_PREFIX = "^([\\d-]+ [\\d:,]+)(:)";
      var CB_SUFFIX = "(:)([^:]+)(:)(.*)$";
      var cbRule = function (levelRe, cls) {
        var regex = CB_PREFIX + "(" + levelRe + ")" + CB_SUFFIX;
        if (isSevere(cls)) {
          return {
            regex: regex,
            token: dup("log.row." + cls, 2)
              .concat(["log.level." + cls])
              .concat(dup("log.row." + cls, 4)),
          };
        }
        return {
          regex: regex,
          token: [
            "log.timestamp",
            "text",
            "log.level." + cls,
            "text",
            "log.logger",
            "text",
            "log.message",
          ],
        };
      };
      var cbRules = [
        cbRule("ERROR|CRITICAL", "error"),
        cbRule("WARNING", "warning"),
        cbRule("INFO|NOTICE", "info"),
        cbRule("DEBUG", "debug"),
      ];

      // ---- NGINX error log: date time [level] pid#tid: message ----
      var NGX_DATE = "(\\d{4}/\\d\\d/\\d\\d \\d\\d:\\d\\d:\\d\\d)";
      var ngxRule = function (levelRe, cls) {
        var regex =
          "^" +
          NGX_DATE +
          "( )(\\[(?:" +
          levelRe +
          ")\\])( )(\\d+#\\d+:)( )(.*)$";
        if (isSevere(cls)) {
          return {
            regex: regex,
            token: dup("log.row." + cls, 2)
              .concat(["log.level." + cls])
              .concat(dup("log.row." + cls, 4)),
          };
        }
        return {
          regex: regex,
          token: [
            "log.timestamp",
            "text",
            "log.level." + cls,
            "text",
            "log.pid",
            "text",
            "log.message",
          ],
        };
      };
      var ngxRules = [
        ngxRule("error|crit|alert|emerg", "error"),
        ngxRule("warn", "warning"),
        ngxRule("notice|info", "info"),
        ngxRule("debug", "debug"),
      ];

      // ---- NGINX access log -------------------------------------------
      // host ip - reqid user [ts] "METHOD url" status bytes "ref" "ua"
      // One rule per status class (only the status group varies).
      var ACCESS_TOKENS = function (statusScope) {
        return [
          "log.host",
          "text",
          "log.ip",
          "text",
          "log.reqid",
          "text",
          "log.user",
          "text",
          "log.timestamp",
          "text",
          "log.quoted",
          "log.http.method",
          "text",
          "log.url",
          "log.quoted",
          "text",
          statusScope,
          "text",
          "log.number",
          "text",
          "log.quoted",
          "text",
          "log.quoted",
        ];
      };
      var ACCESS_REGEX = function (statusDigits) {
        return (
          "^(\\S+)( )(\\S+)( - )(\\S+)( )(\\S+)( )(\\[[^\\]]*\\])( )" +
          '(")([A-Z]+)( )([^"]*)(")( )' +
          "(" +
          statusDigits +
          ")( )(\\d+|-)( )" +
          '("[^"]*")( )("[^"]*")$'
        );
      };
      var accessRules = [
        {
          regex: ACCESS_REGEX("2\\d{2}"),
          token: ACCESS_TOKENS("log.status.2xx"),
        },
        {
          regex: ACCESS_REGEX("3\\d{2}"),
          token: ACCESS_TOKENS("log.status.3xx"),
        },
        {
          regex: ACCESS_REGEX("4\\d{2}"),
          token: ACCESS_TOKENS("log.status.4xx"),
        },
        {
          regex: ACCESS_REGEX("5\\d{2}"),
          token: ACCESS_TOKENS("log.status.5xx"),
        },
        { regex: ACCESS_REGEX("\\d{3}"), token: ACCESS_TOKENS("log.status") },
      ];

      // Specific rules first. The two catch-alls tile any unstructured line:
      // a run of non-printable / control bytes (binary content) flagged as
      // log.control, then a run of printable text as neutral log.message. Both
      // are single-token char-class runs — no capturing groups (ACE requires
      // (?:) when token is a string), linear, ReDoS-free even on a huge binary
      // blob on one line. Excludes \t \n \r (whitespace / line terminators).
      var CONTROL = "[\\x00-\\x08\\x0b\\x0c\\x0e-\\x1f\\x7f]+";
      this.$rules = {
        start: appRules
          .concat(cbRules)
          .concat(ngxRules)
          .concat(accessRules)
          .concat([
            { token: "log.control", regex: CONTROL },
            {
              token: "log.message",
              regex: "[^\\x00-\\x08\\x0b\\x0c\\x0e-\\x1f\\x7f]+",
            },
          ]),
      };

      this.normalizeRules();
    };

    oop.inherits(BunkerWebLogHighlightRules, TextHighlightRules);
    exports.BunkerWebLogHighlightRules = BunkerWebLogHighlightRules;
  },
);

// Shared: does a line START a structured log entry? (the 5 formats the
// tokenizer recognizes). Anything else is a continuation line — a traceback,
// JSON, config dump, or blank/indented line — and folds under its header.
// KEEP IN SYNC with BunkerWebLogHighlightRules below: this is a second copy of
// the header shapes (start states), used by the FoldMode to find fold groups.
var BWLOG_START_RE =
  /^(?:\[[^\]]*\] \[[^\]]*\] \[\d+\] \[|[\d-]+ [\d:,]+ \[[^\]]*\] \[\d+\] \[|[\d-]+ [\d:,]+:(?:DEBUG|INFO|NOTICE|WARNING|ERROR|CRITICAL):|\d{4}\/\d\d\/\d\d \d\d:\d\d:\d\d \[|\S+ \S+ - \S+ \S+ \[[^\]]*\] ")/u;
function bwlogIsLogStart(line) {
  return typeof line === "string" && BWLOG_START_RE.test(line);
}

ace.define(
  "ace/mode/bunkerweb_log",
  [
    "require",
    "exports",
    "module",
    "ace/lib/oop",
    "ace/mode/text",
    "ace/mode/bunkerweb_log_highlight_rules",
    "ace/mode/folding/bunkerweb_log",
  ],
  function (require, exports, module) {
    "use strict";

    var oop = require("../lib/oop");
    var TextMode = require("./text").Mode;
    var BunkerWebLogHighlightRules =
      require("./bunkerweb_log_highlight_rules").BunkerWebLogHighlightRules;
    var BunkerWebLogFoldMode = require("./folding/bunkerweb_log").FoldMode;

    var Mode = function () {
      TextMode.call(this);
      this.HighlightRules = BunkerWebLogHighlightRules;
      this.foldingRules = new BunkerWebLogFoldMode();
      this.$behaviour = this.$defaultBehaviour;
    };
    oop.inherits(Mode, TextMode);

    (function () {
      this.$id = "ace/mode/bunkerweb_log";
    }).call(Mode.prototype);

    exports.Mode = Mode;
  },
);

ace.define(
  "ace/mode/folding/bunkerweb_log",
  [
    "require",
    "exports",
    "module",
    "ace/lib/oop",
    "ace/mode/folding/fold_mode",
    "ace/range",
  ],
  function (require, exports, module) {
    "use strict";
    var oop = require("../../lib/oop");
    var BaseFoldMode = require("./fold_mode").FoldMode;
    var Range = require("../../range").Range;

    var FoldMode = (exports.FoldMode = function () {});
    oop.inherits(FoldMode, BaseFoldMode);

    (function () {
      // Foldable when this row starts a log entry AND the next row is a
      // continuation (does not itself start a log entry).
      this.getFoldWidget = function (session, foldStyle, row) {
        var line = session.getLine(row);
        if (!bwlogIsLogStart(line)) return "";
        var next = session.getLine(row + 1);
        if (next === undefined || bwlogIsLogStart(next)) return "";
        return "start";
      };

      // Fold from the END of the header line to the end of the last
      // continuation line, so the header stays visible with a pill at its end.
      this.getFoldWidgetRange = function (session, foldStyle, row) {
        var line = session.getLine(row);
        if (!bwlogIsLogStart(line)) return;
        var maxRow = session.getLength();
        var end = row;
        while (end + 1 < maxRow && !bwlogIsLogStart(session.getLine(end + 1))) {
          end++;
        }
        if (end === row) return; // no continuation -> not foldable
        var count = end - row;
        var firstCont = session.getLine(row + 1) || "";
        var isTrace =
          /^\s*(?:Traceback \(most recent call last\)|File ")/.test(
            firstCont,
          ) || /Traceback \(most recent call last\)/.test(firstCont);
        var range = new Range(
          row,
          line.length,
          end,
          session.getLine(end).length,
        );
        range.placeholder = isTrace
          ? " Traceback (" + count + " lines) "
          : " ⋯ " + count + " lines ";
        return range;
      };
    }).call(FoldMode.prototype);
  },
);

// Force the factory to evaluate now so the mode is fully registered and any
// error surfaces immediately rather than on first setMode().
(function () {
  ace.require(["ace/mode/bunkerweb_log"], function (m) {
    if (typeof module == "object" && typeof exports == "object" && module) {
      module.exports = m;
    }
  });
})();
