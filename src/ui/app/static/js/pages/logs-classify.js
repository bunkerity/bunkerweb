// Shared log-line classification + timestamp helpers.
//
// Extracted from logs.js so the ACE viewer (logs.js) and the live-tail
// dashboard (logs-live.js) classify lines with the SAME rules. The
// classification is security-sensitive — it inspects only the structured
// prefix before the first quote so an attacker-supplied "[ERROR]" in a URL /
// user-agent can't spoof a line's level. Keep that guard intact.

// ---- Level detection (mirrors the ACE mode's matchers, all formats) ----
export const LEVELS = [
  { key: "critical", cls: "danger", icon: "bx-error", label: "Critical" },
  { key: "error", cls: "danger", icon: "bx-error-circle", label: "Error" },
  { key: "warning", cls: "warning", icon: "bx-error", label: "Warning" },
  { key: "notice", cls: "info", icon: "bx-info-circle", label: "Notice" },
  { key: "info", cls: "info", icon: "bx-info-circle", label: "Info" },
  { key: "debug", cls: "secondary", icon: "bx-bug", label: "Debug" },
];
// Emoji alternatives are written as \u{...} escapes (with the /u flag) rather
// than literal glyphs — behaviorally identical matching, but keeps this shared
// module free of literal emoji (repo lint forbids emoji-as-icons in copy).
export const LEVEL_RES = {
  critical: /\[\s*(?:CRITICAL|\u{1F6A8})\s*\]|:CRITICAL:|\s\[emerg\]\s/u,
  error: /\[\s*(?:ERROR|\u{274C})\s*\]|:ERROR:|\s\[(?:error|alert|crit)\]\s/u,
  warning: /\[\s*(?:WARNING|\u{26A0}\u{FE0F}?)\s*\]|:WARNING:|\s\[warn\]\s/u,
  notice: /\s\[notice\]\s/u,
  info: /\[\s*(?:INFO|\u{2139}\u{FE0F}?)\s*\]|:INFO:/u,
  debug: /\[\s*(?:DEBUG|\u{1F41B})\s*\]|:DEBUG:/u,
};
export function levelOf(line) {
  // Only inspect the structured prefix (before the first quote). Access-log
  // request / referer / user-agent fields are quoted and attacker-controlled,
  // so a "[ERROR]" injected into a URL must not classify the line as an error.
  const q = line.indexOf('"');
  const head = q === -1 ? line : line.slice(0, q);
  for (const L of LEVELS) if (LEVEL_RES[L.key].test(head)) return L.key;
  return null;
}
export function classifyLine(line) {
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
export function fmtLocal(d) {
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
export function localizeLine(line) {
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

// Epoch-ms of a line's leading timestamp (any of the three formats), or NaN.
// Used to timestamp-sort the multi-source backfill before live tailing.
export function parseLeadingTs(line) {
  let m = TS_BRACKET.exec(line);
  if (m) {
    const tz = m[3].slice(0, 3) + ":" + m[3].slice(3);
    return new Date(m[1] + "T" + m[2] + tz).getTime();
  }
  m = TS_PLAIN.exec(line);
  if (m) return new Date(m[1] + "T" + m[2] + "Z").getTime();
  m = TS_NGINX.exec(line);
  if (m)
    return new Date(
      m[1] + "-" + m[2] + "-" + m[3] + "T" + m[4] + "Z",
    ).getTime();
  return NaN;
}
