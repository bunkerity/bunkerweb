function getAlpha2(lang) {
  if (!lang) return "en";
  return lang.split("-")[0].toLowerCase();
}

// Apply translations to elements with [data-i18n] attribute
function applyTranslations() {
  const elements = $("[data-i18n]");
  elements.each(function () {
    const element = $(this);
    const key = element.attr("data-i18n");
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
      }
    }
    const translation = i18next.t(key, options);
    if (element.is("[placeholder]")) {
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
  // Re-initialize Bootstrap tooltips if present
  if (typeof bootstrap !== "undefined" && bootstrap.Tooltip) {
    $('[data-bs-toggle="tooltip"]').each(function () {
      const tooltipTriggerEl = this;
      const instance = bootstrap.Tooltip.getInstance(tooltipTriggerEl);
      if (instance) {
        instance.setContent &&
          instance.setContent({
            ".tooltip-inner": $(tooltipTriggerEl).attr(
              "data-bs-original-title",
            ),
          });
      }
    });
  }
}

// Update the language selector dropdown to show current language
function updateLanguageSelector(lang) {
  const alpha2 = getAlpha2(lang);
  const flagSrc = $("#current-lang-flag")
    .attr("src")
    .replace(/\/[a-z]{2}\.svg$/, `/${alpha2 === "en" ? "us" : alpha2}.svg`);
  $("#current-lang-flag").attr("src", flagSrc);

  // Set the text based on the language
  const langNames = {
    en: "English",
    fr: "Français",
  };
  $("#current-lang-text").text(langNames[alpha2] || "English");
}

// Check if language preference exists in localStorage
const savedLang = localStorage.getItem("language");

i18next
  .use(i18nextHttpBackend)
  .use(i18nextBrowserLanguageDetector)
  .init(
    {
      fallbackLng: "en",
      debug: false,
      ns: ["messages"],
      defaultNS: "messages",
      backend: {
        loadPath: `${$("#home-path")
          .val()
          .trim()
          .replace(/\/home$/, "/locales")}/{{lng}}.json`,
      },
      detection: {
        order: ["localStorage", "navigator", "htmlTag"],
        lookupLocalStorage: "language",
        caches: ["localStorage"],
        convertDetectedLanguage: getAlpha2,
      },
      lng: savedLang || getAlpha2(i18next.language),
    },
    function (err) {
      if (err) return console.error("Error initializing i18next:", err);

      // Apply translation after i18next is initialized
      applyTranslations();
      updateLanguageSelector(i18next.language);

      i18next.on("languageChanged", function (lng) {
        i18next.language = getAlpha2(lng);
        applyTranslations();
        updateLanguageSelector(lng);
      });

      // Handle language selection clicks
      $(document).on("click", ".lang-option", function (e) {
        e.preventDefault();
        const lang = $(this).data("lang");
        changeLanguage(lang);
      });

      window.i18nextReady = true;
    },
  );

// Language switch helper
function changeLanguage(lang) {
  const alpha2 = getAlpha2(lang);
  // Save language preference to localStorage
  localStorage.setItem("language", alpha2);
  i18next.changeLanguage(alpha2);
}

// Handle DataTables collection button translations
$(document).on("click", ".buttons-collection", function () {
  const collection = $(this)
    .closest(".btn-group")
    .find(".dt-button-collection");

  collection.find("[data-i18n]").each(function () {
    const element = $(this);
    const key = element.attr("data-i18n");
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

    element.text(i18next.t(key, options));
  });
});

// Helper to update DataTable language and translations for a given table
function updateTableLanguageAndTranslations(table) {
  if (!table || !window.configureI18n) return;
  const tableId = $(table.table().node()).attr("id");
  const tableName = tableId || "items";
  const t = i18next.t.bind(i18next);
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
      const translation = i18next.t(key, options);
      if (element.is("input")) {
        element.attr("placeholder", translation);
      } else {
        element.text(translation);
      }
    },
  );
}

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
