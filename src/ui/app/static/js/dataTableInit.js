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
  // button (CSV / Excel / clipboard copy) goes through. ``btn.action`` itself is
  // wrapped once (``__bwCsvSafePatched``); the ``format`` assignment inside it
  // runs per click and simply overwrites the previous one.
  ["csvHtml5", "excelHtml5", "copyHtml5"].forEach(function (name) {
    const btn = ext.buttons[name];
    if (!btn || typeof btn.action !== "function" || btn.__bwCsvSafePatched)
      return;
    const origAction = btn.action;
    btn.action = function (e, dt, button, config, cb) {
      config = config || {};
      config.exportOptions = config.exportOptions || {};

      // Buttons' own default formatters are what call ``stripData``, which is
      // what removes the markup from a cell. Replacing them outright therefore
      // exported raw ``innerHTML`` (badges, links, icons) into every CSV / XLSX
      // / clipboard payload, so compose with it instead of overwriting it.
      //
      // ``stripData`` reads its flags from the second argument and skips a step
      // whenever that object is *present* with the flag falsy — in the vendored
      // bundle, ``n && !n.stripHtml || (t = stripHtml(t))``. Passing
      // ``exportOptions`` alone would therefore silently disable stripping
      // again, so the library defaults are restated here. Anything the page set
      // explicitly still wins, because it is merged in last.
      //
      // ``escapeExcelFormula`` is deliberately left out: with it falsy,
      // ``stripData`` skips its own ``^[=@\t\r]`` prefixing and ``bwCsvSafe``
      // remains the single place formula injection is escaped — on a wider
      // character set, and without double-prefixing.
      const stripConfig = $.extend(
        {
          stripHtml: true,
          stripNewlines: true,
          decodeEntities: true,
          trim: true,
        },
        config.exportOptions,
      );
      const stripThenEscape = function (value) {
        return bwCsvSafe($.fn.dataTable.Buttons.stripData(value, stripConfig));
      };

      config.exportOptions.format = $.extend(
        {},
        config.exportOptions.format || {},
        {
          body: stripThenEscape,
          header: stripThenEscape,
          footer: stripThenEscape,
        },
      );
      return origAction.call(this, e, dt, button, config, cb);
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
    delegatedTooltips,
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
    "workflows",
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

  let advancedFilters;
  const syncFilterToggleUI = (isExpanded) => {
    if (advancedFilters) advancedFilters.toggle(isExpanded);
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
    text: `<i class="bx bx-filter" aria-hidden="true"></i><span class="d-none d-md-inline">${t("table_system.filters", "Filters")}</span><span class="af-count" hidden aria-hidden="true"></span>`,
    action: function (e, dt, node, config) {
      if (!advancedFilters) return;
      const willShow = !advancedFilters.isExpanded();
      advancedFilters.toggle(willShow);
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

  bwPrepareTableButtons(safeDataTableOptions, t);
  const dataTable = new DataTable(tableSelector, safeDataTableOptions);
  const tableContainer = dataTable.table().container();
  tableContainer.classList.add("bw-data-table");
  const tableNode = dataTable.table().node();
  if (!tableNode.parentElement.classList.contains("bw-table-scroll")) {
    $(tableNode).wrap('<div class="bw-table-scroll"></div>');
  }
  advancedFilters = bwAdvancedFilters(dataTable, t, filterToggleStorageKey);
  $(tableContainer).find(".dt-search").addClass("search-mini");
  $(tableContainer)
    .find(".btn-minor")
    .not(".action-button")
    .each(function () {
      if (!this.hasAttribute("aria-label"))
        this.setAttribute("aria-label", this.textContent.trim());
      bootstrap.Tooltip.getOrCreateInstance(this, {
        title: () =>
          window.matchMedia("(max-width: 767px)").matches
            ? this.getAttribute("aria-label")
            : "",
      });
    });
  dataTable.on("destroy.dt", () => {
    $(tableContainer)
      .find(".btn-minor")
      .each(function () {
        bootstrap.Tooltip.getInstance(this)?.dispose();
      });
  });
  applyTranslations();

  // Rows are rebuilt on every draw, so per-trigger instances would be disposed and
  // recreated (and leaked) each time. One delegated tooltip builds an instance on
  // first hover instead; the row instances are dropped with the rows.
  if (delegatedTooltips && typeof bootstrap !== "undefined") {
    new bootstrap.Tooltip(dataTable.table().container(), {
      selector: '[data-bs-toggle="tooltip"]',
    });
    const disposeTooltips = (root) => () => {
      $(root())
        .find('[data-bs-toggle="tooltip"]')
        .each(function () {
          const instance = bootstrap.Tooltip.getInstance(this);
          if (instance) instance.dispose();
        });
    };
    dataTable.on(
      "preDraw.dt",
      disposeTooltips(() => dataTable.table().body()),
    );
    dataTable.on(
      "column-visibility.dt",
      disposeTooltips(() => dataTable.table().node()),
    );
  }

  // Shared controls inherit the same neutral toolbar styling.
  const buttonsContainer = dataTable.buttons().container();
  if (buttonsContainer && $(buttonsContainer).length) {
    $(buttonsContainer)
      .find(".toggle-filters")
      .removeClass("btn-secondary btn-outline-primary")
      .addClass("btn btn-sm btn-light btn-minor");
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

  const searchPanesContainer = dataTable.searchPanes?.container?.();
  if (searchPanesContainer) {
    const $container = $(searchPanesContainer);
    const savedFiltersExpanded = localStorage.getItem(filterToggleStorageKey);
    const shouldShowFilters = savedFiltersExpanded === "true";
    $container.addClass("bw-filter-engine").attr("aria-hidden", "true");
    syncFilterToggleUI(shouldShowFilters);
  }

  dataTable.filterToggleSelectors = {
    show: showFiltersSelector,
    hide: hideFiltersSelector,
  };
  dataTable.updateFilterToggleUI = syncFilterToggleUI;
  dataTable.filterToggleStorageKey = filterToggleStorageKey;

  $(".dt-type-numeric").removeClass("dt-type-numeric");

  const syncActionButton = () => {
    if (isReadOnly) return;
    const disabled = dataTable.rows({ selected: true }).count() === 0;
    $(tableContainer)
      .find(".action-button")
      .each(function () {
        bootstrap.Tooltip.getInstance(this)?.dispose();
        $(this)
          .toggleClass("disabled", disabled)
          .attr("aria-disabled", String(disabled));
        if (disabled) {
          $(this)
            .attr(
              "data-bs-original-title",
              t(
                "table_system.multiple_actions",
                "Multiple actions for selected items",
              ),
            )
            .tooltip();
        } else {
          $(this).removeAttr("data-bs-original-title data-i18n");
        }
      });
  };
  syncActionButton();

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

    // Without the second argument every call re-measures the whole table; the
    // adjust() at the end of this function does it once.
    Object.entries(columnVisibility).forEach(([key, value]) => {
      dataTable.column(key).visible(value, false);
    });

    // Save column preferences. The debounce batches a run of column toggles, so a pending
    // write is flushed on pagehide -- otherwise navigating within a second of the last toggle
    // silently discarded it.
    let columnsPreferencesPending = false;
    const postColumnsPreferences = () => {
      columnsPreferencesPending = false;
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
        keepalive: true,
      })
        .then((response) => {
          if (!response.ok) {
            throw new Error("Network response was not ok");
          }
        })
        .catch((error) => {
          console.error("There was a problem with the fetch operation:", error);
        });
    };

    const debouncedPostColumnsPreferences = debounce(
      postColumnsPreferences,
      1000,
    );

    const saveColumnsPreferences = () => {
      columnsPreferencesPending = true;
      debouncedPostColumnsPreferences();
    };

    $(window).on("pagehide", () => {
      if (columnsPreferencesPending) postColumnsPreferences();
    });

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

        const searchPanesContainer = dataTable.searchPanes?.container?.();
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
      const isDefault = Object.entries(defaultColsVisibility).every(
        ([key, value]) => dataTable.column(key).visible() === value,
      );

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
        const isDefault = Object.entries(defaultColsVisibility).every(
          ([key, value]) => dataTable.column(key).visible() === value,
        );
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

  dataTable.on(`select deselect`, syncActionButton);

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
        // One whole sentence per entity (datatable.bulk_select.<entity>.*): the noun is part of the
        // translation, never interpolated from English.
        const msgKey = `datatable.bulk_select.${entityName}.page_${selectedOnPage === 1 ? "one" : "other"}`;
        const actionKey = `datatable.bulk_select.${entityName}.all_filtered`;
        const msgOpts = { count: selectedOnPage };
        const actionOpts = { count: filteredCount };
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
        const msgKey = `datatable.bulk_select.${entityName}.all_done`;
        const actionKey = "datatable.bulk_select_clear";
        const msgOpts = { count: filteredCount };
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

// Keep page-owned actions/export callbacks intact; replace only shared chrome.
function bwPrepareTableButtons(options, t) {
  if (options.searchPanes) options.searchPanes.cascadePanes = false;
  const prepare = (buttons, inCollection = false) =>
    buttons
      .filter((button) => {
        const kind = typeof button === "string" ? button : button.extend;
        return kind !== "colvisRestore";
      })
      .map((button) => {
        if (typeof button === "string" && !$.fn.dataTable.ext.buttons[button])
          return button;
        const item = typeof button === "string" ? { extend: button } : button;
        if (item.extend === "colvis") {
          item.extend = undefined;
          item.className = "btn btn-sm btn-light btn-minor bw-columns-button";
          item.text = `<i class="bx bx-columns" aria-hidden="true"></i><span class="d-none d-md-inline">${t("button.columns", "Columns")}</span>`;
          item.action = (e, dt, node) =>
            bwColumnPopover(dt, node[0], item.columns, t);
        } else if (
          !inCollection &&
          ["collection", "toggle_filters"].includes(item.extend)
        ) {
          item.className = `${item.className || ""} btn btn-sm btn-light btn-minor`;
          item.className = item.className.replace(
            /btn-outline-primary|btn-secondary/g,
            "",
          );
        }
        if (Array.isArray(item.buttons)) {
          if (
            item.extend === "collection" &&
            item.autoClose === undefined &&
            item.buttons.some((child) =>
              [
                "copy",
                "csv",
                "excel",
                "copyHtml5",
                "csvHtml5",
                "excelHtml5",
              ].includes(typeof child === "string" ? child : child.extend),
            )
          )
            item.autoClose = true;
          item.buttons = prepare(item.buttons, true);
        }
        return item;
      });
  Object.values(options.layout || {}).forEach((row) => {
    if (row?.searchPanes) row.searchPanes.cascadePanes = false;
    if (row && typeof row === "object" && Array.isArray(row.buttons)) {
      row.buttons = prepare(row.buttons);
    }
  });
}

let bwCloseColumnPopover;
function bwColumnPopover(dt, trigger, selector, t) {
  if (bwCloseColumnPopover) {
    const sameTrigger = trigger.getAttribute("aria-expanded") === "true";
    bwCloseColumnPopover();
    if (sameTrigger) return;
  }
  const indexes = dt.columns(selector).indexes().toArray();
  if (indexes.length && !indexes.some((index) => dt.column(index).visible()))
    dt.column(indexes[0]).visible(true);
  const panel = document.createElement("div");
  panel.className = "col-pop";
  panel.id = `${dt.table().node().id}-columns-popover`;
  panel.setAttribute("role", "dialog");
  panel.setAttribute(
    "aria-label",
    t("table_system.visible_columns", "Visible columns"),
  );
  const head = document.createElement("div");
  head.className = "col-pop-head";
  const title = document.createElement("strong");
  title.textContent = t("table_system.visible_columns", "Visible columns");
  const count = document.createElement("span");
  count.setAttribute("aria-live", "polite");
  head.append(title, count);
  const list = document.createElement("div");
  list.className = "col-pop-list";
  indexes.forEach((index) => {
    const label = document.createElement("label");
    label.className = "col-pop-item bw-checkbox";
    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = dt.column(index).visible();
    input.dataset.column = index;
    label.append(
      input,
      document.createTextNode(dt.column(index).header().textContent.trim()),
    );
    list.append(label);
  });
  const sync = () => {
    const boxes = [...list.querySelectorAll("input")];
    const visible = indexes.filter((index) =>
      dt.column(index).visible(),
    ).length;
    count.textContent = t(
      "table_system.column_count",
      "{{visible}} of {{total}}",
      { visible, total: indexes.length },
    );
    boxes.forEach((box) => {
      box.checked = dt.column(Number(box.dataset.column)).visible();
      box.disabled = box.checked && visible === 1;
    });
  };
  const footer = document.createElement("div");
  footer.className = "col-pop-foot";
  const showAll = document.createElement("button");
  showAll.type = "button";
  showAll.className = "btn btn-sm btn-light";
  showAll.textContent = t("table_system.show_all", "Show all");
  const reset = showAll.cloneNode();
  reset.textContent = t("button.reset", "Reset");
  showAll.addEventListener("click", () => {
    indexes.forEach((index) => dt.column(index).visible(true, false));
    dt.columns.adjust().draw(false);
    sync();
  });
  reset.addEventListener("click", () => {
    const defaults = JSON.parse(
      document.getElementById("columns_preferences_defaults")?.value || "{}",
    );
    indexes.forEach((index) => {
      if (Object.prototype.hasOwnProperty.call(defaults, index))
        dt.column(index).visible(defaults[index], false);
    });
    if (!indexes.some((index) => dt.column(index).visible()) && indexes.length)
      dt.column(indexes[0]).visible(true, false);
    dt.columns.adjust().draw(false);
    sync();
  });
  footer.append(showAll, reset);
  panel.append(head, list, footer);
  list.addEventListener("change", (event) => {
    const box = event.target;
    dt.column(Number(box.dataset.column)).visible(box.checked);
    dt.columns.adjust().responsive.recalc();
    sync();
  });
  document.body.append(panel);
  const rect = trigger.getBoundingClientRect();
  panel.style.top = `${Math.max(8, Math.min(rect.bottom + 6, window.innerHeight - panel.offsetHeight - 8))}px`;
  panel.style.left = `${Math.max(8, Math.min(rect.left, window.innerWidth - panel.offsetWidth - 8))}px`;
  trigger.setAttribute("aria-expanded", "true");
  trigger.setAttribute("aria-haspopup", "dialog");
  trigger.setAttribute("aria-controls", panel.id);
  const outside = (event) => {
    if (!panel.contains(event.target) && !trigger.contains(event.target))
      close();
  };
  const close = () => {
    panel.remove();
    trigger.setAttribute("aria-expanded", "false");
    document.removeEventListener("click", outside);
    window.removeEventListener("resize", close);
    dt.off("destroy.dt", close);
    bwCloseColumnPopover = null;
  };
  panel.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      close();
      trigger.focus();
    }
  });
  panel.addEventListener("focusout", (event) => {
    if (event.relatedTarget && !panel.contains(event.relatedTarget)) close();
  });
  document.addEventListener("click", outside);
  window.addEventListener("resize", close);
  dt.on("destroy.dt", close);
  bwCloseColumnPopover = close;
  sync();
  panel
    .querySelector(".col-pop input:not(:disabled), .col-pop button")
    ?.focus();
}

// SearchPanes remains the compatibility engine for predicate functions, saved state,
// server-side searchPanes parameters, and existing page deep-link handlers. Its UI
// is replaced by the single-select card, using the pane DataTables' public APIs.
function bwAdvancedFilters(dt, t, storageKey) {
  const engine = dt.searchPanes?.container?.();
  if (!engine || !$(engine).length) return null;
  const $engine = $(engine)
    .addClass("bw-filter-engine")
    .attr("aria-hidden", "true");
  const card = document.createElement("section");
  card.className = "adv-filters";
  card.id = `${dt.table().node().id}-advanced-filters`;
  card.setAttribute(
    "aria-label",
    t("table_system.advanced_filters", "Advanced filters"),
  );
  const head = document.createElement("div");
  head.className = "adv-filters-head";
  const title = document.createElement("strong");
  title.textContent = t("table_system.advanced_filters", "Advanced filters");
  const reset = document.createElement("button");
  reset.type = "button";
  reset.className = "btn btn-sm btn-light";
  reset.textContent = t("button.reset", "Reset");
  const apply = document.createElement("button");
  apply.type = "button";
  apply.className = "btn btn-sm btn-primary";
  apply.textContent = t("table_system.filter", "Filter");
  head.append(title, reset, apply);
  const grid = document.createElement("div");
  grid.className = "adv-filters-grid";
  card.append(head, grid);
  const wrapper = dt.table().container();
  wrapper.querySelector(".bw-table-scroll").before(card);
  const toggleButtons = $(wrapper).find(".toggle-filters");
  const panes = [];
  const labelText = (value) => {
    const template = document.createElement("template");
    template.innerHTML = String(value ?? "");
    return template.content.textContent.trim();
  };
  const refresh = () => {
    let active = 0;
    const seen = new Set();
    $engine.find("table").each(function () {
      if (!$.fn.dataTable.isDataTable(this)) return;
      const api = $(this).DataTable();
      if (api.table().node() !== this) return;
      seen.add(this);
      let pane = panes.find((item) => item.table === this);
      if (!pane) {
        const label = document.createElement("label");
        label.className = "adv-filter-field";
        const caption = document.createElement("span");
        const select = document.createElement("select");
        select.className = "form-select";
        label.append(caption, select);
        grid.append(label);
        pane = { table: this, api, select, caption };
        panes.push(pane);
      }
      pane.api = api;
      const header = this.closest(".dtsp-searchPane")?.querySelector(
        ".dtsp-paneInputButton",
      );
      pane.caption.textContent =
        header?.placeholder || header?.textContent || "";
      let selected = api.rows({ selected: true }).indexes().toArray();
      // Migrate legacy multi-value state to the single value shown by this select.
      if (selected.length > 1) {
        api.rows(selected.slice(1)).deselect();
        selected = selected.slice(0, 1);
      }
      if (selected.length) active++;
      // Preserve an unsubmitted draft while refreshing server-side counts.
      const dirty = pane.select.dataset.dirty === "true";
      pane.select.replaceChildren(new Option(t("table_system.any", "Any"), ""));
      api.rows().every(function () {
        const row = this.data();
        const label = labelText(row.display);
        const option = new Option(label, String(this.index()));
        option.selected = dirty
          ? row.filter === pane.draft
          : selected.includes(this.index());
        pane.select.add(option);
      });
      pane.select.onchange = () => {
        pane.select.dataset.dirty = "true";
        pane.draft =
          pane.select.value === ""
            ? undefined
            : pane.api.row(Number(pane.select.value)).data().filter;
      };
    });
    for (let index = panes.length - 1; index >= 0; index--) {
      if (!seen.has(panes[index].table)) {
        panes[index].select.parentElement.remove();
        panes.splice(index, 1);
      }
    }
    toggleButtons.each(function () {
      this.setAttribute("aria-controls", card.id);
      this.setAttribute(
        "aria-label",
        active
          ? t("table_system.active_filters", "Filters, {{count}} active", {
              count: active,
            })
          : t("table_system.filters", "Filters"),
      );
      const count = this.querySelector(".af-count");
      if (count) {
        count.textContent = active;
        count.hidden = active === 0;
      }
    });
  };
  let applying = false;
  let pending;
  const schedule = () => {
    if (applying) return;
    clearTimeout(pending);
    pending = setTimeout(refresh, 0);
  };
  $engine.on(`draw.dt select.dt deselect.dt`, schedule);
  dt.on("draw.dt", schedule);
  reset.addEventListener("click", () => {
    panes.forEach((pane) => {
      delete pane.select.dataset.dirty;
    });
    dt.searchPanes.clearSelections();
    refresh();
  });
  apply.addEventListener("click", () => {
    // Snapshot values before selecting: cascade redraws can replace pane rows.
    const values = panes.map((pane) => ({
      pane,
      value:
        pane.select.value === ""
          ? undefined
          : pane.api.row(Number(pane.select.value)).data().filter,
    }));
    applying = true;
    dt.searchPanes.clearSelections();
    values.forEach(({ pane, value }) => {
      delete pane.select.dataset.dirty;
      if (value === undefined) return;
      pane.api.rows().every(function () {
        if (this.data().filter === value) this.select();
      });
    });
    applying = false;
    refresh();
  });
  const toggle = (expanded) => {
    card.hidden = !expanded;
    toggleButtons.attr("aria-expanded", String(expanded));
  };
  toggle(localStorage.getItem(storageKey) === "true");
  refresh();
  dt.on("destroy.dt", () => {
    clearTimeout(pending);
    $engine.off(`draw.dt select.dt deselect.dt`, schedule);
    card.remove();
  });
  return { toggle, isExpanded: () => !card.hidden, refresh };
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
      aria: { rowCheckbox: translate("datatable.select_row", "Select row") },
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
    // DataTables' pane search box reads its title from the searchBuilder namespace.
    searchBuilder: {
      searchTitle: translate("searchpane.search_title", "Search: {name}"),
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
