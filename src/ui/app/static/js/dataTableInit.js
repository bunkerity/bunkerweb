// dataTableInit.js

/**
 * Initialize a DataTable with i18n and user preferences.
 * @param {Object} config - Configuration object for the DataTable.
 * @returns {DataTable} - The initialized DataTable instance.
 */
function initializeDataTable(config) {
  // Ensure i18next is loaded before using it
  let t = typeof i18next !== "undefined" ? i18next.t : (key) => key; // Fallback

  const isReadOnly = $("#is-read-only").val().trim() === "True";
  const dbReadOnly = $("#db-read-only").val().trim() === "True";
  const {
    tableSelector,
    tableName,
    columnVisibilityCondition,
    dataTableOptions,
  } = config;

  // Consistent entityName logic
  const allowedNames = [
    "bans",
    "cache",
    "configs",
    "instances",
    "jobs",
    "plugins",
    "reports",
    "services",
    "templates",
  ];
  const entityName = allowedNames.includes(tableName) ? tableName : "items";

  // Ensure dataTableOptions is always an object
  const safeDataTableOptions =
    dataTableOptions && typeof dataTableOptions === "object"
      ? dataTableOptions
      : {};

  const filterToggleStorageKey = `bw-${tableName}-filters-expanded`;
  const filterToggleIdSuffix = String(tableName || "items")
    .toLowerCase()
    .replace(/[^a-z0-9_-]/g, "_");
  const showFiltersId = `show-filters-${filterToggleIdSuffix}`;
  const hideFiltersId = `hide-filters-${filterToggleIdSuffix}`;
  const showFiltersSelector = `#${showFiltersId}`;
  const hideFiltersSelector = `#${hideFiltersId}`;

  const syncFilterToggleUI = (isExpanded) => {
    const $showFilters = $(showFiltersSelector);
    const $hideFilters = $(hideFiltersSelector);
    if (!$showFilters.length || !$hideFilters.length) return;
    if (isExpanded) {
      $showFilters.addClass("d-none");
      $hideFilters.removeClass("d-none");
    } else {
      $showFilters.removeClass("d-none");
      $hideFilters.addClass("d-none");
    }
  };

  const applyLanguageSettings = (dtInstance, translator) => {
    const languageConfig = configureI18n(translator, entityName);
    // Merge new settings into existing ones to preserve any custom settings
    dtInstance.settings()[0].oLanguage = $.extend(
      true,
      dtInstance.settings()[0].oLanguage || {}, // Ensure oLanguage exists
      languageConfig,
    );
  };

  // Configure initial internationalization
  if (
    Object.prototype.hasOwnProperty.call(safeDataTableOptions, "language") &&
    typeof safeDataTableOptions.language === "object"
  ) {
    safeDataTableOptions.language = {
      ...configureI18n(t, entityName),
      ...safeDataTableOptions.language,
    };
  } else {
    safeDataTableOptions.language = configureI18n(t, entityName);
  }

  $.fn.dataTable.ext.buttons.toggle_filters = {
    // Use i18next.t for translatable parts
    text: `<span class="tf-icons bx bx-filter bx-18px me-2"></span><span id="${showFiltersId}" data-i18n="button.show">${t(
      "button.show",
    )}</span><span id="${hideFiltersId}" class="d-none" data-i18n="button.hide">${t(
      "button.hide",
    )}</span><span class="d-none d-md-inline" data-i18n="button.filters_suffix">${t(
      "button.filters_suffix",
    )}</span>`, // Assuming 'filters_suffix' key exists for " filters"
    action: function (e, dt, node, config) {
      const searchPanesContainer = dataTable.searchPanes.container();
      if (!searchPanesContainer) return;
      const $container = $(searchPanesContainer);
      const willShow = !$container.is(":visible");
      $container.slideToggle(); // Smoothly hide or show the container
      syncFilterToggleUI(willShow);
      localStorage.setItem(filterToggleStorageKey, willShow ? "true" : "false");
    },
  };

  // Check for saved pageLength in localStorage
  const savedPageLength = localStorage.getItem(`bw-${tableName}-pageLength`);
  if (savedPageLength !== null) {
    // Apply saved pageLength to the options if it exists
    if (dataTableOptions.pageLength === undefined) {
      dataTableOptions.pageLength = parseInt(savedPageLength, 10);
    }
  }

  if (safeDataTableOptions.infoCallback === undefined) {
    safeDataTableOptions.infoCallback = function (
      settings,
      start,
      end,
      max,
      total,
    ) {
      if (total === 0) {
        return t(
          `datatable.info_empty_${entityName}`,
          `No ${entityName} available`,
        );
      }
      return t(
        `datatable.info_${entityName}`,
        `Showing ${start} to ${end} of ${total} entries`,
        {
          start: start,
          end: end,
          total: total,
        },
      );
    };
  }

  // Initialize DataTable
  // Automatically enable state saving for DataTable
  safeDataTableOptions.stateSave = true;

  const dataTable = new DataTable(tableSelector, safeDataTableOptions);
  applyTranslations();

  // Ensure toggle filter buttons keep the outline-primary styling
  const buttonsContainer = dataTable.buttons().container();
  if (buttonsContainer && $(buttonsContainer).length) {
    $(buttonsContainer)
      .find(".toggle-filters")
      .removeClass("btn-secondary")
      .addClass("btn btn-sm btn-outline-primary");
  }

  const tableWrapperSelector =
    typeof tableSelector === "string" && tableSelector
      ? `${tableSelector}_wrapper`
      : null;

  $("input.dtsp-paneInputButton.search").each(function () {
    const $this = $(this);
    const placeholder = $this.attr("placeholder") || "";
    const i18nSuffix = placeholder.toLowerCase().replace(/\s+/g, "_").trim();

    if (i18nSuffix) $this.attr("data-i18n", `searchpane.${i18nSuffix}`);
  });

  const searchPanesContainer = dataTable.searchPanes.container();
  if (searchPanesContainer) {
    const $container = $(searchPanesContainer);
    const savedFiltersExpanded = localStorage.getItem(filterToggleStorageKey);
    const shouldShowFilters = savedFiltersExpanded === "true";
    if (shouldShowFilters) $container.show();
    else $container.hide();
    syncFilterToggleUI(shouldShowFilters);
  }

  dataTable.filterToggleSelectors = {
    show: showFiltersSelector,
    hide: hideFiltersSelector,
  };
  dataTable.updateFilterToggleUI = syncFilterToggleUI;
  dataTable.filterToggleStorageKey = filterToggleStorageKey;

  $(".dt-type-numeric").removeClass("dt-type-numeric");

  if (!isReadOnly)
    $(".action-button")
      .parent()
      .attr("data-bs-original-title", t("tooltip.table.select_rows_for_action"))
      .attr("data-i18n", "tooltip.table.select_rows_for_action")
      .attr("data-bs-placement", "top")
      .tooltip();

  $(".dt-search label").addClass("visually-hidden");
  // Use i18next.t for the placeholder
  $(".dt-search input[type=search]")
    .attr("placeholder", t("form.placeholder.search"))
    .attr("data-i18n", "form.placeholder.search");

  $(tableSelector).removeClass("d-none");
  $(`#${tableName}-waiting`).addClass("visually-hidden");

  const $columnsPreferenceDefaults = $("#columns_preferences_defaults");
  const $columnsPreference = $("#columns_preferences");
  let originalColumnsPreferences = {};

  if ($columnsPreferenceDefaults.length && $columnsPreference.length) {
    const defaultColsVisibility = JSON.parse(
      $columnsPreferenceDefaults.val().trim(),
    );
    originalColumnsPreferences = JSON.parse($columnsPreference.val().trim());

    // Handle column visibility preferences
    let columnVisibility = localStorage.getItem(`bw-${tableName}-columns`);
    if (columnVisibility === null) {
      columnVisibility = { ...originalColumnsPreferences };
    } else {
      columnVisibility = JSON.parse(columnVisibility);
    }

    Object.entries(columnVisibility).forEach(([key, value]) => {
      dataTable.column(key).visible(value);
    });

    // Save column preferences
    const saveColumnsPreferences = debounce(() => {
      const data = new FormData();
      data.append("csrf_token", $("#csrf_token").val().trim());
      data.append("table_name", tableName);
      data.append("columns_preferences", JSON.stringify(columnVisibility));

      const savePreferencesUrl = $("#home-path")
        .val()
        .trim()
        .replace(/\/home$/, "/set_columns_preferences");

      fetch(savePreferencesUrl, {
        method: "POST",
        body: data,
      })
        .then((response) => {
          if (!response.ok) {
            throw new Error("Network response was not ok");
          }
        })
        .catch((error) => {
          console.error("There was a problem with the fetch operation:", error);
        });
    }, 1000);

    if (typeof i18next !== "undefined") {
      i18next.on("languageChanged", (lng) => {
        // Update the local translator function
        t = i18next.t;
        // Re-apply language settings to the existing DataTable instance
        applyLanguageSettings(dataTable, t);
        // Redraw the table to reflect changes in info, pagination etc.
        dataTable.draw(false);
        // Re-apply translations to static elements within the table wrapper if needed
        // (e.g., custom buttons, search input placeholder if not handled by draw)
        if (tableWrapperSelector) {
          $(`${tableWrapperSelector} [data-i18n]`).each(function () {
            const element = $(this);
            const key = element.attr("data-i18n");
            const translation = t(key);

            if (element.is("input[placeholder]")) {
              element.attr("placeholder", translation);
            } else if (element.is("button") || element.is("span")) {
              const textNode = element
                .contents()
                .filter(function () {
                  return this.nodeType === 3;
                })
                .first();

              if (element.is("[placeholder]")) {
                element.attr("placeholder", translation);
              } else if (element.is("[title]")) {
                element.attr("title", translation);
              } else if (element.is("[data-bs-original-title]")) {
                element.attr("data-bs-original-title", translation);
              } else if (element.is("[aria-label]")) {
                element.attr("aria-label", translation);
              } else if (textNode.length) {
                textNode.replaceWith(DOMPurify.sanitize(translation));
              } else {
                element.text(translation);
                if (element.parent().is("span.dtsp-name[title]")) {
                  element.parent().attr("title", ` ${translation}`);
                }
              }
            }
          });
        }

        const searchPanesContainer = dataTable.searchPanes.container();
        if (searchPanesContainer && $(searchPanesContainer).length) {
          updateFilterTranslations();
        }
      });
    }

    // Column visibility event
    dataTable.on("column-visibility.dt", function (e, settings, column, state) {
      if (
        typeof columnVisibilityCondition === "function" &&
        !columnVisibilityCondition(column)
      ) {
        return;
      }
      columnVisibility[column] = state;
      const isDefault =
        JSON.stringify(columnVisibility) ===
        JSON.stringify(defaultColsVisibility);

      if (isDefault) {
        localStorage.removeItem(`bw-${tableName}-columns`);
      } else {
        localStorage.setItem(
          `bw-${tableName}-columns`,
          JSON.stringify(columnVisibility),
        );
      }

      if (dbReadOnly || Object.keys(originalColumnsPreferences).length === 0)
        return;

      saveColumnsPreferences();
    });

    // Override the default colvisRestore to respect server defaults
    dataTable.on(
      "buttons-action.dt",
      function (e, buttonApi, dtApi, node, config) {
        const isRestore =
          (config && config.extend === "colvisRestore") ||
          (config &&
            typeof config.className === "string" &&
            config.className.includes("buttons-colvisRestore"));
        if (!isRestore) return;

        // Apply default visibility from server-provided COLUMNS_PREFERENCES_DEFAULTS
        Object.entries(defaultColsVisibility).forEach(([key, value]) => {
          const colIdx = parseInt(key, 10);
          if (
            typeof columnVisibilityCondition === "function" &&
            !columnVisibilityCondition(colIdx)
          ) {
            return;
          }
          // Update local model then apply visibility
          columnVisibility[colIdx] = value;
          if (dataTable.column(colIdx).visible() !== value) {
            dataTable.column(colIdx).visible(value, false); // defer draw
          }
        });

        // Sync localStorage to reflect default state
        const isDefault =
          JSON.stringify(columnVisibility) ===
          JSON.stringify(defaultColsVisibility);
        if (isDefault) {
          localStorage.removeItem(`bw-${tableName}-columns`);
        } else {
          localStorage.setItem(
            `bw-${tableName}-columns`,
            JSON.stringify(columnVisibility),
          );
        }

        // Persist preferences to backend if applicable
        if (!dbReadOnly && Object.keys(originalColumnsPreferences).length > 0) {
          saveColumnsPreferences();
        }

        // Redraw once after batch changes and re-apply translations
        dataTable.columns.adjust().draw(false);
        applyTranslations();
      },
    );
  }

  // Page length change event
  dataTable.on("length.dt", function (e, settings, len) {
    localStorage.setItem(`bw-${tableName}-pageLength`, len);
  });

  $(document).on("hidden.bs.toast", ".toast", function (event) {
    if (event.target.id.startsWith("feedback-toast")) {
      setTimeout(() => {
        $(this).remove();
      }, 100);
    }
  });

  if (dataTable.responsive) dataTable.responsive.recalc();

  dataTable.on("mouseenter", "td", function () {
    if (dataTable.cell(this).index() === undefined) return;
    const rowIdx = dataTable.cell(this).index().row;

    dataTable
      .cells()
      .nodes()
      .each((el) => el.classList.remove("highlight"));

    dataTable
      .cells()
      .nodes()
      .each(function (el) {
        if (dataTable.cell(el).index().row === rowIdx)
          el.classList.add("highlight");
      });
  });

  dataTable.on("mouseleave", "td", function () {
    dataTable
      .cells()
      .nodes()
      .each((el) => el.classList.remove("highlight"));
  });

  dataTable.on("select", function (e, dt, type, indexes) {
    const actionButton = $(".action-button");
    if (!actionButton.length) return;

    // Enable the actions button
    actionButton
      .removeClass("disabled")
      .parent()
      .attr("data-bs-toggle", null)
      .attr("data-bs-original-title", null)
      .attr("data-bs-placement", null)
      .tooltip("dispose");
  });

  dataTable.on("deselect", function (e, dt, type, indexes) {
    // If no rows are selected, disable the actions button
    if (dataTable.rows({ selected: true }).count() === 0) {
      const actionButton = $(".action-button");
      if (!actionButton.length) return;

      if (!isReadOnly)
        actionButton
          .addClass("disabled")
          .parent()
          .attr("data-bs-toggle", "tooltip")
          .attr(
            "data-bs-original-title",
            t("tooltip.table.select_rows_for_action"),
          )
          .attr("data-i18n", "tooltip.table.select_rows_for_action")
          .attr("data-bs-placement", "top")
          .tooltip();
    }
  });

  // Note: colvisRestore handling moved earlier to respect defaults

  dataTable.columns.adjust().responsive.recalc();

  return dataTable;
}

