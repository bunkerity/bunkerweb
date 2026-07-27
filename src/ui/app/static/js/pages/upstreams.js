document.addEventListener("DOMContentLoaded", () => {
  const dataElement = document.getElementById("upstreams-data");
  const upstreams = new Map(
    JSON.parse(dataElement?.value || "[]").map((pool) => [pool.id, pool]),
  );
  const rows = Array.from(document.querySelectorAll(".upstream-row"));
  const serverTemplate = document.getElementById("upstream-server-template");
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

  function newServerRow() {
    return serverTemplate.content.firstElementChild.cloneNode(true);
  }

  // A stream pool takes a whole TCP/UDP service and an http/gRPC pool takes a path on an HTTP
  // one, so offering the wrong services is offering an attach the API will refuse. Hide them
  // instead, and say how many were hidden so the list never looks mysteriously short.
  function applyProtocol(protocol, selectId, hintId, pathFieldId) {
    const select = document.getElementById(selectId);
    if (select) {
      let hidden = 0;
      Array.from(select.options).forEach((option) => {
        const isStreamService = option.dataset.serverType === "stream";
        option.hidden = isStreamService !== (protocol === "stream");
        if (option.hidden) {
          option.selected = false;
          hidden += 1;
        }
      });
      const hint = document.getElementById(hintId);
      if (hint) {
        hint.classList.toggle("d-none", hidden === 0);
        hint.textContent = translate(
          "upstreams.services_hidden",
          `${hidden} service(s) hidden: a ${protocol} upstream can only be attached to a ${protocol === "stream" ? "stream" : "HTTP"} service.`,
          { count: hidden, protocol },
        );
      }
    }
    // A stream server has no location, so the path field would be a lie.
    const pathField = document.getElementById(pathFieldId);
    if (pathField) {
      pathField.closest(".col-md-4, .mt-3")?.classList.toggle("d-none", protocol === "stream");
    }
  }

  function fillServerRow(row, server) {
    row.querySelector("[name=server_host]").value = server.host || "";
    row.querySelector("[name=server_weight]").value = server.weight ?? 1;
    row.querySelector("[name=server_max_fails]").value = server.max_fails ?? 1;
    row.querySelector("[name=server_fail_timeout]").value =
      server.fail_timeout || "10s";
    row.querySelector("[name=server_role]").value = server.backup
      ? "backup"
      : server.down
        ? "down"
        : "primary";
  }

  function setServers(container, servers) {
    container.replaceChildren();
    const list = servers && servers.length ? servers : [{}];
    list.forEach((server) => {
      const row = newServerRow();
      fillServerRow(row, server);
      container.appendChild(row);
    });
  }

  // One delegated listener for both modals: rows are cloned at runtime, so binding per row
  // would miss every server added after load.
  document.addEventListener("click", (event) => {
    const addButton = event.target.closest(".upstream-server-add");
    if (addButton) {
      event.preventDefault();
      const container = addButton
        .closest(".col-12")
        ?.querySelector(".upstream-servers");
      container?.appendChild(newServerRow());
      return;
    }

    const removeButton = event.target.closest(".upstream-server-remove");
    if (removeButton) {
      event.preventDefault();
      const container = removeButton.closest(".upstream-servers");
      // Never remove the last row: an upstream with no server is refused by the API, and an
      // empty editor gives the operator nothing to type into.
      if (container && container.children.length > 1) {
        removeButton.closest(".upstream-server-row").remove();
      }
    }
  });

  function fillEditForm(pool) {
    document.getElementById("upstream-edit-id").value = pool.id;
    document.getElementById("upstream-edit-name").value = pool.name || "";
    document.getElementById("upstream-edit-protocol").value =
      pool.protocol || "http";
    document.getElementById("upstream-edit-backend-ssl").checked = Boolean(
      pool.backend_ssl,
    );
    document.getElementById("upstream-edit-method").value =
      pool.method || "round_robin";
    document.getElementById("upstream-edit-keepalive").value =
      pool.keepalive ?? "";
    document.getElementById("upstream-edit-description").value =
      pool.description || "";
    setServers(
      document.getElementById("upstream-edit-servers"),
      pool.servers || [],
    );

    // The pool is shared: editing it changes every service it is attached to, so say how many
    // and which ones before the operator saves.
    const shared = document.getElementById("upstream-edit-shared");
    const services = (pool.services || []).map(
      (attachment) => `${attachment.service_id} (${attachment.match_path})`,
    );
    shared.classList.toggle("d-none", services.length === 0);
    if (services.length) {
      shared.textContent = translate(
        "upstreams.edit_shared",
        `This upstream is attached to ${services.length} service(s): ${services.join(", ")}. Saving changes all of them.`,
        { count: services.length, services: services.join(", ") },
      );
    }
  }

  const createProtocol = document.getElementById("upstream-create-protocol");
  const syncCreate = () =>
    applyProtocol(
      createProtocol?.value || "http",
      "upstream-create-services",
      "upstream-create-services-hidden",
      "upstream-create-path",
    );
  createProtocol?.addEventListener("change", syncCreate);
  syncCreate();

  rows.forEach((row) => {
    const pool = upstreams.get(row.dataset.upstreamId);
    if (!pool) return;

    row.querySelector(".upstream-edit")?.addEventListener("click", (event) => {
      fillEditForm(pool);
      showModal("upstream-edit-modal", event.currentTarget);
    });

    row
      .querySelector(".upstream-attach")
      ?.addEventListener("click", (event) => {
        document.getElementById("upstream-attach-id").value = pool.id;
        const hosts = (pool.servers || [])
          .map((server) => server.host)
          .join(", ");
        document.getElementById("upstream-attach-copy").textContent = translate(
          "upstreams.attach_copy",
          `Attach ${pool.name} (${hosts}) to one or more services.`,
          { name: pool.name, servers: hosts },
        );
        applyProtocol(
          pool.protocol || "http",
          "upstream-attach-services",
          "upstream-attach-services-hidden",
          "upstream-attach-path",
        );
        showModal("upstream-attach-modal", event.currentTarget);
      });

    row
      .querySelector(".upstream-delete")
      ?.addEventListener("click", (event) => {
        document.getElementById("upstream-delete-id").value = pool.id;
        document.getElementById("upstream-delete-copy").textContent = translate(
          "upstreams.delete_copy",
          `Delete the upstream ${pool.name}?`,
          { name: pool.name },
        );
        showModal("upstream-delete-modal", event.currentTarget);
      });
  });

  const searchInput = document.getElementById("upstreams-search");
  const serviceFilter = document.getElementById("upstreams-service-filter");

  function applyFilters() {
    const term = (searchInput?.value || "").trim().toLowerCase();
    const service = serviceFilter?.value || "";
    rows.forEach((row) => {
      const pool = upstreams.get(row.dataset.upstreamId) || {};
      const hosts = (pool.servers || [])
        .map((server) => server.host || "")
        .join(" ");
      const haystack =
        `${pool.name || ""} ${pool.description || ""} ${hosts}`.toLowerCase();
      const matchesTerm = !term || haystack.includes(term);
      const matchesService =
        !service ||
        (pool.services || []).some(
          (attachment) => attachment.service_id === service,
        );
      row.hidden = !(matchesTerm && matchesService);
    });
  }

  searchInput?.addEventListener("input", applyFilters);
  serviceFilter?.addEventListener("change", applyFilters);
  document
    .getElementById("upstreams-search-clear")
    ?.addEventListener("click", () => {
      if (searchInput) searchInput.value = "";
      applyFilters();
    });
});
