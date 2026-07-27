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

    // The rule is shared: editing it changes every service it is attached to, so say how
    // many and which ones before the operator saves.
    const shared = document.getElementById("redirect-edit-shared");
    const services = rule.services || [];
    shared.classList.toggle("d-none", services.length === 0);
    if (services.length) {
      shared.textContent = translate(
        "redirects.edit_shared",
        `This redirect is attached to ${services.length} service(s): ${services.join(", ")}. Saving changes all of them.`,
        { count: services.length, services: services.join(", ") },
      );
    }
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
      ?.addEventListener("click", (event) => {
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
        showModal("redirect-attach-modal", event.currentTarget);
      });

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
  const serviceFilter = document.getElementById("redirects-service-filter");

  function applyFilters() {
    const term = (searchInput?.value || "").trim().toLowerCase();
    const service = serviceFilter?.value || "";
    rows.forEach((row) => {
      const rule = redirects.get(row.dataset.redirectId) || {};
      const haystack =
        `${rule.name || ""} ${rule.from_path || ""} ${rule.to_url || ""}`.toLowerCase();
      const matchesTerm = !term || haystack.includes(term);
      const matchesService =
        !service || (rule.services || []).includes(service);
      row.hidden = !(matchesTerm && matchesService);
    });
  }

  searchInput?.addEventListener("input", applyFilters);
  serviceFilter?.addEventListener("change", applyFilters);
  document
    .getElementById("redirects-search-clear")
    ?.addEventListener("click", () => {
      if (searchInput) searchInput.value = "";
      applyFilters();
    });
});
