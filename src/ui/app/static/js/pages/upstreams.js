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
      pathField
        .closest(".col-md-4, .mt-3")
        ?.classList.toggle("d-none", protocol === "stream");
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

  function openAttach(pool, trigger) {
    document.getElementById("upstream-attach-id").value = pool.id;
    const hosts = (pool.servers || []).map((server) => server.host).join(", ");
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
    showModal("upstream-attach-modal", trigger);
  }

  const textCell = (row, text, className = "") => {
    const cell = document.createElement("td");
    if (className) cell.className = className;
    cell.textContent = text;
    row.append(cell);
    return cell;
  };

  // Read-only view of the pool members: address, weight, max fails, fail timeout and the
  // configured role (not live health: the page has no runtime data).
  function openMembers(pool, trigger) {
    const count = (pool.servers || []).length;
    document.getElementById("upstream-members-copy").textContent = translate(
      count === 1 ? "upstreams.members_copy" : "upstreams.members_copy_plural",
      `${pool.name}: ${count} ${count === 1 ? "server" : "servers"}`,
      { name: pool.name, count },
    );
    const body = document.getElementById("upstream-members-body");
    body.replaceChildren();
    (pool.servers || []).forEach((server) => {
      const row = document.createElement("tr");
      textCell(row, server.host || "", "res-mono");
      textCell(row, String(server.weight ?? 1));
      textCell(row, String(server.max_fails ?? 1));
      textCell(row, server.fail_timeout || "10s");
      textCell(
        row,
        server.down
          ? translate("upstreams.role.down", "Down")
          : server.backup
            ? translate("upstreams.role.backup", "Backup")
            : translate("upstreams.role.primary", "Primary"),
      );
      body.append(row);
    });
    showModal("upstream-members-modal", trigger);
  }

  // Attachments are per service AND path (a service can hold several paths of one pool), so
  // each Detach carries the path it removes; Attach stays an explicit, separate operation.
  function openServices(pool, trigger) {
    const list = document.getElementById("upstream-services-list");
    const attachButton = document.getElementById("upstream-services-attach");
    const readonly = attachButton.disabled;
    document.getElementById("upstream-services-copy").textContent = translate(
      "upstreams.services_copy",
      `${pool.name}: ${(pool.servers || []).map((server) => server.host).join(", ")}`,
      {
        name: pool.name,
        servers: (pool.servers || []).map((server) => server.host).join(", "),
      },
    );
    document.getElementById("upstream-services-shared").textContent = translate(
      "upstreams.detach_shared",
      "This upstream is shared. Detaching it removes it from that service and path only; the other attachments keep it.",
    );
    list.replaceChildren();
    (pool.services || []).forEach((attachment) => {
      const item = document.createElement("li");
      item.className =
        "list-group-item d-flex align-items-center justify-content-between gap-2 px-0";
      const label = document.createElement("span");
      const code = document.createElement("span");
      code.className = "svc-code";
      code.textContent = attachment.service_id;
      label.append(code);
      // A stream pool takes the whole service and has no location.
      if (pool.protocol !== "stream" && attachment.match_path) {
        const path = document.createElement("span");
        path.className = "res-mono ms-2";
        path.textContent = attachment.match_path;
        label.append(path);
      }
      item.append(label);
      if (!readonly) {
        const form = document.createElement("form");
        form.method = "post";
        form.action = list.dataset.detachUrl;
        [
          ["csrf_token", list.dataset.csrf],
          ["upstream_id", pool.id],
          ["service_id", attachment.service_id],
          ["match_path", attachment.match_path ?? ""],
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
        const ariaLabel = translate(
          "aria.label.detach_from_service",
          `Detach ${pool.name} from ${attachment.service_id}`,
          { name: pool.name, service: attachment.service_id },
        );
        button.setAttribute("aria-label", ariaLabel);
        button.title = ariaLabel;
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
      const services = modalFor("upstream-services-modal");
      services?.element.addEventListener(
        "hidden.bs.modal",
        () => openAttach(pool, trigger),
        { once: true },
      );
      services?.instance.hide();
    };
    showModal("upstream-services-modal", trigger);
  }

  rows.forEach((row) => {
    const pool = upstreams.get(row.dataset.upstreamId);
    if (!pool) return;

    row.querySelector(".upstream-edit")?.addEventListener("click", (event) => {
      fillEditForm(pool);
      showModal("upstream-edit-modal", event.currentTarget);
    });

    row
      .querySelector(".upstream-attach")
      ?.addEventListener("click", (event) =>
        openAttach(pool, event.currentTarget),
      );

    row
      .querySelector(".upstream-members")
      ?.addEventListener("click", (event) =>
        openMembers(pool, event.currentTarget),
      );

    row
      .querySelector(".upstream-services")
      ?.addEventListener("click", (event) =>
        openServices(pool, event.currentTarget),
      );

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
  const protocolFilter = document.getElementById("upstreams-protocol-filter");
  const tlsFilter = document.getElementById("upstreams-tls-filter");
  const noMatch = document.getElementById("upstreams-no-match");

  function applyFilters() {
    const term = (searchInput?.value || "").trim().toLowerCase();
    const protocol = protocolFilter?.value || "";
    const tls = tlsFilter?.value || "";
    let visible = 0;
    rows.forEach((row) => {
      const pool = upstreams.get(row.dataset.upstreamId) || {};
      const hosts = (pool.servers || [])
        .map((server) => server.host || "")
        .join(" ");
      const paths = (pool.services || [])
        .map((attachment) => attachment.match_path || "")
        .join(" ");
      const haystack =
        `${pool.name || ""} ${pool.description || ""} ${hosts} ${paths}`.toLowerCase();
      const matches =
        (!term || haystack.includes(term)) &&
        (!protocol || pool.protocol === protocol) &&
        (!tls || Boolean(pool.backend_ssl) === (tls === "yes"));
      row.hidden = !matches;
      if (matches) visible += 1;
    });
    if (noMatch) noMatch.hidden = visible > 0 || rows.length === 0;
  }

  searchInput?.addEventListener("input", applyFilters);
  protocolFilter?.addEventListener("change", applyFilters);
  tlsFilter?.addEventListener("change", applyFilters);
  document
    .getElementById("upstreams-search-clear")
    ?.addEventListener("click", () => {
      if (searchInput) searchInput.value = "";
      applyFilters();
    });

  // A create or edit the server refused comes back with ?retry=create|edit: reopen the modal
  // with what was typed instead of making the operator start over. The input stays in this
  // tab's sessionStorage, never in the URL.
  function wireRetry(
    form,
    modalId,
    draftKey,
    retryValue,
    serversId,
    onRestore,
  ) {
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
      // One editor row per submitted server; the server_* lists are parallel, row by row.
      const hosts = draft.filter(([name]) => name === "server_host");
      setServers(
        document.getElementById(serversId),
        hosts.map(() => ({})),
      );
      const seen = {};
      Array.from(form.elements).forEach((field) => {
        if (!field.name || field.name === "csrf_token") return;
        const values = draft
          .filter(([name]) => name === field.name)
          .map(([, value]) => value);
        const index = seen[field.name] || 0;
        seen[field.name] = index + 1;
        if (field.type === "checkbox")
          field.checked = values.includes(field.value);
        else if (field.multiple)
          Array.from(field.options).forEach((option) => {
            option.selected = values.includes(option.value);
          });
        else if (index < values.length) field.value = values[index];
      });
      onRestore?.();
      showModal(modalId);
    }
  }

  const url = new URL(window.location.href);
  wireRetry(
    document.querySelector("#upstream-create-modal form"),
    "upstream-create-modal",
    "bw-upstream-create-draft",
    "create",
    "upstream-create-servers",
    syncCreate,
  );
  const editForm = document.querySelector("#upstream-edit-modal form");
  wireRetry(
    editForm,
    "upstream-edit-modal",
    "bw-upstream-edit-draft",
    "edit",
    "upstream-edit-servers",
    () => {
      const pool = upstreams.get(editForm.elements["upstream_id"]?.value);
      const shared = document.getElementById("upstream-edit-shared");
      const services = (pool?.services || []).map(
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
    },
  );
  if (url.searchParams.has("retry")) {
    url.searchParams.delete("retry");
    window.history.replaceState(null, "", url);
  }
});
