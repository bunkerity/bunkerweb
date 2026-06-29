/**
 * Custom ACE mode for the BunkerWeb "RAW" settings editor (service settings and
 * global config).
 *
 * The raw editor holds env-style `KEY=value` lines, but a few settings are
 * type:"file" and hold MULTILINE values (PEM certificates / keys, base64
 * blocks): CUSTOM_SSL_CERT_DATA, CUSTOM_SSL_KEY_DATA,
 * REVERSE_PROXY_SSL_TRUSTED_CERTIFICATE_DATA. This mode provides:
 *
 *   1. Neutral KEY=value highlighting (the editor used ace/mode/nginx before,
 *      which is not the right grammar for env-style settings).
 *   2. A FoldMode that collapses a multiline value under its `KEY=` header line
 *      into a "⋯ N lines" pill — the same idea as the logs viewer fold mode
 *      (ace-mode-bunkerweb_log.js), so a large cert no longer floods the editor.
 *
 * Whether a line starts a real setting and whether that setting is multiline
 * capable is decided by predicates that plugins-settings.js stashes on the
 * session (`session.$bwRawFold`) from the server-emitted #raw-known-keys list —
 * the SAME source of truth as the save-time parser (issue #3651). Without those
 * predicates the mode simply does not fold.
 *
 * Registered as "ace/mode/bunkerweb_settings". Loaded as a classic deferred
 * script AFTER ace.js and BEFORE the plugins-settings.js module so the mode is
 * in ACE's registry before session.setMode() runs.
 */
ace.define(
  "ace/mode/bunkerweb_settings_highlight_rules",
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

    var BunkerWebSettingsHighlightRules = function () {
      this.$rules = {
        start: [
          // Full-line comment.
          { token: "comment", regex: "^\\s*#.*$" },
          // KEY=value: setting keys are UPPERCASE [A-Z0-9_]. The value is left
          // un-tokenized past the first "=" so base64 "==" padding and "=" in
          // values are not mis-highlighted.
          {
            token: ["variable", "keyword.operator", "string"],
            regex: "^([A-Z][A-Z0-9_]*)(=)(.*)$",
          },
          // Continuation lines of a multiline value (PEM body, base64).
          { defaultToken: "string" },
        ],
      };
    };
    oop.inherits(BunkerWebSettingsHighlightRules, TextHighlightRules);

    exports.BunkerWebSettingsHighlightRules = BunkerWebSettingsHighlightRules;
  },
);

ace.define(
  "ace/mode/folding/bunkerweb_settings",
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
      // Predicates stashed on the session by plugins-settings.js. They depend on
      // the server-emitted #raw-known-keys, so the FoldMode never hard-codes the
      // schema.
      var folds = function (session) {
        return session.$bwRawFold || null;
      };

      // Foldable when this row is a multiline-capable KEY= line AND the next row
      // is a continuation (not itself a known KEY= line).
      this.getFoldWidget = function (session, foldStyle, row) {
        var p = folds(session);
        if (!p) return "";
        var line = session.getLine(row);
        if (!p.isMultilineKeyLine(line)) return "";
        var next = session.getLine(row + 1);
        if (next === undefined || p.isKnownKeyLine(next)) return "";
        return "start";
      };

      // Fold from the END of the header line to the end of the last continuation
      // line, so the `KEY=` header stays visible with a pill at its end.
      this.getFoldWidgetRange = function (session, foldStyle, row) {
        var p = folds(session);
        if (!p) return;
        var line = session.getLine(row);
        if (!p.isMultilineKeyLine(line)) return;
        var maxRow = session.getLength();
        var end = row;
        while (
          end + 1 < maxRow &&
          !p.isKnownKeyLine(session.getLine(end + 1))
        ) {
          end++;
        }
        if (end === row) return; // no continuation -> not foldable
        var count = end - row;
        var range = new Range(
          row,
          line.length,
          end,
          session.getLine(end).length,
        );
        range.placeholder =
          " ⋯ " + count + (count === 1 ? " line " : " lines ");
        return range;
      };
    }).call(FoldMode.prototype);
  },
);

ace.define(
  "ace/mode/bunkerweb_settings",
  [
    "require",
    "exports",
    "module",
    "ace/lib/oop",
    "ace/mode/text",
    "ace/mode/bunkerweb_settings_highlight_rules",
    "ace/mode/folding/bunkerweb_settings",
  ],
  function (require, exports, module) {
    "use strict";

    var oop = require("../lib/oop");
    var TextMode = require("./text").Mode;
    var BunkerWebSettingsHighlightRules =
      require("./bunkerweb_settings_highlight_rules").BunkerWebSettingsHighlightRules;
    var BunkerWebSettingsFoldMode =
      require("./folding/bunkerweb_settings").FoldMode;

    var Mode = function () {
      TextMode.call(this);
      this.HighlightRules = BunkerWebSettingsHighlightRules;
      this.foldingRules = new BunkerWebSettingsFoldMode();
      this.lineCommentStart = "#";
      this.$behaviour = this.$defaultBehaviour;
    };
    oop.inherits(Mode, TextMode);

    (function () {
      this.$id = "ace/mode/bunkerweb_settings";
    }).call(Mode.prototype);

    exports.Mode = Mode;
  },
);
