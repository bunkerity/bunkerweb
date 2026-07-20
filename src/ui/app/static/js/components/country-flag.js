/**
 * Shared "country cell" renderer -- a decorative flag (ISO 3166-1 alpha-2) + the localized
 * country name + a Bootstrap tooltip. Single source of truth for the markup that
 * components/country-flag.html's `country_flag()` macro renders server-side and that
 * static/js/pages/bans.js + static/js/pages/reports.js render client-side inside their
 * DataTables `render()` callbacks (rows arrive over AJAX, so there is no server-rendered
 * <tr> the macro could slot into -- these two pages needed a JS-side renderer either way).
 * Both pages previously hand-built this cell inline, in two subtly different shapes
 * (see components/country-flag.html's doc comment for the diff); they now both call
 * `BWCountryFlag.html()` here instead, and share this file's `updateTooltips()` in place of
 * their own near-identical `updateCountryTooltips()` copies.
 *
 * `flagBase` MUST stay same-origin ("/static/img/flags" by default) -- the UI's CSP
 * img-src (main.py's set_security_headers) does not allowlist flagcdn.com or any other
 * remote flag host, so pointing this elsewhere silently blocks every flag image.
 *
 * Exposes window.BWCountryFlag:
 *   config              -- { flagBase, flagHeight } defaults, overridable per-call via opts.
 *   isNA(code)          -- true for "", "unknown", "local", "n/a", "na", "zz", "-", "—", or
 *                          anything that isn't exactly 2 letters.
 *   normalize(code)     -- upper-cased 2-letter ISO code, or "ZZ" for the NA set.
 *   srcFor(code, opts)  -- the flag <img> src for a code.
 *   html(code, opts)    -- the full cell markup (string) -- pass this straight into a
 *                          DataTables column's render() callback.
 *   updateTooltips()    -- re-translates every rendered `[data-country]` cell's tooltip
 *                          title via i18next and re-inits every Bootstrap tooltip on the
 *                          page. Call after a DataTables redraw / language switch (same spot
 *                          bans.js/reports.js already called their own copy from).
 *
 * Not covered: DataTables' `type` argument (sort/filter/type vs "display") -- like the
 * inline code this replaces, `html()` always returns the display markup regardless of type,
 * so sorting/filtering this column keeps relying on the underlying raw `data` value already
 * being sortable/filterable text (unchanged pre-existing behaviour, not this task's scope).
 */
(function () {
  "use strict";
  if (window.BWCountryFlag) return;

  var config = {
    flagBase: "/static/img/flags",
    flagHeight: 17,
  };

  // Values that mean "no country could be resolved" -- matches the not-applicable checks
  // bans.js/reports.js already ran inline, plus a couple of extra defensive sentinels.
  var NA_SET = {
    "": 1,
    UNKNOWN: 1,
    LOCAL: 1,
    "N/A": 1,
    NA: 1,
    ZZ: 1,
    "-": 1,
    "—": 1,
  };

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function isNA(code) {
    if (code == null) return true;
    var c = String(code).trim().toUpperCase();
    if (NA_SET[c]) return true;
    return !/^[A-Z]{2}$/.test(c);
  }

  function normalize(code) {
    return isNA(code) ? "ZZ" : String(code).trim().toUpperCase();
  }

  function srcFor(code, opts) {
    opts = opts || {};
    var base = (opts.flagBase || config.flagBase).replace(/\/+$/, "");
    var flagCode = isNA(code) ? "zz" : normalize(code).toLowerCase();
    return base + "/" + flagCode + ".svg";
  }

  // The full country-cell markup -- mirrors components/country-flag.html's `country_flag()`
  // macro. opts: name, showLabel, tooltip, height, classes, flagBase (see file doc comment).
  function html(code, opts) {
    opts = opts || {};
    var na = isNA(code);
    var iso = normalize(code);
    var i18nKey = na ? "country.not_applicable" : "country." + iso;
    var label = opts.name != null ? opts.name : na ? "N/A" : iso;
    var dataCountry = na ? "unknown" : iso;
    var height = opts.height || config.flagHeight;
    var showLabel = opts.showLabel !== false;
    var tooltip = opts.tooltip !== false;
    var classes =
      "d-inline-flex align-items-center" +
      (opts.classes ? " " + opts.classes : "");

    var attrs = ' class="' + esc(classes) + '"';
    attrs += ' data-country="' + esc(dataCountry) + '"';
    if (tooltip) {
      attrs +=
        ' data-bs-toggle="tooltip" data-bs-original-title="' + esc(label) + '"';
    }

    var img =
      '<img src="' +
      esc(srcFor(code, opts)) +
      '" class="border border-1 p-0 me-1" height="' +
      height +
      '" loading="lazy" alt="" aria-hidden="true" />';

    var nameSpan =
      "<span" +
      (showLabel ? "" : ' class="visually-hidden"') +
      ' data-i18n="' +
      i18nKey +
      '">' +
      esc(label) +
      "</span>";

    return "<span" + attrs + ">" + img + nameSpan + "</span>";
  }

  // Ported as-is from bans.js/reports.js's identical `updateCountryTooltips()` -- retranslates
  // every rendered [data-country] cell's tooltip title via i18next, then re-inits every
  // Bootstrap tooltip on the page (not scoped to country cells -- matches the original, which
  // relied on this same call also picking up other freshly-drawn tooltip triggers).
  function updateTooltips() {
    var t =
      typeof i18next !== "undefined"
        ? i18next.t
        : function (key, fallback) {
            return fallback || key;
          };

    $("[data-country]").each(function () {
      var $elem = $(this);
      var code = $elem.attr("data-country");
      var i18nKey =
        code === "unknown" ? "country.not_applicable" : "country." + code;
      var countryName = t(i18nKey, "Unknown");
      if (countryName && countryName !== "country.not_applicable") {
        $elem.attr("data-bs-original-title", countryName);
      }
    });
    $('[data-bs-toggle="tooltip"]').tooltip("dispose").tooltip();
  }

  window.BWCountryFlag = {
    config: config,
    isNA: isNA,
    normalize: normalize,
    srcFor: srcFor,
    html: html,
    updateTooltips: updateTooltips,
  };
})();
