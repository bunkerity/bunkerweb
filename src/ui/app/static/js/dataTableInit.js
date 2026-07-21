// dataTableInit.js

function collectDataTableSearchPaneEntries(requestData) {
  if (!requestData || typeof requestData !== "object") return [];

  const entries = Object.keys(requestData)
    .filter((key) => key.startsWith("searchPanes["))
    .map((key) => [key, String(requestData[key] || "")]);

  const flatten = (value, path) => {
    if (value === null || typeof value === "undefined") return;

    if (Array.isArray(value)) {
      value.forEach((item, index) => flatten(item, `${path}[${index}]`));
      return;
    }

    if (typeof value === "object") {
      Object.keys(value)
        .sort((a, b) => a.localeCompare(b))
        .forEach((key) => flatten(value[key], `${path}[${String(key)}]`));
      return;
    }

    entries.push([path, String(value)]);
  };

  if (requestData.searchPanes && typeof requestData.searchPanes === "object") {
    flatten(requestData.searchPanes, "searchPanes");
  }

  const seen = new Set();
  return entries
    .filter(([key, value]) => {
      const signature = `${key}=${value}`;
      if (seen.has(signature)) return false;
      seen.add(signature);
      return true;
    })
    .sort((a, b) => a[0].localeCompare(b[0]));
}

function getDataTableStateParams(dataTable) {
  const params = dataTable.ajax.params() || {};
  const state = {
    search: params.search ? params.search.value : "",
    order_column:
      params.order && params.order.length > 0
        ? params.columns[params.order[0].column].data
        : "",
    order_dir:
      params.order && params.order.length > 0 ? params.order[0].dir : "",
  };

  collectDataTableSearchPaneEntries(params).forEach(([key, value]) => {
    state[key] = value;
  });

  return state;
}

function appendDataTableParamsInputs(form, params, inputClass = "") {
  Object.entries(params).forEach(([name, value]) => {
    form.append(
      $("<input>", {
        type: "hidden",
        name: name,
        value: value,
        class: inputClass,
      }),
    );
  });
}

function appendDataTableStateInputs(form, dataTable) {
  appendDataTableParamsInputs(form, getDataTableStateParams(dataTable));
}

/**
 * Escape a single cell value against spreadsheet formula injection (CWE-1236).
 *
 * Mirrors the Python ``defusedcsv`` ``_escape`` logic used by the server-side
 * exports in ``app.utils.csv_writer`` / ``app.utils.csv_safe``: prefix a leading
 * single quote when the first character is one of ``= + - @ | %`` (and the value
 * is not a number / numeric-looking string), and additionally backslash-escape
 * embedded ``|`` characters. ``null``/``undefined`` and numeric values pass
 * through unchanged.
 *
 * Applied globally to every DataTables Buttons CSV / Excel / clipboard export
 * via the patch immediately below — every ``extend: "csv" | "excel" | "copy"``
 * button on every page picks this up automatically.
 *
 * @param {*} value Raw cell value coming from a DataTables row.
 * @returns {*} Escaped value safe for CSV / XLSX / clipboard targets.
 */
function bwCsvSafe(value) {
  if (value === null || value === undefined) return value;
  if (typeof value === "number") return value;
  let s = String(value);
  if (s && /^[@+\-=|%\t\r]/.test(s) && !/^-?[0-9,.]+$/.test(s)) {
    s = s.replace(/\\/g, "\\\\");
    s = s.replace(/\|/g, "\\|");
    s = "'" + s;
  }
  return s;
}