/**
 * Configure DataTable internationalization using i18next
 * @param {Function} t - The i18next translation function
 * @param {string} entityName - The name of the entity for context-specific translations
 * @returns {Object} - DataTables language configuration object
 */
function configureI18n(t, entityName) {
  // Ensure t is a function, provide a fallback if not (e.g., during initial load before i18next is ready)
  const translate =
    typeof t === "function" ? t : (key, fallback) => fallback || key;

  return {
    emptyTable: translate(
      `datatable.info_empty_${entityName}`,
      `No ${entityName} available`,
    ),
    info: translate(
      `datatable.info_${entityName}`,
      "Showing _START_ to _END_ of _TOTAL_ entries",
    ),
    infoEmpty: translate(
      `datatable.info_empty_${entityName}`,
      `No ${entityName} available`,
    ),
    infoFiltered: translate(
      `datatable.info_filtered_${entityName}`,
      "(_MAX_ total entries)",
    ),
    lengthMenu: translate(
      `datatable.length_menu_${entityName}`,
      "Display _MENU_ entries",
    ),
    zeroRecords: translate(
      `datatable.zero_records_${entityName}`,
      `No matching ${entityName} found`,
    ),
    processing: translate("datatable.processing", "Processing..."),
    search: translate("datatable.search", "Search:"),
    select: {
      rows: {
        _: translate(
          `datatable.select_rows_${entityName}_plural`,
          "Selected %d entries",
        ),
        0: translate(
          `datatable.select_rows_${entityName}_0`,
          "No entries selected",
        ),
        1: translate(
          `datatable.select_rows_${entityName}_1`,
          "Selected 1 entry",
        ),
      },
    },
    searchPanes: {
      emptyPanes: translate("searchpane.empty", "No search panes available"),
      loadMessage: translate("searchpane.loading", "Loading search panes..."),
      title: {
        _: translate("searchpane.title_plural", "Active Filters - %d"),
        0: translate("searchpane.title_0", "No Active Filter"),
        1: translate("searchpane.title_1", "Active Filter - 1"),
      },
      clearMessage: translate("searchpane.clear", "Clear All"),
      collapse: {
        0: translate("searchpane.collapse_0", "SearchPanes"),
        _: translate("searchpane.collapse_plural", "SearchPanes (%d)"),
      },
      collapseMessage: translate("searchpane.collapse_message", "Collapse All"),
      showMessage: translate("searchpane.show_message", "Show All"),
      count: translate("searchpane.count", "{total}"),
      countFiltered: translate("searchpane.countFiltered", "{shown} ({total})"),
    },
  };
}

