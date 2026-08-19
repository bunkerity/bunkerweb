function getAlpha2(lang) {
  if (!lang) return "en";
  return lang.split("-")[0].toLowerCase();
}

// The message catalog is assigned by `/locales/<lang>.js`, a plain script loaded just before this
// one, so it is a parse-time constant rather than something to wait for. That is the whole point
// of the native-i18n migration: templates arrive translated from the server, and the handful of
// strings JavaScript still builds are resolved here, synchronously, with no DOM pass afterwards.
const catalog = window.BW_I18N || {};
const currentLanguage = window.BW_LANG || "en";

// Escape exactly what i18next escaped: interpolated values, never the catalog string itself.
// Several call sites feed service names and field names through here and drop the result into
// HTML, so dropping the escaping would be a stored-XSS hole rather than a cosmetic change.
const htmlEntities = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;",
};

function escapeValue(value) {
  return String(value).replace(
    /[&<>"']/g,
    (character) => htmlEntities[character],
  );
}

// i18next's own three signatures, because ~40 call sites use all of them:
//   t("some.key")
//   t("some.key", "fallback")            /  t("some.key", { count: 3, defaultValue: "…" })
//   t("some.key", "fallback {{n}}", { n: 3 })
//
// The three-argument form is the one that is easy to drop and expensive to miss: it is how the
// DataTables `infoCallback` passes start/end/total, and without it the footer of every table reads
// "Showing {{start}} to {{end}} of {{total}}" — placeholders intact, no error anywhere.
//
// Missing keys fall back to `defaultValue` and then to the key itself, which is what i18next did
// and what gettext does server-side — a key rendered raw is the signal that it is missing.
function t(key, defaultValue, options) {
  const settings =
    typeof defaultValue === "string"
      ? { defaultValue: defaultValue, ...(options || {}) }
      : defaultValue || {};
  const value = String(key)
    .split(".")
    .reduce((node, part) => (node == null ? undefined : node[part]), catalog);
  const message =
    typeof value === "string"
      ? value
      : settings.defaultValue !== undefined
        ? settings.defaultValue
        : key;
  const escape =
    !settings.interpolation || settings.interpolation.escapeValue !== false;

  return String(message).replace(/{{\s*([\w.]+)\s*}}/g, (placeholder, name) =>
    settings[name] === undefined
      ? placeholder
      : escape
        ? escapeValue(settings[name])
        : String(settings[name]),
  );
}

// Plugin front-ends call `i18next.t` directly (core `letsencrypt` does, and external plugins are
// free to), and a dozen call sites here still guard on `i18next.isInitialized` or subscribe to
// `languageChanged`. The library is gone; this is the surface they used.
//
// `isInitialized` is true because it now always is — the catalog is loaded before any of this
// runs, which is the whole point. The event methods are accepted and dropped: a language switch
// reloads the page, so nothing can fire between one language and the next.
window.t = t;
window.i18next = {
  t: t,
  language: currentLanguage,
  isInitialized: true,
  exists: (key) => t(key, { defaultValue: "\u0000" }) !== "\u0000",
  changeLanguage: (lang) => changeLanguage(lang),
  on: () => {},
  off: () => {},
};

// Translate `data-i18n` markup that JavaScript built.
//
// This used to run over the whole document on every page load, because the page arrived in
// English and something had to rewrite it. It does not run on load any more: templates are
// rendered translated by the server, and `t()` resolves everything else as it is built.
//
// What is left is markup a page script assembles from a string — DataTables column titles, the
// template editor's panes, the workflow canvas. Those have no server render to attach to, so they
// still carry the key and still ask for it explicitly, over the subtree they just created.
const explicitI18nAttributes = {
  "data-i18n-aria-label": "aria-label",
  "data-i18n-title": "title",
  "data-i18n-placeholder": "placeholder",
  "data-i18n-empty-text": "data-empty-text",
};

function applyTranslations(root) {
  const selector = ["[data-i18n]"]
    .concat(
      Object.keys(explicitI18nAttributes).map((attribute) => `[${attribute}]`),
    )
    .join(", ");
  const scope = root ? $(root) : $(document);

  scope
    .find(selector)
    .addBack(selector)
    .each(function () {
      const element = $(this);
      let options = {};
      const optionsAttr = element.attr("data-i18n-options");
      if (optionsAttr) {
        try {
          options = JSON.parse(optionsAttr);
        } catch (e) {
          console.error("Error parsing data-i18n-options:", e, optionsAttr);
        }
      }
      // Never escape here: the value is written with `.text()` or into an attribute, both of which
      // escape on their own, and double-escaping turns an apostrophe into `&#39;` on the page.
      const translate = (key) =>
        t(key, { ...options, interpolation: { escapeValue: false } });

      Object.entries(explicitI18nAttributes).forEach(
        ([keyAttribute, targetAttribute]) => {
          const attributeKey = element.attr(keyAttribute);
          if (attributeKey)
            element.attr(targetAttribute, translate(attributeKey));
        },
      );

      const key = element.attr("data-i18n");
      if (!key) return;
      const translation = translate(key);
      const explicitTarget = element.attr("data-i18n-attr");
      if (explicitTarget === "text") {
        element.text(translation);
      } else if (explicitTarget) {
        element.attr(explicitTarget, translation);
      } else if (element.is("[placeholder]")) {
        element.attr("placeholder", translation);
      } else if (element.is("[title]")) {
        element.attr("title", translation);
      } else if (element.is("[data-bs-original-title]")) {
        element.attr("data-bs-original-title", translation);
      } else if (element.is("[aria-label]")) {
        element.attr("aria-label", translation);
      } else {
        element.text(translation);
        if (element.parent().is("span.dtsp-name[title]")) {
          element.parent().attr("title", ` ${translation}`);
        }
      }
    });

  // Bootstrap caches a tooltip's content at construction, so an already-built one keeps showing
  // the untranslated title until it is told otherwise.
  if (typeof bootstrap !== "undefined" && bootstrap.Tooltip) {
    scope.find('[data-bs-toggle="tooltip"]').each(function () {
      const instance = bootstrap.Tooltip.getInstance(this);
      if (instance && instance.setContent) {
        instance.setContent({
          ".tooltip-inner": $(this).attr("data-bs-original-title"),
        });
      }
    });
  }
}

window.applyTranslations = applyTranslations;

// Parse supported languages from hidden textarea
let supportedLanguages = [];
try {
  const textarea = document.getElementById("supported-languages-json");
  if (textarea) {
    supportedLanguages = JSON.parse(textarea.value);
  }
} catch (e) {
  console.error("Failed to parse supported languages JSON:", e);
}
const supportedLngs = supportedLanguages.map((l) => l.code);
const flagCodeMap = Object.fromEntries(
  supportedLanguages.map((l) => [l.code, l.flag.replace(".svg", "")]),
);
// Update langNames and add langEnglishNames for search
const langNames = Object.fromEntries(
  supportedLanguages.map((l) => [l.code, l.name]),
);
const langEnglishNames = Object.fromEntries(
  supportedLanguages.map((l) => [l.code, l.english_name || l.name]),
);

// Update the language selector dropdown to show current language
function updateLanguageSelector(lang) {
  const alpha2 = getAlpha2(lang);
  const flagCode = flagCodeMap[alpha2] || flagCodeMap["en"] || "us";
  const $flagSelector = $("#current-lang-flag");
  if (!$flagSelector.length) {
    return;
  }
  const flagSrc = $flagSelector
    .attr("src")
    .replace(/\/[a-z]{2}\.svg$/, `/${flagCode}.svg`);
  $flagSelector.attr("src", flagSrc);
  $("#current-lang-text").text(
    langNames[alpha2] || langNames["en"] || "English",
  );
  $("#language-dropdown-menu .lang-option").removeClass("active");
  $(
    "#language-dropdown-menu .lang-option[data-lang='" + alpha2 + "']",
  ).addClass("active");
}

// Tell the server which language to render in, and report whether it heard.
//
// Every page is rendered server-side now, so this is the only channel through which the server
// learns the choice — including on the setup wizard, which used to opt out on the grounds that it
// had no session to carry one. It does: `/set_language` needs no account and no writable
// database, only a session, and refusing it there left the wizard permanently in one language.
function saveLanguage(rootUrl, language) {
  const csrfToken = $("#csrf_token").val();
  if (!csrfToken) {
    console.warn(
      "CSRF token not found, cannot save language preference to server",
    );
    return Promise.resolve(false);
  }

  const data = new FormData();
  data.append("language", language);
  data.append("csrf_token", csrfToken);

  return fetch(rootUrl, {
    method: "POST",
    body: data,
  })
    .then((response) => {
      if (!response.ok) {
        throw new Error("Network response was not ok");
      }
      return true;
    })
    .catch((error) => {
      console.error("Error saving language preference to server:", error);
      return false;
    });
}

// Debounce function to prevent multiple rapid requests
function debounce(func, wait) {
  let timeout;
  return function (...args) {
    const context = this;
    clearTimeout(timeout);
    timeout = setTimeout(() => func.apply(context, args), wait);
  };
}

// Function to update documentation links based on language
function updateDocumentationLinks(lang) {
  const alpha2 = getAlpha2(lang);
  const supportedDocLangs = ["fr", "de", "es", "zh"];
  const langPrefix = supportedDocLangs.includes(alpha2) ? `/${alpha2}` : "";

  // Get BunkerWeb version from a global variable or data attribute
  const bwVersion =
    window.bw_version || $("body").data("bw-version") || "latest";

  // Update all documentation links
  $(".docs-link").each(function () {
    const $link = $(this);
    const endpoint = $link.data("endpoint") || "";
    const fragment = $link.data("fragment") || "";
    const newUrl = `https://docs.bunkerweb.io/${bwVersion}${langPrefix}${endpoint}/?utm_campaign=self&utm_source=ui${fragment}`;
    $link.attr("href", newUrl);
  });
}

// Language switch helper.
//
// Tells the server, then reloads. There is no client-side half left to switch: the page, its
// chrome and its catalog are all rendered or served for one locale, so the reload *is* the
// switch. A dropdown click can afford it.
function changeLanguage(lang) {
  const alpha2 = getAlpha2(lang);

  // Derived from the home link where there is one; the setup wizard renders no navigation, so
  // it falls back to the absolute path.
  const homePath = $("#home-path").val();
  const rootUrl = homePath
    ? homePath.trim().replace(/\/home$/, "/set_language")
    : "/set_language";

  saveLanguage(rootUrl, alpha2).then((recorded) => {
    if (recorded) window.location.reload();
  });
}

// Helper to update DataTable language and translations for a given table
function updateTableLanguageAndTranslations(table) {
  if (!table || !window.configureI18n) return;
  const tableId = $(table.table().node()).attr("id");
  const tableName = tableId || "items";
  const languageSettings = configureI18n(t, tableName);
  table.context[0].oLanguage = $.extend(
    true,
    table.context[0].oLanguage || {},
    languageSettings,
  );
}

// Helper function to update translations for filter elements
function updateFilterTranslations() {
  $("input.dtsp-paneInputButton.search:not([data-i18n])").each(function () {
    const $this = $(this);
    const placeholder = $this.attr("placeholder") || "";
    const i18nSuffix = placeholder.toLowerCase().replace(/\s+/g, "_").trim();

    if (i18nSuffix) $this.attr("data-i18n", `searchpane.${i18nSuffix}`);
  });

  $(".dtsp-name [data-i18n], .dtsp-paneInputButton[data-i18n]").each(
    function () {
      const element = $(this);
      const key = element.attr("data-i18n");
      if (!key) return;
      let options = {};
      const optionsAttr = element.attr("data-i18n-options");
      if (optionsAttr) {
        try {
          options = JSON.parse(optionsAttr.replace(/'/g, '"'));
        } catch (e) {
          console.error(
            `Error parsing data-i18n-options for key "${key}":`,
            e,
            optionsAttr,
          );
          return;
        }
      }
      const translation = t(key, options);
      if (element.is("input")) {
        element.attr("placeholder", translation);
      } else {
        element.text(translation);
      }
    },
  );
}

$(document).ready(function () {
  // What the i18next callback used to do once its catalog had arrived. The catalog is already
  // here, so this is the whole of it: no init, no ready flag, no re-translation on switch.
  updateLanguageSelector(currentLanguage);
  updateDocumentationLinks(currentLanguage);
  $("[name='language']").val(currentLanguage);
  $("#newsletter-locale").val(currentLanguage);

  // Handle language selection clicks
  $(document).on("click", ".lang-option", function (e) {
    e.preventDefault();
    changeLanguage($(this).data("lang"));
  });

  // Handle DataTables collection button translations
  $(document).on("click", ".buttons-collection", function () {
    const collection = $(this)
      .closest(".btn-group")
      .find(".dt-button-collection");

    collection.find("[data-i18n]").each(function () {
      const element = $(this);
      const key = element.attr("data-i18n");
      // `[data-i18n]` matches an *empty* attribute too, and DataTables' `colvis` writes one:
      // `columnText` emits `data-i18n="${i18nKey || ""}"`, and since the table headers are
      // rendered translated there is no key on them to read back. Without this guard, opening the
      // Columns dropdown replaced every label with `t("")` — an empty string — leaving the six
      // ordinals ("4.", "5.", ...) and nothing else. `applyTranslations` already guards this way.
      if (!key) return;
      let options = {};
      const optionsAttr = element.attr("data-i18n-options");

      if (optionsAttr) {
        try {
          options = JSON.parse(optionsAttr.replace(/'/g, '"'));
        } catch (e) {
          console.error(
            `Error parsing data-i18n-options for key "${key}":`,
            e,
            optionsAttr,
          );
          return;
        }
      }

      element.text(t(key, options));
    });
  });

  // Handle all relevant DataTables events to ensure language is applied and translations are updated
  $(document).on(
    ["draw.dt", "init.dt", "processing.dt"].join(" "),
    function (e, settings) {
      if (settings && settings.oInstance && window.configureI18n) {
        const table = new $.fn.dataTable.Api(settings);
        updateTableLanguageAndTranslations(table);
      }
      updateFilterTranslations();
    },
  );

  $(document).on("click", ".toggle-filters", updateFilterTranslations);

  // Prevent scroll propagation to the menu
  $("#language-dropdown-menu").on("wheel touchmove", function (e) {
    e.stopPropagation();
  });

  // Language selector search logic
  $(document).on(
    "input",
    "#language-search",
    throttle(function () {
      const searchValue = $(this).val().toLowerCase().trim();
      let visibleItems = 0;
      $("#language-dropdown-menu li.nav-item").each(function () {
        const $item = $(this);
        const langCode = $item.data("lang");
        const englishName = langEnglishNames[langCode]
          ? langEnglishNames[langCode].toLowerCase()
          : "";
        const localizedName = langNames[langCode]
          ? langNames[langCode].toLowerCase()
          : "";
        const matches =
          englishName.includes(searchValue) ||
          localizedName.includes(searchValue);
        $item.toggle(matches);
        if (matches) visibleItems++;
      });
      if (visibleItems === 0) {
        if ($("#language-dropdown-menu .no-language-items").length === 0) {
          $("#language-dropdown-menu").append(
            `<li class="no-language-items dropdown-item text-muted">${t(
              "status.no_item",
            )}</li>`,
          );
        }
      } else {
        $("#language-dropdown-menu .no-language-items").remove();
      }
    }, 150),
  );
});
