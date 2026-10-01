// Localizes every flatpickr instance in the UI. No l10n bundle is vendored, so the month and weekday
// names and the first day of the week come from the browser's own `Intl` data for the UI language.
// flatpickr has no RTL support of its own: `options().onReady` tags the calendar with `bw-rtl`, which
// overrides.css mirrors (direction, month arrows).
// Usage: flatpickr(el, { ...window.bwFlatpickr.options(), mode: "range" })
window.bwFlatpickr = (() => {
  // 2024-01-01 is a Monday and 2024-01-07 a Sunday, so the loops walk a full month and a full week.
  const names = (lang, unit, style, count, date) =>
    Array.from({ length: count }, (_, i) =>
      new Intl.DateTimeFormat(lang, { [unit]: style }).format(date(i)),
    );

  const firstDayOfWeek = (lang) => {
    try {
      const locale = new Intl.Locale(lang);
      const info = locale.getWeekInfo ? locale.getWeekInfo() : locale.weekInfo;
      // Intl: 1 = Monday ... 7 = Sunday; flatpickr: 0 = Sunday.
      return info && info.firstDay ? info.firstDay % 7 : 0;
    } catch (e) {
      return 0;
    }
  };

  // `window.BW_LANG` is the UI's own language code (`br`, `tw`...), which `Intl` reads as Breton and Twi.
  // `<html lang>` carries the resolved BCP-47 tag the server rendered (`pt-BR`, `zh-Hant`).
  const locale = (lang = document.documentElement.lang || "en") => ({
    months: {
      longhand: names(lang, "month", "long", 12, (m) => new Date(2024, m, 1)),
      shorthand: names(lang, "month", "short", 12, (m) => new Date(2024, m, 1)),
    },
    weekdays: {
      longhand: names(
        lang,
        "weekday",
        "long",
        7,
        (d) => new Date(2024, 0, 7 + d),
      ),
      shorthand: names(
        lang,
        "weekday",
        "short",
        7,
        (d) => new Date(2024, 0, 7 + d),
      ),
    },
    firstDayOfWeek: firstDayOfWeek(lang),
  });

  const options = (lang) => ({
    locale: locale(lang),
    onReady: [
      (_dates, _value, instance) => {
        if (document.documentElement.dir === "rtl") {
          instance.calendarContainer.classList.add("bw-rtl");
        }
      },
    ],
  });

  return { locale, options };
})();
