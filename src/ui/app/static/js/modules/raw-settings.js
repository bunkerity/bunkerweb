// Parse the same known-key boundaries for saving, draft actions and highlighting.
export function parseRawSettings(text, { isKnownSettingKey, isMultilineKey }) {
  const entries = [];
  let current = null;
  const flush = () => {
    if (!current) return;
    if (!isMultilineKey(current.key)) current.value = current.value.trim();
    entries.push(current);
    current = null;
  };
  String(text || "")
    .replace(/\r\n?/g, "\n")
    .split("\n")
    .forEach((line, row) => {
      const eq = line.indexOf("=");
      const key = eq < 0 ? "" : line.slice(0, eq).trim();
      if (isKnownSettingKey(key)) {
        flush();
        current = {
          key,
          value: line.slice(eq + 1),
          start: row,
          end: row,
        };
      } else if (current && isMultilineKey(current.key)) {
        current.value += "\n" + line;
        current.end = row;
      }
    });
  flush();
  return entries;
}
