// Live multi-source log dashboard (the /logs landing when no file is selected).
// One merged EventSource → /logs/stream/multi. All DOM is built with
// textContent (log lines carry attacker-influenced content — never innerHTML).
import { levelOf, classifyLine, parseLeadingTs } from "./logs-classify.js";

(function () {
  const stream = document.getElementById("log-stream");
  if (!stream) return; // ACE viewer mode (a file is selected) — nothing to do.

  const t =
    typeof i18next !== "undefined"
      ? i18next.t
      : (key, fallback, options) => {
          let translated = fallback || key;
          if (options) {
            for (const k in options) {
              translated = translated.replace(`{{${k}}}`, options[k]);
            }
          }
          return translated;
        };

  // Keep the browser buffer aligned with the server tail cap.
  const MAX_LOG_LINES = 10000;
  const sources = (stream.dataset.sources || "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);

  // Model: {text, ts} records. Backfill is timestamp-sorted once; live appends
  // land on the end in arrival order.
  let lines = [];
  let levelFilter = "all"; // all | errors | security
  let grepQuery = "";
  let paused = false;
  let eventSource = null;

  // Whole line is tinted by its detected level (kit .lg-* palette). levelOf's
  // pre-quote-prefix guard means an injected "[ERROR]" in a URL can't spoof it.
  function levelClass(text) {
    const lv = levelOf(text);
    if (lv === "critical" || lv === "error") return "lg-err";
    if (lv === "warning") return "lg-warn";
    if (lv === "notice" || lv === "info") return "lg-info";
    if (lv === "debug") return "lg-dim";
    return "";
  }

  function passesFilter(text) {
    if (levelFilter !== "all") {
      const sev = classifyLine(text); // "error" | "warning" | null
      if (levelFilter === "security" && sev !== "error") return false;
      if (levelFilter === "errors" && sev === null) return false;
    }
    if (grepQuery && !text.toLowerCase().includes(grepQuery)) return false;
    return true;
  }

  function lineEl(text) {
    const div = document.createElement("div");
    const cls = levelClass(text);
    if (cls) div.className = cls;
    div.textContent = text; // NEVER innerHTML.
    return div;
  }

  function atBottom() {
    return stream.scrollHeight - stream.scrollTop - stream.clientHeight < 40;
  }
  function toBottom() {
    stream.scrollTop = stream.scrollHeight;
  }

  function splitLines(content) {
    if (!content) return [];
    const parts = content.split("\n");
    if (parts[parts.length - 1] === "") parts.pop();
    return parts;
  }

  // Full rebuild — backfill flush, level change, grep change.
  function renderAll() {
    const frag = document.createDocumentFragment();
    for (const rec of lines) {
      if (passesFilter(rec.text)) frag.appendChild(lineEl(rec.text));
    }
    stream.replaceChildren(frag);
    toBottom();
  }

  // Append one record; keep model + DOM within the line cap.
  function pushRecord(text, wasAtBottom) {
    lines.push({ text, ts: 0 });
    if (lines.length > MAX_LOG_LINES) {
      lines.splice(0, lines.length - MAX_LOG_LINES);
    }
    if (passesFilter(text)) {
      stream.appendChild(lineEl(text));
      while (stream.childElementCount > MAX_LOG_LINES) {
        stream.removeChild(stream.firstElementChild);
      }
      if (wasAtBottom) toBottom();
    }
  }

  // ---- Backfill: one `refresh` frame per source at stream start ----
  let backfill = new Map();
  let pending = new Set(sources);
  let backfilled = false;
  let backfillTimer = null;

  function resetBackfill() {
    if (backfillTimer) clearTimeout(backfillTimer);
    backfill = new Map();
    pending = new Set(sources);
    backfilled = false;
    lines = [];
    stream.replaceChildren();
    // Flush even if a source was dropped server-side or logs are quiet.
    backfillTimer = setTimeout(() => {
      if (!backfilled) flushBackfill();
    }, 1500);
  }

  function flushBackfill() {
    if (backfillTimer) {
      clearTimeout(backfillTimer);
      backfillTimer = null;
    }
    const all = [];
    for (const src of sources) {
      let lastTs = 0;
      for (const text of splitLines(backfill.get(src) || "")) {
        let ts = parseLeadingTs(text);
        // A continuation line (no leading timestamp) inherits its header's ts
        // so it stays grouped through the sort.
        if (isNaN(ts)) ts = lastTs;
        else lastTs = ts;
        all.push({ text, ts });
      }
    }
    all.sort((a, b) => a.ts - b.ts); // stable: equal ts keeps insertion order
    if (all.length > MAX_LOG_LINES) all.splice(0, all.length - MAX_LOG_LINES);
    lines = all;
    backfill = new Map();
    backfilled = true;
    renderAll();
  }

  function onFrame(data) {
    if (data.type === "error") return; // over-limit / server error — leave view as-is
    if (data.type === "refresh" && !backfilled) {
      backfill.set(data.source, data.content || "");
      pending.delete(data.source);
      if (!pending.size) flushBackfill();
      return;
    }
    // append / rotated / stray-refresh — live, arrival order. Drain any pending
    // backfill first so the sorted history renders before live lines pile on.
    if (!backfilled) flushBackfill();
    const wasAtBottom = atBottom();
    for (const text of splitLines(data.content)) pushRecord(text, wasAtBottom);
  }

  function connect() {
    if (!sources.length) return;
    const base = window.location.pathname.replace(/\/$/, "");
    const url = `${base}/stream/multi?sources=${encodeURIComponent(sources.join(","))}`;
    eventSource = new EventSource(url);
    eventSource.onopen = resetBackfill; // fresh (re)connect => re-backfill
    eventSource.onmessage = (event) => {
      try {
        onFrame(JSON.parse(event.data));
      } catch (e) {
        /* ignore a malformed frame; wait for the next */
      }
    };
    eventSource.onerror = () => {
      // EventSource auto-reconnects on transient drops; only surface a dead
      // stream (CLOSED) in the UI.
      if (eventSource && eventSource.readyState === EventSource.CLOSED) {
        eventSource = null;
        if (!paused) setPause(true);
      }
    };
  }

  // ---- Controls ----
  const pauseBtn = document.getElementById("log-pause");
  function setPause(state) {
    paused = state;
    if (paused) {
      if (eventSource) {
        eventSource.close();
        eventSource = null;
      }
    } else if (!eventSource) {
      connect();
    }
    if (pauseBtn) {
      const icon = pauseBtn.querySelector("i");
      const label = pauseBtn.querySelector(".log-pause-label");
      if (icon) icon.className = "bx " + (paused ? "bx-play" : "bx-pause");
      if (label) {
        label.textContent = paused
          ? t("logs.resume", "Resume")
          : t("logs.pause", "Pause");
      }
      pauseBtn.setAttribute("aria-pressed", String(paused));
    }
  }
  if (pauseBtn) pauseBtn.addEventListener("click", () => setPause(!paused));

  const levelSel = document.getElementById("log-level-filter");
  if (levelSel) {
    levelSel.addEventListener("change", () => {
      levelFilter = levelSel.value;
      renderAll();
    });
  }

  const grepInput = document.getElementById("log-grep");
  if (grepInput) {
    let grepTimer = null;
    grepInput.addEventListener("input", () => {
      if (grepTimer) clearTimeout(grepTimer);
      grepTimer = setTimeout(() => {
        grepQuery = (grepInput.value || "").trim().toLowerCase();
        renderAll();
      }, 150);
    });
  }

  // 3-state Expand (ported from the design kit operate.js).
  const expandBtn = document.getElementById("log-expand");
  if (expandBtn) {
    let expandState = 0; // 0 default, 1 tall, 2 full
    expandBtn.addEventListener("click", () => {
      expandState = (expandState + 1) % 3;
      stream.classList.toggle("tall", expandState === 1);
      stream.classList.toggle("fullview", expandState === 2);
      const icon =
        expandState === 0
          ? "bx-expand"
          : expandState === 1
            ? "bx-expand-alt"
            : "bx-collapse";
      const lbl =
        expandState === 0
          ? t("logs.expand", "Expand")
          : expandState === 1
            ? t("logs.taller", "Taller")
            : t("logs.collapse", "Collapse");
      const i = document.createElement("i");
      i.className = "bx " + icon;
      i.setAttribute("aria-hidden", "true");
      expandBtn.replaceChildren(i, document.createTextNode(" " + lbl));
      if (expandState !== 0) toBottom();
    });
  }

  const countEl = document.getElementById("log-source-count");
  if (countEl) {
    countEl.textContent = t(
      "logs.tailing_sources",
      "Tailing · {{count}} sources",
      {
        count: sources.length,
      },
    );
  }

  connect();

  const teardown = () => {
    if (eventSource) eventSource.close();
  };
  window.addEventListener("beforeunload", teardown);
  window.addEventListener("pagehide", teardown);
})();