// Expose configureI18n globally so it can be used by i18n.js for language switching
window.configureI18n = configureI18n;

// Helper function to update translations for filter elements (if needed within this file)
// Consider making this globally available if used by both files.
function updateFilterTranslations() {
  const translate =
    typeof i18next !== "undefined"
      ? i18next.t
      : (key, fallback) => fallback || key;
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
      const translation = translate(key, options);
      if (element.is("input")) {
        element.attr("placeholder", translation);
      } else {
        element.text(translation);
      }
    },
  );
  // Update SearchPanes title
  const searchPanes = $(".dtsp-title");
  if (searchPanes.length) {
    const currentTitle = searchPanes.text();
    // Attempt to extract the count if present
    const match = currentTitle.match(/\((\d+)\)/);
    const count = match ? parseInt(match[1], 10) : 0;
    const titleKey =
      count === 0
        ? "searchpane.title_0"
        : count === 1
          ? "searchpane.title_1"
          : "searchpane.title_plural";
    searchPanes.text(translate(titleKey, { count: count }));
  }
  // Update SearchPanes clear/collapse buttons
  $(".dtsp-clearAll, .dtsp-collapseAll, .dtsp-showAll").each(function () {
    const $button = $(this);
    let key = "";
    if ($button.hasClass("dtsp-clearAll")) key = "searchpane.clear";
    else if ($button.hasClass("dtsp-collapseAll"))
      key = "searchpane.collapse_message";
    else if ($button.hasClass("dtsp-showAll")) key = "searchpane.show_message";
    if (key) $button.text(translate(key));
  });
}