(function patchDataTablesButtonsForFormulaInjection() {
  if (typeof $ === "undefined" || !$.fn || !$.fn.dataTable) return;
  const ext = $.fn.dataTable.ext;
  if (!ext || !ext.buttons) return;

  // Built-in HTML5 export buttons: ``extend: "csv" | "excel" | "copy"`` resolve
  // to these via DataTables' button alias chain. We patch the per-button
  // ``action`` instead of ``exportOptions`` defaults because DataTables Buttons'
  // ``_resolveExtends`` does **not** deep-merge ``exportOptions`` from defaults
  // when the per-page config supplies its own ``exportOptions`` block, so any
  // ``format`` we put on the default object gets dropped.
  //
  // Wrapping ``action`` lets us mutate the resolved ``config`` immediately
  // before the export pipeline runs, which is the same call site every export
  // button (CSV / Excel / clipboard copy) goes through. The mutation is
  // idempotent because reassigning ``format.body`` to the same ``bwCsvSafe``
  // reference is a no-op on subsequent clicks.
  ["csvHtml5", "excelHtml5", "copyHtml5"].forEach(function (name) {
    const btn = ext.buttons[name];
    if (!btn || typeof btn.action !== "function" || btn.__bwCsvSafePatched)
      return;
    const origAction = btn.action;
    btn.action = function (e, dt, button, config) {
      config = config || {};
      config.exportOptions = config.exportOptions || {};
      config.exportOptions.format = $.extend(
        {},
        config.exportOptions.format || {},
        { body: bwCsvSafe, header: bwCsvSafe, footer: bwCsvSafe },
      );
      return origAction.call(this, e, dt, button, config);
    };
    btn.__bwCsvSafePatched = true;
  });
})();

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
    // Migrate old "All" (-1) to 100
    const parsedPageLength = parseInt(savedPageLength, 10);
    if (parsedPageLength === -1) {
      localStorage.setItem(`bw-${tableName}-pageLength`, "100");
    }
    // Apply saved pageLength to the options if it exists
    if (dataTableOptions.pageLength === undefined) {
      dataTableOptions.pageLength =
        parsedPageLength === -1 ? 100 : parsedPageLength;
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

  // Migrate stale "All" (-1) page length from DataTables' own saved state
  const existingStateLoadParams = safeDataTableOptions.stateLoadParams;
  safeDataTableOptions.stateLoadParams = function (settings, data) {
    if (data.length === -1) {
      data.length = 100;
    }
    if (typeof existingStateLoadParams === "function") {
      existingStateLoadParams.call(this, settings, data);
    }
  };

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
    // Strip data-i18n alongside the tooltip attrs: leaving it while
    // data-bs-original-title is removed makes applyTranslations() fall through
    // to .text() and overwrite the button content with the raw tooltip string.
    actionButton
      .removeClass("disabled")
      .parent()
      .attr("data-bs-toggle", null)
      .attr("data-bs-original-title", null)
      .attr("data-bs-placement", null)
      .removeAttr("data-i18n")
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

  // Cross-page selection affordance.
  // The header checkbox is configured (per-page) with `headerCheckbox: "select-page"`,
  // so by default it selects only rows on the current page. When more matching rows
  // exist on other pages, surface a banner that lets the user opt-in to selecting
  // the entire filtered set — and, once opted in, opt out via "Clear selection".
  //
  // Skipped for `serverSide: true` tables (bans, reports): DataTables only holds
  // the current page client-side, so `rows({ search: "applied" }).select()` would
  // not actually select off-page rows. A correct cross-page bulk action on a
  // server-side table requires submitting the active filter to the server-side
  // endpoint instead of an explicit row-id list — out of scope for this banner.
  const isServerSide = !!(
    dataTable.settings &&
    dataTable.settings()[0] &&
    dataTable.settings()[0].oFeatures &&
    dataTable.settings()[0].oFeatures.bServerSide
  );
  const $tableWrapper = $(`#${tableName}_wrapper`);
  if ($tableWrapper.length && !isServerSide) {
    const $bulkBanner = $(
      '<div class="dt-bulk-select-banner alert alert-primary py-2 px-3 mb-2 d-none align-items-center" role="status">' +
        '<i class="bx bx-info-circle me-2" aria-hidden="true"></i>' +
        '<span class="dt-bulk-select-message flex-grow-1"></span>' +
        '<button type="button" class="btn btn-sm btn-link p-0 ms-2 dt-bulk-select-action"></button>' +
        "</div>",
    );
    $tableWrapper.prepend($bulkBanner);

    const setBannerVisible = (visible) => {
      $bulkBanner
        .toggleClass("d-none", !visible)
        .toggleClass("d-flex", visible);
    };

    const updateBulkBanner = () => {
      const pageCount = dataTable.rows({ page: "current" }).count();
      const filteredCount = dataTable.rows({ search: "applied" }).count();
      const selectedCount = dataTable.rows({ selected: true }).count();
      const selectedOnPage = dataTable
        .rows({ page: "current", selected: true })
        .count();

      // Only meaningful when filtered set spans more than one page
      if (filteredCount <= pageCount) {
        setBannerVisible(false);
        return;
      }

      const $msg = $bulkBanner.find(".dt-bulk-select-message");
      const $action = $bulkBanner.find(".dt-bulk-select-action");

      if (
        selectedOnPage === pageCount &&
        pageCount > 0 &&
        selectedCount < filteredCount
      ) {
        const msgKey = "datatable.bulk_select_page";
        const actionKey = "datatable.bulk_select_all_filtered";
        const msgOpts = { count: selectedOnPage, entity: entityName };
        const actionOpts = { count: filteredCount, entity: entityName };
        $msg
          .attr("data-i18n", msgKey)
          .attr("data-i18n-options", JSON.stringify(msgOpts))
          .text(
            t(
              msgKey,
              `All ${selectedOnPage} ${entityName} on this page are selected.`,
              msgOpts,
            ),
          );
        $action
          .attr("data-i18n", actionKey)
          .attr("data-i18n-options", JSON.stringify(actionOpts))
          .data("action", "select-all-filtered")
          .text(
            t(
              actionKey,
              `Select all ${filteredCount} matching ${entityName}`,
              actionOpts,
            ),
          );
        setBannerVisible(true);
        return;
      }

      if (selectedCount >= filteredCount && filteredCount > 0) {
        const msgKey = "datatable.bulk_select_all_done";
        const actionKey = "datatable.bulk_select_clear";
        const msgOpts = { count: filteredCount, entity: entityName };
        $msg
          .attr("data-i18n", msgKey)
          .attr("data-i18n-options", JSON.stringify(msgOpts))
          .text(
            t(
              msgKey,
              `All ${filteredCount} matching ${entityName} are selected.`,
              msgOpts,
            ),
          );
        $action
          .attr("data-i18n", actionKey)
          .removeAttr("data-i18n-options")
          .data("action", "clear")
          .text(t(actionKey, "Clear selection"));
        setBannerVisible(true);
        return;
      }

      setBannerVisible(false);
    };

    $bulkBanner.on("click", ".dt-bulk-select-action", function () {
      const action = $(this).data("action");
      if (action === "select-all-filtered") {
        dataTable.rows({ search: "applied" }).select();
      } else if (action === "clear") {
        dataTable.rows().deselect();
      }
    });

    // Coalesce updates: bulk select operations (e.g.
    // `dataTable.rows({ search: "applied" }).select()` on a 5k-row table) emit
    // one `select` event per row. Without batching we'd run `updateBulkBanner`
    // 5k times in a single tick. A single pending flag plus rAF collapses the
    // burst to one render per frame.
    let bulkBannerPending = false;
    const scheduleBulkBannerUpdate = () => {
      if (bulkBannerPending) return;
      bulkBannerPending = true;
      const flush = () => {
        bulkBannerPending = false;
        updateBulkBanner();
      };
      if (typeof window.requestAnimationFrame === "function") {
        window.requestAnimationFrame(flush);
      } else {
        setTimeout(flush, 0);
      }
    };
    dataTable.on(
      "select deselect draw page length search",
      scheduleBulkBannerUpdate,
    );
    scheduleBulkBannerUpdate();
  }

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
