$(document).ready(function () {
  // Ensure i18next is loaded before using it
  const t =
    typeof i18next !== "undefined"
      ? i18next.t
      : (key, fallback, options) => {
          // Basic fallback supporting simple interpolation
          let translated = fallback || key;
          if (options) {
            for (const optKey in options) {
              translated = translated.replace(`{{${optKey}}}`, options[optKey]);
            }
          }
          return translated;
        };

  const editorElement = $("#raw-logs");
  const initialContent = editorElement.text().trim();
  const editor = ace.edit(editorElement[0]);
  var theme = $("#theme").val();
  let eventSource = null;
  let isFollowing = false;

  // Get current file from URL parameters
  const urlParams = new URLSearchParams(window.location.search);
  const currentFile = urlParams.get("file");

  // Keep the in-browser buffer aligned with the server page size (logs.py
  // PAGE_SIZE) so follow-mode never trims below what the page first loaded.
  const MAX_LOG_LINES = 10000;

  function setEditorTheme() {
    if (theme === "dark") {
      editor.setTheme("ace/theme/cloud9_night");
    } else {
      editor.setTheme("ace/theme/cloud9_day");
    }
  }

  setEditorTheme();
  editor.session.setMode("ace/mode/bunkerweb_log");
  // ACE's foldAll() and the native gutter chevron both create folds with the
  // default "..." placeholder, discarding the labelled count the FoldMode set on
  // the fold range. Copy it back so every collapsed entry shows "⋯ N lines" /
  // "Traceback (N lines)" — the FoldMode stays the single source of the label.
  editor.session.on("changeFold", function (e) {
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
  editor.setReadOnly(true);
  editor.setOptions({
    fontSize: "14px",
    showPrintMargin: false,
    tabSize: 2,
    useSoftTabs: true,
    wrap: true,
  });
  editor.renderer.setScrollMargin(10, 10);

  // ============================ Content pipeline ============================
  // fullText is the source of truth (mirrors the file). allLines is its split
  // view. The editor only ever shows computeVisible(): level-filtered, tailed
  // and optionally time-localized. Rebuilding from fullText keeps append/trim
  // seam-safe (same as plain string concatenation).
  const state = {
    fullText: initialContent,
    allLines: [],
    hiddenLevels: new Set(),
    tailLimit: 0, // 0 = all
    localTime: false,
    collapse: false,
  };
  function syncLines() {
    if (!state.fullText.length) {
      state.allLines = [];
      return;
    }
    const parts = state.fullText.split("\n");
    // Drop the single trailing empty element produced by a final newline, so an
    // appended chunk starts a fresh line instead of merging onto the last one.
    if (parts[parts.length - 1] === "") parts.pop();
    state.allLines = parts;
  }
  syncLines();

  // ---- Level detection (mirrors the ACE mode's matchers, all formats) ----
  const LEVELS = [
    { key: "critical", cls: "danger", icon: "bx-error", label: "Critical" },
    { key: "error", cls: "danger", icon: "bx-error-circle", label: "Error" },
    { key: "warning", cls: "warning", icon: "bx-error", label: "Warning" },
    { key: "notice", cls: "info", icon: "bx-info-circle", label: "Notice" },
    { key: "info", cls: "info", icon: "bx-info-circle", label: "Info" },
    { key: "debug", cls: "secondary", icon: "bx-bug", label: "Debug" },
  ];
  const LEVEL_RES = {
    critical: /\[\s*(?:CRITICAL|🚨)\s*\]|:CRITICAL:|\s\[emerg\]\s/u,
    error: /\[\s*(?:ERROR|❌)\s*\]|:ERROR:|\s\[(?:error|alert|crit)\]\s/u,
    warning: /\[\s*(?:WARNING|⚠️?)\s*\]|:WARNING:|\s\[warn\]\s/u,
    notice: /\s\[notice\]\s/u,
    info: /\[\s*(?:INFO|ℹ️?)\s*\]|:INFO:/u,
    debug: /\[\s*(?:DEBUG|🐛)\s*\]|:DEBUG:/u,
  };
  function levelOf(line) {
    // Only inspect the structured prefix (before the first quote). Access-log
    // request / referer / user-agent fields are quoted and attacker-controlled,
    // so a "[ERROR]" injected into a URL must not classify the line as an error.
    const q = line.indexOf('"');
    const head = q === -1 ? line : line.slice(0, q);
    for (const L of LEVELS) if (LEVEL_RES[L.key].test(head)) return L.key;
    return null;
  }
  function classifyLine(line) {
    const lv = levelOf(line);
    if (lv === "critical" || lv === "error") return "error";
    if (lv === "warning") return "warning";
    return null;
  }

  // ---- Optional local-time rewrite of leading timestamps (opt-in) ----
  const pad = (n) => String(n).padStart(2, "0");
  function localOffset(d) {
    const off = -d.getTimezoneOffset();
    const a = Math.abs(off);
    return (off >= 0 ? "+" : "-") + pad(Math.floor(a / 60)) + pad(a % 60);
  }
  function fmtLocal(d) {
    return (
      d.getFullYear() +
      "-" +
      pad(d.getMonth() + 1) +
      "-" +
      pad(d.getDate()) +
      " " +
      pad(d.getHours()) +
      ":" +
      pad(d.getMinutes()) +
      ":" +
      pad(d.getSeconds())
    );
  }
  const TS_BRACKET = /^\[(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2}) ([+-]\d{4})\]/;
  const TS_PLAIN = /^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2})(,\d+)?(?=[:\s])/;
  const TS_NGINX = /^(\d{4})\/(\d{2})\/(\d{2}) (\d{2}:\d{2}:\d{2})(?=\s)/;
  function localizeLine(line) {
    let m = TS_BRACKET.exec(line);
    if (m) {
      const tz = m[3].slice(0, 3) + ":" + m[3].slice(3);
      const d = new Date(m[1] + "T" + m[2] + tz);
      return isNaN(d)
        ? line
        : "[" +
            fmtLocal(d) +
            " " +
            localOffset(d) +
            "]" +
            line.slice(m[0].length);
    }
    m = TS_PLAIN.exec(line);
    if (m) {
      const d = new Date(m[1] + "T" + m[2] + "Z"); // tz-less logs assumed UTC
      return isNaN(d)
        ? line
        : fmtLocal(d) + (m[3] || "") + line.slice(m[0].length);
    }
    m = TS_NGINX.exec(line);
    if (m) {
      const d = new Date(m[1] + "-" + m[2] + "-" + m[3] + "T" + m[4] + "Z");
      if (isNaN(d)) return line;
      return (
        d.getFullYear() +
        "/" +
        pad(d.getMonth() + 1) +
        "/" +
        pad(d.getDate()) +
        " " +
        pad(d.getHours()) +
        ":" +
        pad(d.getMinutes()) +
        ":" +
        pad(d.getSeconds()) +
        line.slice(m[0].length)
      );
    }
    return line;
  }

  function computeVisible() {
    let lines = state.allLines;
    if (state.hiddenLevels.size) {
      // Filter by ENTRY, not by line: a continuation line (traceback frame /
      // config-dump body — no level of its own) inherits the level of the log
      // entry it belongs to, so hiding a level hides the whole multi-line entry
      // instead of dropping only its header and orphaning the body under a
      // surviving entry (which also mislabels a fold's line count).
      let entryLevel = null;
      const isStart =
        typeof bwlogIsLogStart === "function" ? bwlogIsLogStart : () => true;
      lines = lines.filter((l) => {
        const lv = levelOf(l);
        if (lv)
          entryLevel = lv; // a header carries the entry's level
        else if (isStart(l)) entryLevel = null; // level-less start (access log) = own entry
        const eff = lv || entryLevel; // continuation inherits its header's level
        return !eff || !state.hiddenLevels.has(eff);
      });
    }
    if (state.tailLimit && lines.length > state.tailLimit) {
      lines = lines.slice(-state.tailLimit);
    }
    if (state.localTime) lines = lines.map(localizeLine);
    return lines;
  }

  function renderView(opts) {
    opts = opts || {};
    const visible = computeVisible();
    editor.setValue(visible.join("\n"), -1);
    refreshAnnotations();
    updateShowing(visible.length);
    if (state.collapse) editor.session.foldAll();
    if (opts.toBottom) scrollToBottom();
  }

  function updateShowing(visibleCount) {
    const el = document.getElementById("logs-showing");
    if (!el) return;
    const total = state.allLines.length;
    if (visibleCount === total) {
      el.textContent = t("logs.showing_all", "{{total}} lines", {
        total: total.toLocaleString(),
      });
    } else {
      el.textContent = t(
        "logs.showing_some",
        "showing {{shown}} of {{total}}",
        {
          shown: visibleCount.toLocaleString(),
          total: total.toLocaleString(),
        },
      );
    }
  }

  // ============================ Level filter chips ============================
  let lastLevelsKey = "";
  function makeChip(L, count) {
    const hidden = state.hiddenLevels.has(L.key);
    const btn = document.createElement("button");
    btn.type = "button";
    btn.dataset.level = L.key;
    btn.className =
      "btn btn-sm logs-chip me-1 mb-1 " +
      (hidden ? "btn-outline-secondary logs-chip-off" : "btn-outline-" + L.cls);
    btn.setAttribute("aria-pressed", String(!hidden));
    const label = t("logs.level_" + L.key, L.label);
    btn.title = t("tooltip.toggle_level", "Show / hide {{level}} lines", {
      level: label,
    });
    // Build with DOM methods (no innerHTML) — all values are trusted, but this
    // keeps the chip XSS-proof by construction.
    const icon = document.createElement("i");
    icon.className = "bx " + L.icon + " bx-xs";
    icon.setAttribute("aria-hidden", "true");
    const countEl = document.createElement("span");
    countEl.className = "ms-1 logs-chip-count";
    countEl.id = "logs-chip-count-" + L.key;
    countEl.textContent = count;
    btn.appendChild(icon);
    btn.appendChild(document.createTextNode(" " + label + " "));
    btn.appendChild(countEl);
    btn.addEventListener("click", () => toggleLevel(L, btn));
    return btn;
  }
  function toggleLevel(L, btn) {
    if (state.hiddenLevels.has(L.key)) state.hiddenLevels.delete(L.key);
    else state.hiddenLevels.add(L.key);
    const hidden = state.hiddenLevels.has(L.key);
    btn.setAttribute("aria-pressed", String(!hidden));
    btn.classList.toggle("logs-chip-off", hidden);
    btn.classList.remove("btn-outline-" + L.cls, "btn-outline-secondary");
    btn.classList.add(
      hidden ? "btn-outline-secondary" : "btn-outline-" + L.cls,
    );
    renderView();
  }
  function updateCounts() {
    const counts = {};
    LEVELS.forEach((L) => (counts[L.key] = 0));
    for (const line of state.allLines) {
      const lv = levelOf(line);
      if (lv) counts[lv]++;
    }
    const present = LEVELS.filter((L) => counts[L.key] > 0);
    const container = document.getElementById("logs-level-chips");
    if (!container) return;
    const key = present.map((L) => L.key).join(",");
    if (key !== lastLevelsKey) {
      container.replaceChildren();
      present.forEach((L) => container.appendChild(makeChip(L, counts[L.key])));
      lastLevelsKey = key;
    } else {
      present.forEach((L) => {
        const c = document.getElementById("logs-chip-count-" + L.key);
        if (c) c.textContent = counts[L.key];
      });
    }
  }

  // ============================ Error annotations ============================
  let issueRows = [];
  let annTimer = null;
  function refreshAnnotations() {
    const session = editor.getSession();
    const total = session.getLength();
    const annotations = [];
    issueRows = [];
    let errors = 0;
    let warnings = 0;
    for (let row = 0; row < total; row++) {
      const sev = classifyLine(session.getLine(row));
      if (!sev) continue;
      annotations.push({
        row: row,
        column: 0,
        type: sev,
        text:
          sev === "error"
            ? t("logs.annotation_error", "Error")
            : t("logs.annotation_warning", "Warning"),
      });
      issueRows.push(row);
      if (sev === "error") errors++;
      else warnings++;
    }
    session.setAnnotations(annotations);
    updateIssueUI(errors, warnings);
  }
  function scheduleAnnotationRefresh() {
    if (annTimer) clearTimeout(annTimer);
    annTimer = setTimeout(refreshAnnotations, 300);
  }
  function updateIssueUI(errors, warnings) {
    const labelEl = document.getElementById("logs-issue-label");
    const countBtn = document.getElementById("logs-issue-count");
    const prevBtn = document.getElementById("logs-prev-issue");
    const nextBtn = document.getElementById("logs-next-issue");
    const totalIssues = errors + warnings;
    if (labelEl) labelEl.textContent = String(totalIssues);
    const variant = errors
      ? "btn-outline-danger"
      : warnings
        ? "btn-outline-warning"
        : "btn-outline-secondary";
    [prevBtn, countBtn, nextBtn].forEach((b) => {
      if (!b) return;
      b.classList.remove(
        "btn-outline-secondary",
        "btn-outline-warning",
        "btn-outline-danger",
      );
      b.classList.add(variant);
    });
    if (countBtn) {
      const summary = t(
        "logs.issue_summary",
        "{{errors}} error(s), {{warnings}} warning(s)",
        { errors: errors, warnings: warnings },
      );
      countBtn.setAttribute("title", summary);
      countBtn.setAttribute("aria-label", summary); // expose count to assistive tech
    }
    [prevBtn, nextBtn].forEach((b) => {
      if (b) b.disabled = totalIssues === 0;
    });
  }
  function jumpToIssue(direction) {
    if (!issueRows.length) return;
    const cur = editor.getCursorPosition().row;
    let target = null;
    if (direction > 0) {
      target = issueRows.find((r) => r > cur);
      if (target === undefined) target = issueRows[0];
    } else {
      for (let i = issueRows.length - 1; i >= 0; i--) {
        if (issueRows[i] < cur) {
          target = issueRows[i];
          break;
        }
      }
      if (target === null) target = issueRows[issueRows.length - 1];
    }
    editor.gotoLine(target + 1, 0, true);
    editor.scrollToLine(target, true, true);
    editor.focus();
  }

  // ============================ Toolbar wiring ============================
  const searchBtn = document.getElementById("logs-search");
  if (searchBtn)
    searchBtn.addEventListener("click", () => editor.execCommand("find"));

  const prevIssueBtn = document.getElementById("logs-prev-issue");
  if (prevIssueBtn)
    prevIssueBtn.addEventListener("click", () => jumpToIssue(-1));
  const nextIssueBtn = document.getElementById("logs-next-issue");
  if (nextIssueBtn)
    nextIssueBtn.addEventListener("click", () => jumpToIssue(1));

  let wrapEnabled = true;
  const wrapBtn = document.getElementById("logs-wrap");
  if (wrapBtn)
    wrapBtn.addEventListener("click", function () {
      wrapEnabled = !wrapEnabled;
      editor.getSession().setUseWrapMode(wrapEnabled);
      this.classList.toggle("active", wrapEnabled);
      this.setAttribute("aria-pressed", String(wrapEnabled));
    });

  const tailSelect = document.getElementById("logs-tail");
  if (tailSelect)
    tailSelect.addEventListener("change", function () {
      state.tailLimit = parseInt(this.value, 10) || 0;
      renderView();
    });

  const localTimeBtn = document.getElementById("logs-localtime");
  if (localTimeBtn)
    localTimeBtn.addEventListener("click", function () {
      state.localTime = !state.localTime;
      this.classList.toggle("active", state.localTime);
      this.setAttribute("aria-pressed", String(state.localTime));
      renderView();
    });

  const collapseBtn = document.getElementById("logs-collapse");
  if (collapseBtn)
    collapseBtn.addEventListener("click", function () {
      state.collapse = !state.collapse;
      this.classList.toggle("active", state.collapse);
      this.setAttribute("aria-pressed", String(state.collapse));
      if (state.collapse) editor.session.foldAll();
      else editor.session.unfold();
    });

  // Download link (built relative to the current path, like the stream URL,
  // so it works behind the reverse-proxy prefix too).
  const downloadBtn = document.getElementById("logs-download");
  if (downloadBtn && currentFile) {
    downloadBtn.href =
      window.location.pathname +
      "/download?file=" +
      encodeURIComponent(currentFile);
    downloadBtn.setAttribute("download", currentFile);
  }

  // Cursor row/col overlay (ext-statusbar).
  try {
    const StatusBar = ace.require("ace/ext/statusbar").StatusBar;
    const sbEl = document.getElementById("logs-statusbar");
    if (StatusBar && sbEl) new StatusBar(editor, sbEl);
  } catch (e) {
    /* statusbar extension unavailable */
  }

  // Ctrl/Cmd-click linking (ext-linking): open real URLs, or highlight every
  // occurrence of a clicked IP to trace it through the log.
  try {
    editor.setOption("enableLinking", true);
    editor.on("linkClick", function (data) {
      const token = data && data.token;
      if (!token || !token.value) return;
      const value = token.value;
      if (/^https?:\/\//i.test(value)) {
        window.open(value, "_blank", "noopener,noreferrer");
        return;
      }
      const isIp =
        (token.type && token.type.indexOf("ip") !== -1) ||
        /^\d{1,3}(?:\.\d{1,3}){3}$/.test(value) ||
        /^[0-9a-f]*:[0-9a-f:]+$/i.test(value);
      if (isIp)
        editor.findAll(value, {
          caseSensitive: true,
          wholeWord: false,
          regExp: false,
        });
    });
  } catch (e) {
    /* linking extension unavailable */
  }

  // File metadata caption (size / lines / modified), formatted client-side.
  (function renderMeta() {
    const el = document.getElementById("logs-meta");
    if (!el || !el.dataset.size) return;
    const humanSize = (b) => {
      const u = ["B", "KB", "MB", "GB", "TB"];
      let i = 0;
      b = Number(b);
      while (b >= 1024 && i < u.length - 1) {
        b /= 1024;
        i++;
      }
      return (i ? b.toFixed(1) : b) + " " + u[i];
    };
    const lines = Number(el.dataset.lines).toLocaleString();
    const mtime = new Date(Number(el.dataset.mtime) * 1000);
    el.textContent = t(
      "logs.meta",
      "{{size}} · {{lines}} lines · modified {{when}}",
      {
        size: humanSize(el.dataset.size),
        lines: lines,
        when: isNaN(mtime) ? "?" : fmtLocal(mtime),
      },
    );
  })();

  // ============================ Follow / new-lines pill ============================
  let autoScroll = true;
  let pendingNew = 0;
  function isAtBottom() {
    return (
      editor.renderer.getLastVisibleRow() >= editor.session.getLength() - 2
    );
  }
  function scrollToBottom() {
    editor.gotoLine(editor.session.getLength(), 0, false);
  }
  function showPill() {
    const pill = document.getElementById("logs-new-pill");
    if (!pill) return;
    const c = document.getElementById("logs-new-count");
    if (c) c.textContent = pendingNew;
    pill.classList.remove("d-none");
    // Announce via a persistent live region (the pill itself is display:none-
    // toggled, which screen readers don't reliably announce).
    const sr = document.getElementById("logs-sr-status");
    if (sr)
      sr.textContent = t("logs.new_lines_sr", "{{count}} new log lines", {
        count: pendingNew,
      });
  }
  function hidePill() {
    const pill = document.getElementById("logs-new-pill");
    if (pill) pill.classList.add("d-none");
    pendingNew = 0;
    const sr = document.getElementById("logs-sr-status");
    if (sr) sr.textContent = "";
  }
  editor.session.on("changeScrollTop", () => {
    if (!isFollowing) return;
    if (isAtBottom()) {
      autoScroll = true;
      hidePill();
    } else {
      autoScroll = false;
    }
  });
  const newPill = document.getElementById("logs-new-pill");
  if (newPill)
    newPill.addEventListener("click", () => {
      autoScroll = true;
      hidePill();
      scrollToBottom();
    });

  function trimAllLines() {
    if (state.allLines.length <= MAX_LOG_LINES) return;
    // Keep MAX_LOG_LINES total INCLUDING the notice line (so the cap holds).
    const removed = state.allLines.length - (MAX_LOG_LINES - 1);
    const notice = t(
      "logs.trimmed_notice",
      "--- {{count}} older log lines were removed for performance ---",
      { count: removed },
    );
    state.allLines = [notice].concat(
      state.allLines.slice(-(MAX_LOG_LINES - 1)),
    );
    state.fullText = state.allLines.join("\n");
  }

  // ============================ Initial render ============================
  renderView();
  updateCounts();

  // Smooth scroll to bottom after content is loaded
  setTimeout(() => {
    const totalLines = editor.session.getLength();
    const duration = 1000;
    const startTime = Date.now();
    function smoothScroll() {
      const elapsed = Date.now() - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const easeOut = 1 - Math.pow(1 - progress, 3);
      editor.gotoLine(Math.floor(totalLines * easeOut), 0, false);
      if (progress < 1) requestAnimationFrame(smoothScroll);
    }
    smoothScroll();
  }, 100);

  editorElement.removeClass("visually-hidden");
  $("#logs-waiting").addClass("visually-hidden");

  // Follow logs functionality using Server-Sent Events
  function startFollowing() {
    if (!currentFile || isFollowing) return;
    isFollowing = true;
    autoScroll = true;
    const $followBtn = $("#follow-logs");
    $followBtn.find("i").removeClass("bx-play").addClass("bx-stop");
    $followBtn.find("span").text(t("button.stop", "Stop"));
    $followBtn.attr("aria-label", t("button.stop", "Stop"));
    $followBtn
      .removeClass("btn-outline-primary")
      .addClass("btn-outline-danger");

    eventSource = new EventSource(
      `${window.location.pathname}/stream?file=${encodeURIComponent(currentFile)}`,
    );

    eventSource.onmessage = function (event) {
      try {
        const data = JSON.parse(event.data);
        switch (data.type) {
          case "refresh":
            if (data.content !== undefined) {
              state.fullText = data.content;
              syncLines();
              trimAllLines();
              updateCounts();
              renderView({ toBottom: true });
            }
            break;

          case "append":
            if (data.content) {
              const before = state.allLines.length;
              state.fullText += data.content;
              syncLines();
              const added = Math.max(0, state.allLines.length - before);
              trimAllLines();
              updateCounts();
              if (autoScroll) {
                renderView({ toBottom: true });
              } else {
                pendingNew += added;
                showPill();
                scheduleQuietRender();
              }
            }
            break;

          case "rotated":
            if (data.content !== undefined) {
              state.fullText = data.content;
              syncLines();
              trimAllLines();
              updateCounts();
              renderView({ toBottom: true });
            }
            break;

          case "heartbeat":
            break;

          case "error":
            stopFollowing();
            break;
        }
      } catch (e) {
        // Ignore a malformed stream frame and wait for the next one.
      }
    };

    eventSource.onerror = function () {
      // EventSource auto-reconnects on transient drops (readyState === CONNECTING)
      // and replays the last id as Last-Event-ID so the server resumes. Only tear
      // down when the browser has given up for good (CLOSED).
      if (eventSource && eventSource.readyState === EventSource.CLOSED) {
        stopFollowing();
      }
    };
  }

  // When paused (user scrolled up), still refresh the buffer/annotations but
  // without yanking the viewport — debounced to absorb append bursts.
  let quietTimer = null;
  function scheduleQuietRender() {
    if (quietTimer) clearTimeout(quietTimer);
    quietTimer = setTimeout(() => {
      if (!isFollowing || autoScroll) return; // user returned to bottom / stopped
      const first = editor.renderer.getFirstVisibleRow();
      const visible = computeVisible();
      editor.setValue(visible.join("\n"), -1);
      // Re-apply folds (setValue clears them) so collapse survives follow-mode
      // appends, then restore the scroll anchor. scrollToLine is a pure,
      // top-aligned scroll restore with no cursor move — the right primitive for
      // a read-only viewer — and it sidesteps gotoLine's session.unfold() call
      // on the anchor row.
      if (state.collapse) editor.session.foldAll();
      editor.renderer.scrollToLine(first, false, false);
      scheduleAnnotationRefresh();
      updateShowing(visible.length);
    }, 400);
  }

  function stopFollowing() {
    if (!isFollowing) return;
    isFollowing = false;
    hidePill();
    if (quietTimer) clearTimeout(quietTimer);
    if (annTimer) clearTimeout(annTimer);
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }
    const $followBtn = $("#follow-logs");
    $followBtn.find("i").removeClass("bx-stop").addClass("bx-play");
    $followBtn.find("span").text(t("button.follow", "Follow"));
    $followBtn.attr("aria-label", t("button.follow", "Follow"));
    $followBtn
      .removeClass("btn-outline-danger")
      .addClass("btn-outline-primary");
  }

  $("#follow-logs").click(function () {
    if (isFollowing) stopFollowing();
    else startFollowing();
  });

  $("#copy-logs").click(function () {
    const $this = $(this);
    editor.selectAll();
    editor.focus();
    navigator.clipboard.writeText(editor.getSelectedText()).catch(() => {});
    $this.attr("data-bs-original-title", "Copied!").tooltip("show");
    setTimeout(() => {
      $this.tooltip("hide").attr("data-bs-original-title", "");
    }, 2000);
  });

  $("#dark-mode-toggle").on("change", function () {
    setTimeout(() => {
      theme = $("#theme").val();
      setEditorTheme();
    }, 30);
  });

  // Clean up EventSource when the page goes away. pagehide covers bfcache /
  // mobile cases where beforeunload doesn't fire.
  $(window).on("beforeunload pagehide", function () {
    if (eventSource) eventSource.close();
  });
});
