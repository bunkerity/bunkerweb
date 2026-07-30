// The raw settings editor for /services/<svc> and /global-settings, plus the page chrome that
// used to live in the dying advanced pane.
//
// This is `js/plugins-settings.js` (4149 lines) with the easy and advanced panes removed. Of
// what is gone, ~1,570 lines were already duplicated -- the widget bucket in
// `js/components/settings-widgets.js` (which carries three fixes this copy never had, the
// jQuery-4 `data-default` coercion among them) and the stepper in
// `js/pages/template-settings-page.js` -- and the rest was nav, search and pane switching for
// panes no page renders any more.
//
// SAFE BESIDE `settings-widgets.js`, and that is deliberate: the two share ZERO delegated
// selectors. This file touches `.ace-editor`, `.copy-settings`, `.save-settings`,
// `.toggle-draft`, `.toggle-override-non-global`; the widgets module touches `.plugin-setting*`,
// `.multi*`, `.add-multiple`, `.remove-multiple`, `.show-multiple`, `.reset-setting`. The old
// monolith could not make that claim -- it duplicated 17 of them, so a page loading both
// double-fired every one.
//
// `ace.require` at the ace block below is TOP-LEVEL and unguarded, which is why this file may
// only be loaded by a page that also loads `libs/ace` BEFORE it (both callers do, and
// `ace-mode-bunkerweb_settings.js` must sit between the two -- it reads `session.$bwRawFold`,
// stashed by the editor init here, and silently stops folding if that ordering breaks).
$(document).ready(() => {
  // Ensure i18next is loaded before using it
  const t = typeof i18next !== "undefined" ? i18next.t : (key) => key; // Fallback

  let toastNum = 0;

  const isReadOnlyValue = $("#is-read-only").val() || "";
  const isReadOnly = isReadOnlyValue.trim() === "True";

  if (isReadOnly && window.location.pathname.endsWith("/new"))
    window.location.href = window.location.href.split("/new")[0];

  // Canonical RAW-editor key universe emitted by the server (#raw-known-keys).
  // Shared by the raw-config parser (issue #3651) and the settings fold mode.
  // Returns {keys, bases, multiline, multilineBases} (all arrays).
  const parseRawKeySpec = () => {
    try {
      const parsed = JSON.parse($("#raw-known-keys").val() || "{}") || {};
      return {
        keys: parsed.keys || [],
        bases: parsed.bases || [],
        multiline: parsed.multiline || [],
        multilineBases: parsed.multilineBases || [],
      };
    } catch (_e) {
      return { keys: [], bases: [], multiline: [], multilineBases: [] };
    }
  };

  // Build the shared RAW key predicates from #raw-known-keys. Single source of
  // truth for the raw-config parser, the locked-line highlighter, and the
  // settings fold mode, so "what is a setting key" / "what can be multiline" is
  // decided identically everywhere (issue #3651).
  const makeRawKeyPredicates = () => {
    const spec = parseRawKeySpec();
    const knownKeys = new Set(spec.keys);
    const multilineKeys = new Set(spec.multiline);
    const matchesKeySet = (token, keySet, baseList) => {
      if (!token) return false;
      if (keySet.has(token)) return true;
      for (let i = 0; i < baseList.length; i++) {
        const base = baseList[i];
        if (
          base &&
          token.indexOf(base + "_") === 0 &&
          /^\d+$/.test(token.slice(base.length + 1))
        ) {
          return true;
        }
      }
      return false;
    };
    return {
      spec,
      // The setting key a physical line declares, or null if it is not a
      // `KEY=...` line at all.
      keyOfLine: (line) => {
        const eq = line.indexOf("=");
        return eq === -1 ? null : line.slice(0, eq).trim();
      },
      isKnownSettingKey: (token) => matchesKeySet(token, knownKeys, spec.bases),
      isMultilineKey: (token) =>
        matchesKeySet(token, multilineKeys, spec.multilineBases),
    };
  };

  const isOverrideNonGlobalEnabled = () =>
    ($("#override-non-global-settings").val() || "no")
      .toString()
      .trim()
      .toLowerCase() === "yes";

  const setOverrideNonGlobalEnabled = (enabled) => {
    const value = enabled ? "yes" : "no";

    const $hidden = $("#override-non-global-settings");
    if ($hidden.length) {
      $hidden.val(value);
    }

    const $buttons = $(
      "#override-non-global-settings-toggle, #override-non-global-settings-toggle-mobile",
    );
    $buttons
      .toggleClass("btn-outline-secondary", !enabled)
      .toggleClass("btn-primary", enabled)
      .attr("aria-pressed", enabled ? "true" : "false");

    $buttons.find("i").each(function () {
      $(this)
        .toggleClass("bx-toggle-left", !enabled)
        .toggleClass("bx-toggle-right", enabled);
    });
  };

  if ($("#override-non-global-settings").length) {
    setOverrideNonGlobalEnabled(isOverrideNonGlobalEnabled());
  }

  $(document).on("click", ".toggle-override-non-global", () => {
    setOverrideNonGlobalEnabled(!isOverrideNonGlobalEnabled());
  });

  const $serviceMethodInput = $("#service-method");

  // The raw editor's serialiser. Was `getFormFromSettings(elem)` with easy / advanced / raw
  // branches; only the raw one survives, and `elem` was never read even then.
  const buildRawForm = () => {
    const form = $("<form>", {
      method: "POST",
      action: window.location.href,
      class: "visually-hidden",
    });

    // Helper function to append hidden inputs
    const appendHiddenInput = (form, name, value, asTextarea = false) => {
      if (asTextarea) {
        const $textarea = $("<textarea>", {
          name: name,
          class: "visually-hidden",
        });
        $textarea.val(value ?? "");
        form.append($textarea);
        return;
      }

      form.append(
        $("<input>", {
          type: "hidden",
          name: name,
          value: value,
        }),
      );
    };

    // Handle missing CSRF token gracefully
    const csrfToken = $("#csrf_token").val() || "";
    appendHiddenInput(form, "csrf_token", csrfToken);

    // Key universe emitted by the RAW template (#raw-known-keys): every valid
    // setting key, the base-prefixes of "multiple" settings, and the subset of
    // keys that hold multiline values (type:"file" settings such as
    // CUSTOM_SSL_CERT_DATA / CUSTOM_SSL_KEY_DATA / *_TRUSTED_CERTIFICATE_DATA).
    // The parser below uses it so a PEM/base64 block is reassembled instead of
    // being shattered into bogus variables on save (issue #3651).
    const { isKnownSettingKey, isMultilineKey } = makeRawKeyPredicates();

    // Parse env-style raw config into ordered [key, value] pairs. A physical
    // line begins a new pair only when the token before its first "=" is a
    // known setting key; any other line is a continuation that is folded back
    // into the current value — but ONLY when the current key is multiline
    // capable, so ordinary single-line settings can never absorb stray lines.
    // Split once on the first "=" (indexOf, not split) so base64 "==" padding
    // and "=" inside values survive untouched.
    const parseRawConfig = (rawText) => {
      const pairs = [];
      if (!rawText) return pairs;
      let current = null;
      const flush = () => {
        if (!current) return;
        // Single-line values keep the historical trim(); multiline (file)
        // values are preserved verbatim because PEM/base64 are byte-sensitive.
        if (!isMultilineKey(current.key)) current.value = current.value.trim();
        pairs.push(current);
        current = null;
      };
      rawText
        .replace(/\r\n?/g, "\n")
        .split("\n")
        .forEach((line) => {
          const eq = line.indexOf("=");
          const candidateKey = eq === -1 ? null : line.slice(0, eq).trim();
          if (candidateKey !== null && isKnownSettingKey(candidateKey)) {
            flush();
            current = { key: candidateKey, value: line.slice(eq + 1) };
          } else if (current && isMultilineKey(current.key)) {
            current.value += "\n" + line;
          }
          // Otherwise: a stray/blank/comment line under a single-line setting,
          // or content before the first key -> ignore (generated config never
          // produces these).
        });
      flush();
      return pairs;
    };

    // Helper to fold a raw config blob into a {key: value} object.
    const parseConfig = (selector) => {
      const acc = {};
      parseRawConfig($(selector).val()).forEach(({ key, value }) => {
        if (key) acc[key] = value;
      });
      return acc;
    };

    // Parse original and default configurations
    const entireconfigOriginals = parseConfig("#raw-entire-config");
    const configDefaults = parseConfig("#raw-config-defaults");

    // Sets to keep track of processed keys
    const formKeys = new Set();
    const skippedKeys = new Set();

    // Process the current configuration
    const rawEditor = editorRegistry["raw-config-editor"];
    const rawConfigSource = rawEditor
      ? rawEditor.getValue()
      : $("#raw-config").val();
    parseRawConfig(rawConfigSource).forEach(({ key, value }) => {
      if (!key) return;
      if (key === "IS_DRAFT") {
        skippedKeys.add(key);
        return;
      }
      appendHiddenInput(form, key, value, String(value).indexOf("\n") !== -1);
      formKeys.add(key);
    });

    // Append default values if they are not already in the form and not skipped
    Object.entries(configDefaults).forEach(([key, value]) => {
      if (!formKeys.has(key) && !skippedKeys.has(key)) {
        appendHiddenInput(form, key, value, String(value).indexOf("\n") !== -1);
        formKeys.add(key);
      }
    });

    // Append original values if they are not already in the form and not skipped
    Object.entries(entireconfigOriginals).forEach(([key, value]) => {
      if (!formKeys.has(key) && !skippedKeys.has(key)) {
        appendHiddenInput(form, key, value, String(value).indexOf("\n") !== -1);
        formKeys.add(key);
      }
    });

    // Always post current draft state, including in raw mode.
    const $draftInput = $("#is-draft");
    if ($draftInput.length) {
      appendHiddenInput(form, "IS_DRAFT", $draftInput.val());
    }

    // OLD_SERVER_NAME, by NAME rather than by the old `#old-server-name` id.
    //
    // That id was emitted by models/plugin_settings_body.html, i.e. only inside the
    // `general` plugin's body -- which reached the service page only through the advanced
    // pane. With the pane gone the id no longer exists anywhere, and an unposted
    // OLD_SERVER_NAME is not a cosmetic loss: routes/services.py pops it to "",
    // Config.edit_service then reads `old_server_name.split()[0]` and raises IndexError
    // inside CONFIG_TASKS_EXECUTOR, which never clears DATA["RELOADING"] -- the save is lost
    // and the loading page spins forever. The compose shelf emits the key as a plain
    // control-key input (models/compose_shelf.html), so match on the name and take the first
    // in document order, which is the same one `request.form.to_dict()` would keep.
    const $oldServerName = $('[name="OLD_SERVER_NAME"]').first();
    if ($oldServerName.length) {
      appendHiddenInput(form, "OLD_SERVER_NAME", $oldServerName.val());
    }

    const hasOverrideNonGlobalSetting =
      $("#override-non-global-settings").length > 0;
    if (hasOverrideNonGlobalSetting) {
      const overrideNonGlobalServices = isOverrideNonGlobalEnabled();
      appendHiddenInput(
        form,
        "OVERRIDE_NON_GLOBAL_SERVICES",
        overrideNonGlobalServices ? "yes" : "no",
      );
    }

    return form;
  };

  // `.save-settings` is now the RAW pane's button and nothing else: the compose pane submits
  // its own real form with a plain `type="submit"` (models/compose_pane.html), deliberately
  // without this class, because this handler serialises the raw editor and would post neither
  // the shelf nor its control keys. The old `currentMode` branch is gone with the modes.
  $(".save-settings").on("click", async function () {
    if (isReadOnly) {
      alert(t("alert.readonly_mode"));
      return;
    }

    const form = buildRawForm();

    const draftInput = $("#is-draft");
    const wasDraft = draftInput.data("original") === "yes";
    const isDraft = form.find("input[name='IS_DRAFT']").val() === "yes";

    if (form.children().length < 2 && isDraft === wasDraft) {
      alert(t("alert.no_changes_detected"));
      return;
    }

    form.appendTo("body").submit();
  });

  $(".toggle-draft").on("click", function () {
    const draftInput = $("#is-draft");
    const isDraft = draftInput.val() === "yes";
    const newValue = isDraft ? "no" : "yes";

    draftInput.val(newValue);
    const newStatusKey = isDraft ? "status.online" : "status.draft";
    $(".toggle-draft").html(
      `<i class="bx bx-sm bx-${
        isDraft ? "globe" : "file-blank"
      }"></i>&nbsp; <span data-i18n="${newStatusKey}">${t(newStatusKey)}</span>`,
    );

    // Keep the raw editor's IS_DRAFT line in sync with the toggle button. Without
    // this the raw editor would still display the previous IS_DRAFT value after
    // toggling, and a subsequent direct edit in the editor (which is the source
    // of truth in raw mode through the editor->#is-draft change handler) would
    // overwrite the toggle's new value with the stale editor line.
    const rawEditor = editorRegistry["raw-config-editor"];
    if (rawEditor) {
      const lines = rawEditor.getValue().split("\n");
      let mutated = false;
      for (let i = 0; i < lines.length; i++) {
        if (/^\s*IS_DRAFT\s*=/.test(lines[i])) {
          const replacement = `IS_DRAFT=${newValue}`;
          if (lines[i] !== replacement) {
            lines[i] = replacement;
            mutated = true;
          }
          break;
        }
      }
      if (mutated) {
        rawEditor.setValue(lines.join("\n"), -1);
      }
    }
  });

  $(".copy-settings").on("click", function () {
    const rawEditor = editorRegistry["raw-config-editor"];
    const config = rawEditor ? rawEditor.getValue() : $("#raw-config").val();

    // Use the Clipboard API
    navigator.clipboard
      .writeText(config)
      .then(() => {
        // Show tooltip
        const button = $(this);
        button
          .attr("data-bs-original-title", t("tooltip.copied"))
          .tooltip("show");

        // Hide tooltip after 2 seconds
        setTimeout(() => {
          button.tooltip("hide").attr("data-bs-original-title", "");
        }, 2000);
      })
      .catch((err) => {
        console.error("Failed to copy text: ", err);
      });
  });

  if ($serviceMethodInput.length) {
    if ($serviceMethodInput.val() === "autoconf") {
      const feedbackToast = $("#feedback-toast").clone(); // Clone the feedback toast
      feedbackToast.attr("id", `feedback-toast-${toastNum++}`); // Corrected to set the ID for the failed toast
      feedbackToast.find("span").text("Disclaimer");
      feedbackToast
        .find(".fw-medium")
        .text(t("toast.disclaimer_title"))
        .attr("data-i18n", "toast.disclaimer_title");
      feedbackToast
        .find("div.toast-body")
        .html(
          `<div class='fw-bolder' data-i18n="toast.autoconf_disclaimer_bold">${t(
            "toast.autoconf_disclaimer_bold",
          )}</div><span data-i18n="toast.autoconf_disclaimer_detail">${t(
            "toast.autoconf_disclaimer_detail",
          )}</span>`,
        );
      feedbackToast.attr("data-bs-autohide", "false");
      feedbackToast.appendTo("#feedback-toast-container"); // Ensure the toast is appended to the container
      feedbackToast.toast("show");
    }
  }

  const AceRange = ace.require("ace/range").Range;
  var editors = [];
  var editorRegistry = {};
  const triggerRawConfigSave = () => {
    const $saveBtn = $(".raw-config-save-btn").not(".disabled");
    if ($saveBtn.length) {
      $saveBtn.first().trigger("click");
      return true;
    }
    return false;
  };
  let rawDisabledMarkers = [];
  let rawDisabledGutterRows = [];

  const setupRawDisabledHighlight = (editor) => {
    const disabledRaw = $("#raw-config-disabled").val();
    if (!disabledRaw) {
      rawDisabledMarkers.forEach((id) => editor.session.removeMarker(id));
      rawDisabledMarkers = [];
      rawDisabledGutterRows.forEach((row) =>
        editor.session.removeGutterDecoration(row, "raw-disabled-gutter"),
      );
      rawDisabledGutterRows = [];
      const remainingAnnotations = editor.session
        .getAnnotations()
        .filter((annotation) => !annotation.rawDisabled);
      editor.session.setAnnotations(remainingAnnotations);
      return;
    }

    const disabledMap = new Map(
      disabledRaw
        .split(/\r?\n/)
        .map((entry) => entry.trim())
        .filter(Boolean)
        .map((entry) => {
          const [key, reason] = entry.split("::");
          return [key.trim(), (reason || "locked").trim()];
        }),
    );

    // Same key predicates as the raw parser, so a locked MULTILINE setting
    // (e.g. a method-managed CUSTOM_SSL_CERT_DATA) highlights its whole
    // PEM/base64 block, not just the header row.
    const { keyOfLine, isKnownSettingKey, isMultilineKey } =
      makeRawKeyPredicates();

    const refreshDisabledIndicators = () => {
      rawDisabledMarkers.forEach((id) => editor.session.removeMarker(id));
      rawDisabledMarkers = [];
      rawDisabledGutterRows.forEach((row) =>
        editor.session.removeGutterDecoration(row, "raw-disabled-gutter"),
      );
      rawDisabledGutterRows = [];

      const baseAnnotations = editor.session
        .getAnnotations()
        .filter((annotation) => !annotation.rawDisabled);
      const disabledAnnotations = [];

      const lines = editor.session.getDocument().getAllLines();
      let row = 0;
      while (row < lines.length) {
        const key = keyOfLine(lines[row]);
        if (!key || !isKnownSettingKey(key) || !disabledMap.has(key)) {
          row++;
          continue;
        }

        // A locked multiline setting spans its continuation rows too, up to the
        // next real KEY= line.
        let endRow = row;
        if (isMultilineKey(key)) {
          while (
            endRow + 1 < lines.length &&
            !isKnownSettingKey(keyOfLine(lines[endRow + 1]) || "")
          ) {
            endRow++;
          }
        }

        const methodKey = disabledMap.get(key);
        const methodLabel = methodKey
          .replace(/_/g, " ")
          .replace(/\b\w/g, (char) => char.toUpperCase());
        for (let r = row; r <= endRow; r++) {
          const range = new AceRange(r, 0, r, Infinity);
          rawDisabledMarkers.push(
            editor.session.addMarker(range, "raw-disabled-line", "fullLine"),
          );
          editor.session.addGutterDecoration(r, "raw-disabled-gutter");
          rawDisabledGutterRows.push(r);
        }

        disabledAnnotations.push({
          row,
          column: 0,
          rawDisabled: true,
          type: "info",
          className: " raw-disabled-annotation",
          text: t("legend.locked_settings_annotation", {
            defaultValue: `Locked (${methodLabel})`,
            method: methodLabel,
            rawMethod: methodKey,
          }),
        });
        row = endRow + 1;
      }

      editor.session.setAnnotations(
        baseAnnotations.concat(disabledAnnotations),
      );
    };

    refreshDisabledIndicators();
    editor.on("change", refreshDisabledIndicators);
  };

  $(".ace-editor").each(function () {
    const $editorElement = $(this);
    const sourceSelector = $editorElement.data("source");
    const $source = sourceSelector ? $(sourceSelector) : null;
    let initialContent = "";

    if ($source && $source.length) {
      if ($source.is("textarea, input")) {
        initialContent = $source.val() || "";
      } else {
        initialContent = ($source.text() || "").trim();
      }
    } else {
      initialContent = $editorElement.text().trim();
    }

    const editor = ace.edit(this);

    editor.session.setMode("ace/mode/nginx");
    // const language = $(this).data("language"); // TODO: Support ModSecurity
    // if (language === "NGINX") {
    //   editor.session.setMode("ace/mode/nginx");
    // } else {
    //   editor.session.setMode("ace/mode/text"); // Default mode if language is unrecognized
    // }

    const method = $editorElement.data("method");
    const explicitReadOnly = $editorElement.data("readonly");
    if (typeof explicitReadOnly !== "undefined") {
      editor.setReadOnly(
        explicitReadOnly === true || explicitReadOnly === "true",
      );
    } else if (method !== "ui" && method !== "api" && method !== "default") {
      editor.setReadOnly(true);
    }

    // Set the editor's initial content
    editor.setValue(initialContent, -1); // The second parameter moves the cursor to the start

    editor.setOptions({
      fontSize: "14px",
      showPrintMargin: false,
      tabSize: 2,
      useSoftTabs: true,
      wrap: true,
    });

    editor.renderer.setPadding(12);
    editor.renderer.setScrollMargin(16, 16);
    editors.push(editor);

    const elementId = $editorElement.attr("id");
    if (elementId) {
      editorRegistry[elementId] = editor;
    }

    if (elementId === "raw-config-editor") {
      // Env-style settings get their own fold-aware mode instead of the generic
      // nginx grammar: multiline file values (PEM/base64) collapse under their
      // KEY= header. The fold predicates come from the SAME #raw-known-keys the
      // save-time parser uses (issue #3651) and are stashed on the session so
      // the (schema-agnostic) FoldMode can read them.
      const rawFoldPreds = makeRawKeyPredicates();
      const lineKeyMatches = (line, test) => {
        const key = rawFoldPreds.keyOfLine(line || "");
        return key !== null && test(key);
      };
      editor.session.$bwRawFold = {
        isKnownKeyLine: (line) =>
          lineKeyMatches(line, rawFoldPreds.isKnownSettingKey),
        isMultilineKeyLine: (line) =>
          lineKeyMatches(line, rawFoldPreds.isMultilineKey),
      };
      editor.session.setMode("ace/mode/bunkerweb_settings");

      // foldAll()/the gutter chevron create folds with the default "..."
      // placeholder; copy back the FoldMode's "⋯ N lines" label (same trick as
      // the logs viewer).
      editor.session.on("changeFold", (e) => {
        const fold = e.data;
        if (
          e.action === "add" &&
          fold &&
          fold.placeholder === "..." &&
          fold.range &&
          fold.range.placeholder
        ) {
          fold.placeholder = fold.range.placeholder;
        }
      });

      // Collapse-all / expand-all toggle in the raw toolbar (default expanded).
      const $foldToggle = $(".raw-config-fold-toggle");
      if ($foldToggle.length) {
        let collapsed = false;
        $foldToggle.on("click", function () {
          collapsed = !collapsed;
          $(this)
            .toggleClass("active", collapsed)
            .attr("aria-pressed", String(collapsed));
          if (collapsed) editor.session.foldAll();
          else editor.session.unfold();
        });
      }

      editor.commands.addCommand({
        name: "saveRawConfigShortcut",
        bindKey: { win: "Ctrl-S", mac: "Command-S" },
        exec: () => {
          triggerRawConfigSave();
        },
        readOnly: false,
      });

      const $rawConfigHidden = $("#raw-config");
      if ($rawConfigHidden.length) {
        $rawConfigHidden.val(editor.getValue());
        editor.on("change", () => {
          $rawConfigHidden.val(editor.getValue());
        });
      }

      // Mirror direct edits to the IS_DRAFT line back into the canonical
      // #is-draft hidden input (and the visible toggle button). The form-build
      // path posts IS_DRAFT from #is-draft, so without this sync a user typing
      // IS_DRAFT=yes directly in the raw editor would never reach the route.
      const syncDraftFromEditor = () => {
        const $draftInput = $("#is-draft");
        if (!$draftInput.length) return;
        const draftLine = editor
          .getValue()
          .split("\n")
          .map((l) => l.trim())
          .find((l) => /^IS_DRAFT\s*=/.test(l));
        if (!draftLine) return;
        const value = draftLine.split("=").slice(1).join("=").trim();
        if (value !== "yes" && value !== "no") return;
        if ($draftInput.val() === value) return;
        $draftInput.val(value);
        const statusKey = value === "yes" ? "status.draft" : "status.online";
        $(".toggle-draft").html(
          `<i class="bx bx-sm bx-${
            value === "yes" ? "file-blank" : "globe"
          }"></i>&nbsp; <span data-i18n="${statusKey}">${t(statusKey)}</span>`,
        );
      };
      syncDraftFromEditor();
      editor.on("change", syncDraftFromEditor);

      setupRawDisabledHighlight(editor);
    }

    if ($source && $source.length && $source.is("textarea, input")) {
      $source.val(editor.getValue());
      editor.on("change", () => {
        $source.val(editor.getValue());
      });
    }
  });

  var theme = $("#theme").val();

  function setEditorTheme() {
    editors.forEach((editor) => {
      if (theme === "dark") {
        editor.setTheme("ace/theme/cloud9_night");
      } else {
        editor.setTheme("ace/theme/cloud9_day");
      }
    });
  }

  setEditorTheme();

  $("#dark-mode-toggle").on("change", function () {
    setTimeout(() => {
      theme = $("#theme").val();
      setEditorTheme();
    }, 30);
  });

  $(document).on("keydown.rawConfigShortcut", function (e) {
    if (!(e.ctrlKey || e.metaKey)) return;
    if (e.key.toLowerCase() !== "s") return;
    if (!$(".raw-config-container").length) return;

    if ($(e.target).hasClass("ace_text-input")) return;

    // Was `currentMode === "raw"`, a module variable the mode machinery kept in sync. The
    // pane's own state is the honest source now, and the gate is not optional: the raw text
    // is server-rendered once and never re-derived from the compose pane, so a Ctrl-S while
    // compose is showing would submit the ORIGINAL config and silently discard every compose
    // edit. Regenerating raw on tab-show is S3.5's job; refusing here is this slice's.
    if ($("#navs-modes-raw").hasClass("active")) {
      e.preventDefault();
      triggerRawConfigSave();
    }
  });
});
