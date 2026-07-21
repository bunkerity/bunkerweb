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
    const label = certificate?.common_name || certificate?.name || "";
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
});
