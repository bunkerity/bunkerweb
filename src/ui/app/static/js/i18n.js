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
        options = JSON.parse(optionsAttr);
      } catch (e) {
        console.error(
          `Error parsing data-i18n-options for key "${key}":`,
          e,
          optionsAttr,
        );
      }
    }
    // Prevent i18next from escaping single quotes to HTML entities
    const translation = i18next.t(key, {
      ...options,
      interpolation: { escapeValue: false },
    });
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
  if (typeof window.updatePageTitle === "function") {
    window.updatePageTitle();
  }
}

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

// Function to save language preference to the server
function saveLanguage(rootUrl, language) {
  // Don't send request if we're in setup mode or readonly
  const dbReadOnly = $("#db-read-only").val().trim() === "True";
  if (isSetup || dbReadOnly) {
    return;
  }

  const csrfToken = $("#csrf_token").val();
  if (!csrfToken) {
    console.warn(
      "CSRF token not found, cannot save language preference to server",
    );
    return;
  }

  const data = new FormData();
  data.append("language", language);
  data.append("csrf_token", csrfToken);

  fetch(rootUrl, {
    method: "POST",
    body: data,
  })
    .then((response) => {
      if (!response.ok) {
        throw new Error("Network response was not ok");
      }
    })
    .catch((error) => {
      console.error("Error saving language preference to server:", error);
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

const debouncedSaveLanguage = debounce(saveLanguage, 1000);

// Check if language preference exists in localStorage
const savedLang = localStorage.getItem("language");

const isSetup = window.location.pathname.endsWith("/setup");
const localesPath = isSetup
  ? "/setup/locales"
  : $("#home-path")
      .val()
      .trim()
      .replace(/\/home$/, "/locales");

function loadPluginTranslations(lang) {
  const path = window.BunkerWebExtraI18nPath;
  if (!path) return Promise.resolve();

  const url = path.replace("{{lng}}", lang);
  return fetch(url)
    .then((resp) => (resp.ok ? resp.json() : null))
    .then((extra) => {
      if (extra) {
        const ns = "messages";
        const existing = i18next.getResourceBundle(lang, ns) || {};
        const merged = { ...existing, ...extra };
        i18next.addResourceBundle(lang, ns, merged, true, true);
      }
    })
    .catch((err) => {
      console.error("Error loading plugin translations:", err);
    });
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

// Language switch helper
function changeLanguage(lang) {
  const alpha2 = getAlpha2(lang);
  // Save language preference to localStorage
  localStorage.setItem("language", alpha2);
  i18next.changeLanguage(alpha2);

  // Update documentation links
  updateDocumentationLinks(alpha2);

  // Get the root URL for the API endpoint
  const rootUrl = $("#home-path")
    .val()
    .trim()
    .replace(/\/home$/, "/set_language");

  // Save language preference to server
  debouncedSaveLanguage(rootUrl, alpha2);
}

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

$(document).ready(function () {
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
          loadPath: `${localesPath}/{{lng}}.json`,
        },
        detection: {
          order: ["localStorage", "navigator", "htmlTag"],
          lookupLocalStorage: "language",
          caches: ["localStorage"],
          convertDetectedLanguage: getAlpha2,
        },
        lng: savedLang || getAlpha2(i18next.language),
        supportedLngs: supportedLngs,
      },
      function (err) {
        if (err) return console.error("Error initializing i18next:", err);

        loadPluginTranslations(i18next.language).then(function () {
          applyTranslations();
          updateLanguageSelector(i18next.language);
          updateDocumentationLinks(i18next.language);
          $("[name='language']").val(i18next.language);
          $("#newsletter-locale").val(i18next.language);
        });

        i18next.on("languageChanged", function (lng) {
          i18next.language = getAlpha2(lng);
          loadPluginTranslations(i18next.language).then(function () {
            applyTranslations();
            updateLanguageSelector(lng);
            updateDocumentationLinks(lng);
            $("#newsletter-locale").val(i18next.language);
          });
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
            `<li class="no-language-items dropdown-item text-muted">${i18next.t(
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
