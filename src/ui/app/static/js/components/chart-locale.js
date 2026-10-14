// Formats the dates and numbers of every chart (axis labels, tooltips) in the UI language. ApexCharts' own English month
// names and `toLocale*String([])` both follow the browser, not the language the user picked.
// `window.BW_LANG` is the UI's own code (`br`, `tw`), which `Intl` reads as Breton and Twi: use the resolved
// BCP-47 tag the server renders in `<html lang>`, like `flatpickr-locale.js`.
// Usage: window.bwChartLocale.format(dateOrEpochMs, { hour: "2-digit" }); window.bwChartLocale.number(1234.5)
window.bwChartLocale = (() => {
  const DEFAULT = {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  };
  const cache = new Map();

  const formatter = (Format, options) => {
    const lang = document.documentElement.lang || "en";
    const key = Format.name + lang + JSON.stringify(options);
    if (!cache.has(key)) cache.set(key, new Format(lang, options));
    return cache.get(key);
  };

  const format = (date, options = DEFAULT) =>
    formatter(Intl.DateTimeFormat, options).format(date);
  const number = (value, options) =>
    formatter(Intl.NumberFormat, options).format(value);

  return { format, number };
})();
