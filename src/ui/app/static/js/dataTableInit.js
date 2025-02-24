// dataTableInit.js

function initializeDataTable(config) {
  const isReadOnly = $("#is-read-only").val().trim() === "True";
  const {
    tableSelector,
    tableName,
    columnVisibilityCondition,
    dataTableOptions,
  } = config;

  $.fn.dataTable.ext.buttons.toggle_filters = {
    text: '<span class="tf-icons bx bx-filter bx-18px me-2"></span><span id="show-filters">Show</span><span id="hide-filters" class="d-none">Hide</span><span class="d-none d-md-inline"> filters</span>',
    action: function (e, dt, node, config) {
      const searchPanesContainer = dataTable.searchPanes.container();
      if (!searchPanesContainer) return;
      dataTable.searchPanes.container().slideToggle(); // Smoothly hide or show the container
      $("#show-filters").toggleClass("d-none"); // Toggle the visibility of the 'Show' span
      $("#hide-filters").toggleClass("d-none"); // Toggle the visibility of the 'Hide' span
    },
  };

  // Initialize DataTable
  const dataTable = new DataTable(tableSelector, dataTableOptions);

  if (dataTable.searchPanes.container())
    dataTable.searchPanes.container().hide();

  $(".dt-type-numeric").removeClass("dt-type-numeric");

  if (!isReadOnly)
    $(".action-button")
      .parent()
      .attr(
        "data-bs-original-title",
        "Please select one or more rows to perform an action.",
      )
      .attr("data-bs-placement", "top")
      .tooltip();

  $(".dt-search label").addClass("visually-hidden");
  $(".dt-search input[type=search]").attr("placeholder", "Search");

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

      if (isReadOnly || !originalColumnsPreferences) return;

      saveColumnsPreferences();
    });
  }

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
            "Please select one or more rows to perform an action.",
          )
          .attr("data-bs-placement", "top")
          .tooltip();
    }
  });

  return dataTable;
}
