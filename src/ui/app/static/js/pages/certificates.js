document.addEventListener("DOMContentLoaded", () => {
  const dataElement = document.getElementById("certificates-data");
  const certificates = new Map(
    JSON.parse(dataElement?.value || "[]").map((certificate) => [
      certificate.id,
      certificate,
    ]),
  );
  const rows = Array.from(document.querySelectorAll(".certificate-row"));
  const translate = (key, fallback, options = {}) =>
    typeof i18next === "undefined"
      ? fallback
      : i18next.t(key, { defaultValue: fallback, ...options });

  function showModal(modal, element, trigger) {
    if (!modal || !element) return;
    if (trigger instanceof HTMLElement) {
      element.addEventListener(
        "hidden.bs.modal",
        () => {
          if (trigger.isConnected) trigger.focus();
        },
        { once: true },
      );
    }
    modal.show(trigger);
  }

  function detailsFor(row) {
    const details = row.nextElementSibling;
    return details?.classList.contains("certificate-details") ? details : null;
  }

  function setExpanded(row, expanded) {
    const details = detailsFor(row);
    const toggle = row.querySelector(".certificate-toggle");
    if (!details || !toggle) return;
    details.hidden = !expanded;
    toggle.setAttribute("aria-expanded", String(expanded));
    toggle.querySelector("i")?.classList.toggle("bx-rotate-90", expanded);
  }

  rows.forEach((row) => {
    setExpanded(row, false);
    row.querySelector(".certificate-toggle")?.addEventListener("click", () => {
      setExpanded(row, Boolean(detailsFor(row)?.hidden));
    });
  });

  const dateFormatter = new Intl.DateTimeFormat(document.documentElement.lang, {
    dateStyle: "medium",
    timeStyle: "short",
  });
  document.querySelectorAll(".certificate-date").forEach((element) => {
    const original = element.getAttribute("datetime");
    const date = new Date(original);
    if (!original || Number.isNaN(date.getTime())) return;
    element.textContent = dateFormatter.format(date);
    element.title = original;
  });

  const search = document.getElementById("certificates-search");
  const sourceFilter = document.getElementById("certificates-source-filter");
  const statusFilter = document.getElementById("certificates-status-filter");
  const serviceFilter = document.getElementById("certificates-service-filter");
  const count = document.getElementById("certificates-count");

  function applyFilters() {
    const query = search?.value.trim().toLocaleLowerCase() || "";
    const source = sourceFilter?.value || "";
    const status = statusFilter?.value || "";
    const service = serviceFilter?.value || "";
    let visible = 0;

    rows.forEach((row) => {
      const details = detailsFor(row);
      const certificate = certificates.get(row.dataset.certificateId);
      const searchable = `${row.textContent} ${details?.textContent || ""}`
        .trim()
        .toLocaleLowerCase();
      const attached = (certificate?.attachments || []).some(
        (attachment) => attachment.service_id === service,
      );
      const matches =
        (!query || searchable.includes(query)) &&
        (!source || row.dataset.source === source) &&
        (!status || row.dataset.status === status) &&
        (!service || attached);

      row.hidden = !matches;
      if (!matches) setExpanded(row, false);
      visible += Number(matches);
    });

    if (count)
      count.textContent = translate(
        "certificates.showing_count",
        `Showing ${visible} of ${rows.length} certificates`,
        { visible, total: rows.length },
      );
    syncSelection();
    syncFilterCount();
  }

  search?.addEventListener("input", applyFilters);
  [sourceFilter, statusFilter, serviceFilter].forEach((filter) =>
    filter?.addEventListener("change", applyFilters),
  );
  document
    .getElementById("certificates-search-clear")
    ?.addEventListener("click", () => {
      search.value = "";
      search.focus();
      applyFilters();
    });

  function certificateFor(button) {
    const owner = button.closest("[data-certificate-id]");
    return certificates.get(owner?.dataset.certificateId);
  }

  const editModalElement = document.getElementById("certificate-edit-modal");
  const editModal = editModalElement
    ? bootstrap.Modal.getOrCreateInstance(editModalElement)
    : null;
  document.querySelectorAll(".certificate-edit").forEach((button) => {
    button.addEventListener("click", () => {
      const certificate = certificateFor(button);
      if (!certificate || !editModal) return;
      document.getElementById("certificate-edit-id").value = certificate.id;
      document.getElementById("certificate-edit-name").value =
        certificate.name || "";
      document.getElementById("certificate-edit-description").value =
        certificate.description || "";
      showModal(editModal, editModalElement, button);
    });
  });

  const attachModalElement = document.getElementById(
    "certificate-attach-modal",
  );
  const attachModal = attachModalElement
    ? bootstrap.Modal.getOrCreateInstance(attachModalElement)
    : null;
  document.querySelectorAll(".certificate-attach").forEach((button) => {
    button.addEventListener("click", () => {
      const certificate = certificateFor(button);
      if (!certificate || !attachModal) return;
      const attached = new Set(
        certificate.attachments.map((attachment) => attachment.service_id),
      );
      const select = document.getElementById("certificate-attach-service");
      const available = Array.from(select.options).filter((option) => {
        option.disabled = Boolean(option.value && attached.has(option.value));
        return option.value && !option.disabled;
      });
      select.value = available[0]?.value || "";
      attachModalElement.querySelector('button[type="submit"]').disabled =
        !available.length;
      document.getElementById("certificate-attach-id").value = certificate.id;
      document.getElementById("certificate-attach-copy").textContent =
        available.length
          ? translate(
              "certificates.attach_copy",
              `Assign “${certificate.common_name || certificate.name}” to a service in the central inventory.`,
              { name: certificate.common_name || certificate.name },
            )
          : translate(
              "certificates.attach_all",
              "This certificate is already attached to every available service.",
            );
      showModal(attachModal, attachModalElement, button);
    });
  });

  const actionModalElement = document.getElementById(
    "certificate-action-modal",
  );
  const actionModal = actionModalElement
    ? bootstrap.Modal.getOrCreateInstance(actionModalElement)
    : null;
  const actionId = document.getElementById("certificate-action-id");
  const actionName = document.getElementById("certificate-action-name");
  const actionSource = document.getElementById("certificate-action-source");
  const actionCopy = document.getElementById("certificate-action-copy");
  const renewDays = document.getElementById("certificate-renew-days");
  const renewDaysInput = document.getElementById(
    "certificate-action-valid-days",
  );
  const actionSubmit = document.getElementById("certificate-action-submit");

  function openAction(action, certificate = null, trigger = null) {
    if (!actionModal) return;
    const label = certificate?.name || certificate?.common_name || "";
    const copies = {
      renew: translate("certificates.confirm_renew", `Renew “${label}”?`, {
        name: label,
      }),
      delete: translate(
        "certificates.confirm_delete",
        `Delete “${label}”? This cannot be undone.`,
        { name: label },
      ),
      renew_due: translate(
        "certificates.confirm_renew_due",
        "Check every certificate and renew those currently due?",
      ),
    };
    const destructive = action === "delete";
    actionId.value = certificate?.id || "";
    actionName.value = action;
    actionSource.value = certificate?.source || "";
    actionCopy.textContent =
      copies[action] ||
      translate(
        "certificates.confirm_generic",
        "Confirm this certificate action?",
      );
    renewDays.hidden =
      action !== "renew" || certificate?.source !== "selfsigned";
    renewDaysInput.disabled = renewDays.hidden;
    actionSubmit.classList.toggle("btn-danger", destructive);
    actionSubmit.classList.toggle("btn-primary", !destructive);
    actionSubmit.classList.toggle("don-jose", !destructive);
    showModal(actionModal, actionModalElement, trigger);
  }

  ["renew", "delete"].forEach((action) => {
    document.querySelectorAll(`.certificate-${action}`).forEach((button) => {
      button.addEventListener("click", () =>
        openAction(action, certificateFor(button), button),
      );
    });
  });
  const renewDue = document.getElementById("certificates-renew-due");
  renewDue?.addEventListener("click", () =>
    openAction("renew_due", null, renewDue),
  );

  const maxUploadBytes = 1024 * 1024;
  const uploadError = document.getElementById("certificate-upload-error");

  function validateFile(input, feedbackId, extensions) {
    if (!input) return false;
    const file = input.files?.[0];
    const feedback = document.getElementById(feedbackId);
    const dropzone = document.querySelector(`[data-file-input="#${input.id}"]`);
    let error = "";
    if (!file)
      error = translate("certificates.file_select", "Select a PEM file.");
    else if (file.size > maxUploadBytes)
      error = translate(
        "certificates.file_size_limit",
        "The file must not exceed 1 MiB.",
      );
    else if (
      !extensions.some((extension) =>
        file.name.toLocaleLowerCase().endsWith(extension),
      )
    )
      error = translate(
        "certificates.file_extensions",
        `Use one of these file extensions: ${extensions.join(", ")}.`,
        { extensions: extensions.join(", ") },
      );

    dropzone?.classList.toggle("is-invalid", Boolean(error));
    dropzone?.setAttribute("aria-invalid", String(Boolean(error)));
    if (feedback) {
      feedback.setAttribute("aria-live", "polite");
      feedback.classList.toggle("text-danger", Boolean(error));
      feedback.classList.toggle("text-success", Boolean(file && !error));
      feedback.textContent =
        error ||
        translate(
          "certificates.file_selected",
          `${file.name} (${Math.ceil(file.size / 1024)} KiB)`,
          { name: file.name, size: Math.ceil(file.size / 1024) },
        );
    }
    return !error;
  }

  const certificateFile = document.getElementById("certificate-pem-input");
  const keyFile = document.getElementById("certificate-key-input");
  certificateFile?.addEventListener("change", () => {
    validateFile(certificateFile, "certificate-pem-feedback", [
      ".pem",
      ".crt",
      ".cer",
    ]);
    if (uploadError) uploadError.hidden = true;
  });
  keyFile?.addEventListener("change", () => {
    validateFile(keyFile, "certificate-key-feedback", [".pem", ".key"]);
    if (uploadError) uploadError.hidden = true;
  });
  document
    .getElementById("certificate-upload-form")
    ?.addEventListener("submit", (event) => {
      const certificateValid = validateFile(
        certificateFile,
        "certificate-pem-feedback",
        [".pem", ".crt", ".cer"],
      );
      const keyValid = validateFile(keyFile, "certificate-key-feedback", [
        ".pem",
        ".key",
      ]);
      if (certificateValid && keyValid) return;
      event.preventDefault();
      uploadError.textContent = translate(
        "certificates.upload_invalid",
        "Choose a valid public certificate and its matching private key.",
      );
      uploadError.hidden = false;
      document.querySelector("#certificate-upload-modal .is-invalid")?.focus();
    });
  // --- Table toolbar: selection, columns, export, bulk actions, filters panel -------------------
  // The page is a static table, not a DataTable, so these mirror the shared toolbar by hand and
  // only call endpoints that already exist (/certificates/action, /certificates/<id>/download).
  const table = document.querySelector(".certificates-table");
  const announce = (text) => {
    const region = document.getElementById("certificates-live");
    if (region) region.textContent = text;
  };
  const baseUrl = window.location.pathname.replace(/\/+$/, "");
  const selectAll = document.getElementById("certificates-select-all");
  const actionsButton = document.getElementById("certificates-actions-btn");
  const actionsWrap = document.getElementById("certificates-actions-wrap");
  const actionsTip = actionsWrap
    ? bootstrap.Tooltip.getOrCreateInstance(actionsWrap)
    : null;

  const isSelected = (row) =>
    Boolean(row.querySelector(".certificate-select")?.checked);
  const selectedCertificates = () =>
    rows
      .filter((row) => !row.hidden && isSelected(row))
      .map((row) => certificates.get(row.dataset.certificateId))
      .filter(Boolean);

  function syncSelection() {
    if (!selectAll) return;
    const visible = rows.filter((row) => !row.hidden);
    const chosen = visible.filter(isSelected);
    selectAll.checked = visible.length > 0 && chosen.length === visible.length;
    selectAll.indeterminate =
      chosen.length > 0 && chosen.length < visible.length;
    const none = chosen.length === 0;
    actionsButton?.setAttribute("aria-disabled", String(none));
    if (none) actionsTip?.enable();
    else actionsTip?.disable();
  }

  // aria-disabled (not disabled) keeps the button focusable so its tooltip stays reachable.
  actionsButton?.addEventListener("click", (event) => {
    if (actionsButton.getAttribute("aria-disabled") === "true") {
      event.preventDefault();
      event.stopPropagation();
    }
  });
  selectAll?.addEventListener("change", () => {
    rows
      .filter((row) => !row.hidden)
      .forEach((row) => {
        const box = row.querySelector(".certificate-select");
        if (box) box.checked = selectAll.checked;
      });
    syncSelection();
  });
  rows.forEach((row) =>
    row
      .querySelector(".certificate-select")
      ?.addEventListener("change", syncSelection),
  );

  // Columns popover: every data column but the toggle, checkbox and actions cells.
  const COLUMNS_KEY = "bw-certificates-columns";
  const headCells = table ? Array.from(table.querySelectorAll("thead th")) : [];
  const toggleable = headCells
    .map((cell, index) => index)
    .filter((index) => index >= 2 && index < headCells.length - 1);
  let hiddenColumns = new Set();
  try {
    hiddenColumns = new Set(
      JSON.parse(localStorage.getItem(COLUMNS_KEY) || "[]").filter((index) =>
        toggleable.includes(index),
      ),
    );
  } catch (error) {
    hiddenColumns = new Set();
  }
  if (hiddenColumns.size >= toggleable.length) hiddenColumns = new Set();
  const columnsList = document.getElementById("certificates-columns-list");

  function applyColumns() {
    rows.forEach((row) =>
      toggleable.forEach((index) =>
        row.cells[index]?.classList.toggle("d-none", hiddenColumns.has(index)),
      ),
    );
    toggleable.forEach((index) =>
      headCells[index].classList.toggle("d-none", hiddenColumns.has(index)),
    );
    try {
      localStorage.setItem(COLUMNS_KEY, JSON.stringify([...hiddenColumns]));
    } catch (error) {
      // Private mode: the choice just does not persist.
    }
    if (!columnsList) return;
    const visibleCount = toggleable.length - hiddenColumns.size;
    document.getElementById("certificates-columns-count").textContent =
      translate(
        "table_system.column_count",
        `${visibleCount} of ${toggleable.length}`,
        {
          visible: visibleCount,
          total: toggleable.length,
        },
      );
    columnsList.replaceChildren(
      ...toggleable.map((index) => {
        const label = document.createElement("label");
        label.className = "dropdown-item d-flex align-items-center gap-2";
        const box = document.createElement("input");
        box.type = "checkbox";
        box.checked = !hiddenColumns.has(index);
        // At least one data column always stays visible.
        box.disabled = box.checked && visibleCount === 1;
        box.addEventListener("change", () => {
          if (box.checked) hiddenColumns.delete(index);
          else hiddenColumns.add(index);
          applyColumns();
        });
        const text = document.createElement("span");
        text.textContent = headCells[index].textContent.trim();
        label.append(box, text);
        return label;
      }),
    );
  }
  document
    .getElementById("certificates-columns-all")
    ?.addEventListener("click", () => {
      hiddenColumns.clear();
      applyColumns();
    });
  applyColumns();

  // Export what is on screen: visible rows, visible columns.
  function cellValue(row, index) {
    const certificate = certificates.get(row.dataset.certificateId);
    if (index === 2) return certificate?.name || "";
    if (index === 8)
      return (certificate?.attachments || [])
        .map((attachment) => attachment.service_id)
        .join(" ");
    const cell = row.cells[index];
    const time = cell?.querySelector("time");
    return (time?.getAttribute("datetime") || cell?.textContent || "")
      .replace(/\s+/g, " ")
      .trim();
  }
  function exportMatrix() {
    const columns = toggleable.filter((index) => !hiddenColumns.has(index));
    return [
      columns.map((index) => headCells[index].textContent.trim()),
      ...rows
        .filter((row) => !row.hidden)
        .map((row) => columns.map((index) => cellValue(row, index))),
    ];
  }
  document
    .getElementById("certificates-export-csv")
    ?.addEventListener("click", () => {
      // A cell starting with = + - @ would be run as a formula by a spreadsheet.
      const quote = (value) =>
        `"${(/^[=+\-@\t\r]/.test(value) ? `'${value}` : value).replace(/"/g, '""')}"`;
      const csv = exportMatrix()
        .map((line) => line.map(quote).join(","))
        .join("\r\n");
      const link = document.createElement("a");
      link.href = URL.createObjectURL(
        new Blob(["\ufeff", csv], { type: "text/csv;charset=utf-8" }),
      );
      link.download = "bw_certificates.csv";
      link.click();
      setTimeout(() => URL.revokeObjectURL(link.href), 1000);
    });
  document
    .getElementById("certificates-export-copy")
    ?.addEventListener("click", async () => {
      const text = exportMatrix()
        .map((line) => line.join("\t"))
        .join("\n");
      try {
        await navigator.clipboard.writeText(text);
        announce(translate("toast.copied", "Copied!"));
      } catch (error) {
        console.error(error);
      }
    });

  // Bulk actions follow the same per-source rules as the row buttons.
  const actionForm = document.getElementById("certificate-action-form");
  async function runBulk(
    action,
    eligible,
    skipped,
    confirmKey,
    confirmFallback,
  ) {
    if (!eligible.length) {
      announce(
        translate(
          "certificates.bulk.none_eligible",
          "None of the selected certificates can take this action.",
        ),
      );
      return;
    }
    const message = [
      translate(confirmKey, confirmFallback, { count: eligible.length }),
      skipped
        ? translate(
            "certificates.bulk.skipped",
            `Selected certificates that cannot take this action, skipped: ${skipped}.`,
            { skipped },
          )
        : "",
    ]
      .filter(Boolean)
      .join(" ");
    const confirmed = await window.BWConfirm.open({
      title: translate(
        "certificates.confirm_action",
        "Confirm certificate action",
      ),
      message,
      destructive: action === "delete",
    });
    if (!confirmed || !actionForm) return;
    const token = actionForm.querySelector('input[name="csrf_token"]').value;
    for (const certificate of eligible) {
      try {
        // One request per certificate on the existing endpoint; the redirect (and the flash it
        // carries) is not followed, the page reloads once at the end.
        await fetch(actionForm.action, {
          method: "POST",
          body: new URLSearchParams({
            csrf_token: token,
            action,
            certificate_id: certificate.id,
            source: certificate.source,
          }),
          credentials: "same-origin",
          redirect: "manual",
        });
      } catch (error) {
        console.error(error);
        break;
      }
    }
    window.location.reload();
  }
  document
    .getElementById("certificates-bulk-renew")
    ?.addEventListener("click", () => {
      const chosen = selectedCertificates();
      const eligible = chosen.filter((item) => item.source === "selfsigned");
      runBulk(
        "renew",
        eligible,
        chosen.length - eligible.length,
        "certificates.bulk.confirm_renew",
        `Self-signed certificates to renew: ${eligible.length}. Continue?`,
      );
    });
  document
    .getElementById("certificates-bulk-delete")
    ?.addEventListener("click", () => {
      const chosen = selectedCertificates();
      const eligible = chosen.filter(
        (item) => item.source !== "letsencrypt" && !item.attachments.length,
      );
      runBulk(
        "delete",
        eligible,
        chosen.length - eligible.length,
        "certificates.bulk.confirm_delete",
        `Certificates to delete: ${eligible.length}. This cannot be undone. Continue?`,
      );
    });
  document
    .getElementById("certificates-bulk-download")
    ?.addEventListener("click", async () => {
      for (const certificate of selectedCertificates()) {
        const link = document.createElement("a");
        link.href = `${baseUrl}/${encodeURIComponent(certificate.id)}/download/chain`;
        link.click();
        // Browsers drop downloads fired in the same tick.
        await new Promise((resolve) => setTimeout(resolve, 400));
      }
    });

  // Filters panel: the three selects keep their ids and behavior; the button shows how many are set.
  const filtersToggle = document.getElementById("certificates-filters-toggle");
  const filtersPanel = document.getElementById("certificates-filters");
  const filtersCount = document.getElementById("certificates-filters-count");
  filtersToggle?.addEventListener("click", () => {
    const open = filtersPanel.hidden;
    filtersPanel.hidden = !open;
    filtersToggle.setAttribute("aria-expanded", String(open));
  });
  function syncFilterCount() {
    if (!filtersCount) return;
    const active = [sourceFilter, statusFilter, serviceFilter].filter(
      (filter) => filter?.value,
    ).length;
    filtersCount.hidden = active === 0;
    filtersCount.textContent = String(active);
    filtersToggle.setAttribute(
      "aria-label",
      active
        ? translate(
            "table_system.active_filters",
            `Filters, ${active} active`,
            {
              count: active,
            },
          )
        : translate("table_system.filters", "Filters"),
    );
  }
  document
    .getElementById("certificates-filters-reset")
    ?.addEventListener("click", () => {
      [sourceFilter, statusFilter, serviceFilter].forEach((filter) => {
        if (filter) filter.value = "";
      });
      applyFilters();
    });

  // Top issuers: ranked table, Detail dialog holds the full list.
  const issuersHost = document.getElementById("certificates-issuers");
  if (issuersHost && window.BWTopTable) {
    let issuers = [];
    try {
      issuers = JSON.parse(
        document.getElementById("certificates-issuers-data")?.value || "[]",
      );
    } catch (error) {
      issuers = [];
    }
    const total = issuers.reduce((sum, [, amount]) => sum + amount, 0);
    const items = issuers.map(([issuer, amount]) => ({
      label: issuer,
      pct: total ? Math.round((amount / total) * 100) : 0,
    }));
    const options = {
      head: {
        label: translate("certificates.issuer", "Issuer"),
        share: translate("tables.top.share", "Share"),
      },
      caption: translate("certificates.issuers", "Top issuers"),
    };
    window.BWTopTable.render($(issuersHost), {
      ...options,
      items: items.slice(0, 6),
      detailLabel: translate("tables.top.detail", "Detail"),
      onDetail: () =>
        window.BWTopTable.openDetail({
          ...options,
          items,
          title: options.caption,
          meta: translate(
            "certificates.issuers_meta",
            `${total} certificates`,
            {
              count: total,
            },
          ),
          closeLabel: translate("button.close", "Close"),
        }),
    });
  }
  syncSelection();
  syncFilterCount();
});
