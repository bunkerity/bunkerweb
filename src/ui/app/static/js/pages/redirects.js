document.addEventListener("DOMContentLoaded", () => {
  const dataElement = document.getElementById("redirects-data");
  const redirects = new Map(
    JSON.parse(dataElement?.value || "[]").map((rule) => [rule.id, rule]),
  );
  const rows = Array.from(document.querySelectorAll(".redirect-row"));
  const translate = (key, fallback, options = {}) =>
    typeof i18next === "undefined"
      ? fallback
      : i18next.t(key, { defaultValue: fallback, ...options });

  const modals = {};
  const modalFor = (id) => {
    if (typeof bootstrap === "undefined") return null;
    if (!modals[id]) {
      const element = document.getElementById(id);
      if (!element) return null;
      modals[id] = { instance: new bootstrap.Modal(element), element };
    }
    return modals[id];
  };

  function showModal(id, trigger) {
    const modal = modalFor(id);
    if (!modal) return;
    if (trigger instanceof HTMLElement) {
      modal.element.addEventListener(
        "hidden.bs.modal",
        () => {
          if (trigger.isConnected) trigger.focus();
        },
        { once: true },
      );
    }
    modal.instance.show(trigger);
  }

  function updateSharedBanner(rule) {
    // The rule is shared: editing it changes every service it is attached to, so say how
    // many and which ones before the operator saves.
    const shared = document.getElementById("redirect-edit-shared");
    const services = rule?.services || [];
    shared.classList.toggle("d-none", services.length === 0);
    if (services.length) {
      shared.textContent = translate(
        "redirects.edit_shared",
        `This redirect is attached to ${services.length} service(s): ${services.join(", ")}. Saving changes all of them.`,
        { count: services.length, services: services.join(", ") },
      );
    }
  }

  function fillEditForm(rule) {
    document.getElementById("redirect-edit-id").value = rule.id;
    document.getElementById("redirect-edit-name").value = rule.name || "";
    document.getElementById("redirect-edit-from-path").value =
      rule.from_path || "/";
    document.getElementById("redirect-edit-to-url").value = rule.to_url || "";
    document.getElementById("redirect-edit-status-code").value =
      rule.status_code || "301";
    document.getElementById("redirect-edit-description").value =
      rule.description || "";
    document.getElementById("redirect-edit-append-uri").checked = Boolean(
      rule.append_request_uri,
    );
    updateSharedBanner(rule);
  }

  function openAttach(rule, trigger) {
    document.getElementById("redirect-attach-id").value = rule.id;
    document.getElementById("redirect-attach-copy").textContent = translate(
      "redirects.attach_copy",
      `Attach ${rule.name} (${rule.from_path} → ${rule.to_url}) to one or more services.`,
      { name: rule.name, from: rule.from_path, to: rule.to_url },
    );
    // Already-attached services would be refused as duplicates, so hide them.
    const select = document.getElementById("redirect-attach-services");
    Array.from(select.options).forEach((option) => {
      option.hidden = (rule.services || []).includes(option.value);
      if (option.hidden) option.selected = false;
    });
    showModal("redirect-attach-modal", trigger);
  }

  // The count in the Services column opens this viewer: every attachment stays an explicit
  // Detach (its own POST, as before) and Attach, with the shared-impact warning beside them.
  function openServices(rule, trigger) {
    const list = document.getElementById("redirect-services-list");
    const attachButton = document.getElementById("redirect-services-attach");
    const readonly = attachButton.disabled;
    document.getElementById("redirect-services-copy").textContent = translate(
      "redirects.services_copy",
      `${rule.name}: ${rule.from_path} → ${rule.to_url}`,
      { name: rule.name, from: rule.from_path, to: rule.to_url },
    );
    document.getElementById("redirect-services-shared").textContent = translate(
      "redirects.detach_shared",
      "This redirect is shared. Detaching it removes it from that service only; the other services keep it.",
    );
    list.replaceChildren();
    (rule.services || []).forEach((serviceId) => {
      const item = document.createElement("li");
      item.className =
        "list-group-item d-flex align-items-center justify-content-between gap-2 px-0";
      const code = document.createElement("span");
      code.className = "svc-code";
      code.textContent = serviceId;
      item.append(code);
      if (!readonly) {
        const form = document.createElement("form");
        form.method = "post";
        form.action = list.dataset.detachUrl;
        [
          ["csrf_token", list.dataset.csrf],
          ["redirect_id", rule.id],
          ["service_id", serviceId],
        ].forEach(([name, value]) => {
          const input = document.createElement("input");
          input.type = "hidden";
          input.name = name;
          input.value = value;
          form.append(input);
        });
        const button = document.createElement("button");
        button.type = "submit";
        button.className = "btn btn-sm btn-outline-danger";
        const label = translate(
          "aria.label.detach_from_service",
          `Detach ${rule.name} from ${serviceId}`,
          { name: rule.name, service: serviceId },
        );
        button.setAttribute("aria-label", label);
        button.title = label;
        const icon = document.createElement("i");
        icon.className = "bx bx-unlink";
        icon.setAttribute("aria-hidden", "true");
        const text = document.createElement("span");
        text.className = "ms-1";
        text.textContent = translate("service.resources.detach", "Detach");
        button.append(icon, text);
        form.append(button);
        item.append(form);
      }
      list.append(item);
    });
    attachButton.onclick = () => {
      const services = modalFor("redirect-services-modal");
      services?.element.addEventListener(
        "hidden.bs.modal",
        () => openAttach(rule, trigger),
        { once: true },
      );
      services?.instance.hide();
    };
    showModal("redirect-services-modal", trigger);
  }

  rows.forEach((row) => {
    const rule = redirects.get(row.dataset.redirectId);
    if (!rule) return;

    row.querySelector(".redirect-edit")?.addEventListener("click", (event) => {
      fillEditForm(rule);
      showModal("redirect-edit-modal", event.currentTarget);
    });

    row
      .querySelector(".redirect-attach")
      ?.addEventListener("click", (event) =>
        openAttach(rule, event.currentTarget),
      );

    row
      .querySelector(".redirect-services")
      ?.addEventListener("click", (event) =>
        openServices(rule, event.currentTarget),
      );

    row
      .querySelector(".redirect-delete")
      ?.addEventListener("click", (event) => {
        document.getElementById("redirect-delete-id").value = rule.id;
        document.getElementById("redirect-delete-copy").textContent = translate(
          "redirects.delete_copy",
          `Delete the redirect ${rule.name}?`,
          { name: rule.name },
        );
        showModal("redirect-delete-modal", event.currentTarget);
      });
  });

  const searchInput = document.getElementById("redirects-search");
  const codeFilter = document.getElementById("redirects-status-filter");
  const noMatch = document.getElementById("redirects-no-match");

  function applyFilters() {
    const term = (searchInput?.value || "").trim().toLowerCase();
    const code = codeFilter?.value || "";
    let visible = 0;
    rows.forEach((row) => {
      const rule = redirects.get(row.dataset.redirectId) || {};
      const haystack =
        `${rule.name || ""} ${rule.description || ""} ${rule.from_path || ""} ${rule.to_url || ""}`.toLowerCase();
      const matches =
        (!term || haystack.includes(term)) &&
        (!code || String(rule.status_code) === code);
      row.hidden = !matches;
      if (matches) visible += 1;
    });
    if (noMatch) noMatch.hidden = visible > 0 || rows.length === 0;
  }

  searchInput?.addEventListener("input", applyFilters);
  codeFilter?.addEventListener("change", applyFilters);
  document
    .getElementById("redirects-search-clear")
    ?.addEventListener("click", () => {
      if (searchInput) searchInput.value = "";
      applyFilters();
    });

  // A create or edit the server refused comes back with ?retry=create|edit: reopen the modal
  // with what was typed instead of making the operator start over. The input stays in this
  // tab's sessionStorage, never in the URL.
  function wireRetry(form, modalId, draftKey, retryValue, onRestore) {
    form?.addEventListener("submit", () => {
      try {
        sessionStorage.setItem(
          draftKey,
          JSON.stringify(
            Array.from(new FormData(form)).filter(
              ([name]) => name !== "csrf_token",
            ),
          ),
        );
      } catch (error) {
        // Storage refused (private mode, quota): the submit still goes through.
      }
    });
    let draft = null;
    try {
      draft = JSON.parse(sessionStorage.getItem(draftKey) || "null");
      sessionStorage.removeItem(draftKey);
    } catch (error) {
      draft = null;
    }
    if (form && draft && url.searchParams.get("retry") === retryValue) {
      Array.from(form.elements).forEach((field) => {
        if (!field.name || field.name === "csrf_token") return;
        const values = draft
          .filter(([name]) => name === field.name)
          .map(([, value]) => value);
        if (field.type === "checkbox")
          field.checked = values.includes(field.value);
        else if (field.multiple)
          Array.from(field.options).forEach((option) => {
            option.selected = values.includes(option.value);
          });
        else if (values.length) field.value = values[0];
      });
      onRestore?.();
      showModal(modalId);
    }
  }

  const url = new URL(window.location.href);
  wireRetry(
    document.querySelector("#redirect-create-modal form"),
    "redirect-create-modal",
    "bw-redirect-create-draft",
    "create",
  );
  const editForm = document.querySelector("#redirect-edit-modal form");
  wireRetry(
    editForm,
    "redirect-edit-modal",
    "bw-redirect-edit-draft",
    "edit",
    () =>
      updateSharedBanner(
        redirects.get(editForm.elements["redirect_id"]?.value),
      ),
  );
  if (url.searchParams.has("retry")) {
    url.searchParams.delete("retry");
    window.history.replaceState(null, "", url);
  }
});
