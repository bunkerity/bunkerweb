// Plugins marketplace grid — client-side filtering (tabs + search), per-card enable/disable
// switch (submits to /plugins/enable), per-card uninstall (reuses the shared delete modal),
// and the drag-and-drop upload flow (ported verbatim from the retired DataTable page so the
// existing /plugins/upload + /plugins/refresh flow keeps working).
$(document).ready(function () {
  const t =
    typeof i18next !== "undefined"
      ? i18next.t
      : (key, fallback) => fallback || key;

  const isAdmin = ($("#is-admin").val() || "True").trim() === "True";
  const isReadOnly =
    ($("#is-read-only").val() || "False").trim() === "True" || !isAdmin;

  // --------------------------------------------------------------------------
  // Filter tabs + search
  // --------------------------------------------------------------------------
  const grid = document.getElementById("plugin-grid");
  const cards = grid
    ? Array.from(grid.querySelectorAll(".plugin-card-col"))
    : [];
  const emptyState = document.getElementById("plugin-grid-empty");
  const searchInput = document.getElementById("plugin-search");
  let activeFilter = "all";

  const matchesFilter = (card, filter) => {
    switch (filter) {
      case "all":
        return true;
      case "enabled":
        return card.dataset.enabled === "true";
      case "disabled":
        return card.dataset.enabled === "false";
      case "core":
        return card.dataset.tier === "core";
      case "community":
        return card.dataset.tier === "community";
      case "pro":
        return card.dataset.tier === "pro";
      default:
        return true;
    }
  };

  const applyFilters = () => {
    const term = (searchInput ? searchInput.value : "").trim().toLowerCase();
    let visible = 0;
    cards.forEach((card) => {
      const matchesSearch =
        !term ||
        card.dataset.name.toLowerCase().includes(term) ||
        card.dataset.description.toLowerCase().includes(term) ||
        card.dataset.plugin.toLowerCase().includes(term);
      const show = matchesFilter(card, activeFilter) && matchesSearch;
      card.classList.toggle("d-none", !show);
      if (show) visible += 1;
    });
    if (emptyState) emptyState.classList.toggle("d-none", visible !== 0);
  };

  const updateCounts = () => {
    const counts = {
      all: 0,
      enabled: 0,
      disabled: 0,
      core: 0,
      community: 0,
      pro: 0,
    };
    cards.forEach((card) => {
      counts.all += 1;
      counts[card.dataset.enabled === "true" ? "enabled" : "disabled"] += 1;
      if (counts[card.dataset.tier] !== undefined)
        counts[card.dataset.tier] += 1;
    });
    document.querySelectorAll(".plugin-filter-count").forEach((el) => {
      const key = el.dataset.filterCount;
      if (counts[key] !== undefined) el.textContent = counts[key];
    });
  };

  document.querySelectorAll(".plugin-filter").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".plugin-filter").forEach((b) => {
        b.classList.toggle("active", b === btn);
        b.setAttribute("aria-selected", b === btn ? "true" : "false");
      });
      activeFilter = btn.dataset.filter;
      applyFilters();
    });
  });

  if (searchInput) searchInput.addEventListener("input", applyFilters);

  updateCounts();
  applyFilters();

  // --------------------------------------------------------------------------
  // Enable/disable switch -> submit the per-card form to /plugins/enable
  // --------------------------------------------------------------------------
  $(document).on("change", ".plugin-switch", function () {
    if (isReadOnly) {
      this.checked = !this.checked;
      alert(
        t(
          "alert.readonly_mode",
          "This action is not allowed in read-only mode.",
        ),
      );
      return;
    }
    const form = this.closest("form");
    if (!form) return;
    const field = form.querySelector(".plugin-enabled-field");
    if (field) field.value = this.checked ? "yes" : "no";
    form.submit();
  });

  // --------------------------------------------------------------------------
  // Uninstall -> reuse the shared delete modal + selected-list recap
  // --------------------------------------------------------------------------
  const pluginsListColumns = [
    {
      key: "name",
      i18n: "table.header.name",
      label: t("table.header.name", "Name"),
      bold: true,
    },
    {
      key: "type",
      i18n: "table.header.type",
      label: t("table.header.type", "Type"),
    },
  ];

  const setupDeletionModal = (plugin) => {
    const modalEl = document.getElementById("modal-delete-plugins");
    if (!modalEl || typeof BWSelectedList === "undefined") return;
    const card = grid.querySelector(
      `.plugin-card-col[data-plugin="${plugin}"]`,
    );
    const rows = [
      {
        id: plugin,
        name: card ? card.dataset.pluginName : plugin,
        type: card ? (card.dataset.type || "").toUpperCase() : "",
      },
    ];
    BWSelectedList.render("#selected-plugins-delete", rows, {
      entity: "plugins",
      hiddenMode: "csv",
      columns: pluginsListColumns,
    });
    new bootstrap.Modal(modalEl).show();
  };

  $(document).on("click", ".delete-plugin", function () {
    if (isReadOnly) {
      alert(
        t(
          "alert.readonly_mode",
          "This action is not allowed in read-only mode.",
        ),
      );
      return;
    }
    setupDeletionModal($(this).data("plugin-id"));
  });

  // --------------------------------------------------------------------------
  // Drag-and-drop upload (ported from the retired plugins.js DataTable page)
  // --------------------------------------------------------------------------
  const dragArea = $("#drag-area");
  const fileInput = $("#file-input");
  const fileList = $("#file-list");

  const validateFile = (file) => {
    const validExtensions = [".zip", ".tar.gz", ".tar.xz"];
    const fileName = file.name.toLowerCase();
    const maxFileSize = 50 * 1024 * 1024; // 50 MB
    if (!validExtensions.some((ext) => fileName.endsWith(ext))) return false;
    if (file.size > maxFileSize) {
      alert("File size exceeds 50 MB limit.");
      return false;
    }
    return true;
  };

  const uploadFile = (file) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("csrf_token", $("#csrf_token").val());

    const currentUrl = window.location.href.split("?")[0].split("#")[0];
    const uploadUrl = currentUrl.replace(/\/$/, "") + "/upload";

    const fileSize = (file.size / 1024).toFixed(2);
    const fileItem = $('<div class="file-item"></div>');
    $("<strong></strong>").text(file.name).appendTo(fileItem);
    fileItem.append(document.createTextNode(` (${fileSize} KB)`));
    fileList.append(fileItem);

    const progressBar = $(
      '<div class="progress-bar" role="progressbar" style="width: 0%;"></div>',
    );
    const progress = $('<div class="progress mt-2"></div>').append(progressBar);
    fileList.append(progress);

    $.ajax({
      url: uploadUrl,
      type: "POST",
      data: formData,
      processData: false,
      contentType: false,
      xhr: function () {
        const xhr = new window.XMLHttpRequest();
        xhr.upload.addEventListener(
          "progress",
          (evt) => {
            if (evt.lengthComputable) {
              const percentComplete = (evt.loaded / evt.total) * 100;
              progressBar.css("width", percentComplete + "%");
              progressBar.attr("aria-valuenow", percentComplete);
            }
          },
          false,
        );
        return xhr;
      },
      success: function () {
        progressBar.addClass("bg-success");
        $("#add-plugins-submit").removeClass("disabled");
        fileItem.append('<span class="text-success ms-2">Uploaded</span>');
      },
      error: function () {
        progressBar.addClass("bg-danger");
        fileItem.append('<span class="text-danger ms-2">Failed</span>');
        alert("An error occurred while uploading the file. Please try again.");
      },
    });
  };

  dragArea.on("click", () => fileInput.click());
  dragArea.on("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      fileInput.click();
    }
  });
  dragArea.on("dragover", (e) => {
    e.preventDefault();
    dragArea.removeClass("border-dashed").addClass("bg-primary text-white");
    dragArea.find("i").removeClass("text-primary");
  });
  dragArea.on("dragleave", (e) => {
    e.preventDefault();
    dragArea.addClass("border-dashed").removeClass("bg-primary text-white");
    dragArea.find("i").addClass("text-primary");
  });
  fileInput.on("change", function () {
    const files = this.files;
    for (let i = 0; i < files.length; i++) {
      setTimeout(() => {
        const file = files[i];
        if (validateFile(file)) uploadFile(file);
        else
          alert("Please upload a valid plugin file (.zip, .tar.gz, .tar.xz).");
      }, 500 * i);
    }
  });
  dragArea.on("drop", function (e) {
    e.preventDefault();
    dragArea.addClass("border-dashed").removeClass("bg-primary text-white");
    dragArea.find("i").addClass("text-primary");
    fileInput.prop("files", e.originalEvent.dataTransfer.files);
    fileInput.trigger("change");
  });
});
