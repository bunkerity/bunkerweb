document.addEventListener("DOMContentLoaded", () => {
  const dataElement = document.getElementById("resource-groups-data");
  const groups = new Map(
    JSON.parse(dataElement?.value || "[]").map((group) => [group.id, group]),
  );
  const compat = JSON.parse(
    document.getElementById("resource-groups-compat")?.value || "{}",
  );
  const kindPlugins = compat.kinds || {};
  const pluginLabels = compat.labels || {};
  const rows = Array.from(document.querySelectorAll(".resource-group-row"));
  const editor = document.getElementById("resource-group-editor");
  const editorModal = editor
    ? bootstrap.Modal.getOrCreateInstance(editor)
    : null;
  const entryRows = document.getElementById("resource-group-entry-rows");
  const entryTemplate = document.getElementById(
    "resource-group-entry-template",
  );
  const emptyEntries = document.getElementById("resource-group-entry-empty");
  const entriesInput = document.getElementById("resource-group-entries");
  const aliasInput = document.getElementById("resource-group-alias");
  const descriptionInput = document.getElementById(
    "resource-group-description",
  );
  const groupIdInput = document.getElementById("resource-group-id");
  const importError = document.getElementById("resource-group-import-error");
  const maxEntries = 5000;
  let entrySequence = 0;
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

  function syncEntryEmpty() {
    if (emptyEntries) emptyEntries.hidden = Boolean(entryRows?.children.length);
  }

  function addEntry(entry = {}) {
    if (!entryRows || !entryTemplate || entryRows.children.length >= maxEntries)
      return;
    const row = entryTemplate.content.firstElementChild.cloneNode(true);
    const kind = row.querySelector(".resource-entry-kind");
    const value = row.querySelector(".resource-entry-value");
    const comment = row.querySelector(".resource-entry-comment");
    kind.value = entry.kind || "ip";
    value.value = entry.value || "";
    comment.value = entry.comment || "";
    [kind, value, comment].forEach((field) => {
      const id = `resource-entry-${entrySequence++}`;
      field.id = id;
      field.previousElementSibling.htmlFor = id;
    });
    entryRows.appendChild(row);
    syncEntryEmpty();
  }

  function openEditor(groupId = null, trigger = null) {
    const group = groupId ? groups.get(groupId) : null;
    if (!editorModal || !entryRows) return;
    groupIdInput.value = group?.id || "";
    aliasInput.value = group?.name || "";
    aliasInput.readOnly = Boolean(group);
    descriptionInput.value = group?.description || "";
    entryRows.replaceChildren();
    (group?.entries || []).forEach(addEntry);
    if (!group) addEntry();
    syncEntryEmpty();
    const title = document.getElementById("resource-group-editor-title");
    if (title)
      title.textContent = group
        ? translate("resource_groups.editor_edit", `Edit @${group.name}`, {
            name: group.name,
          })
        : translate("resource_groups.editor_new", "New resource group");
    showModal(editorModal, editor, trigger);
  }

  // Values dialog: every entry of the group, one tab per kind, with its comment. Built from the
  // same data the editor reads, with text nodes only (values are operator input).
  const valuesModalElement = document.getElementById(
    "resource-group-values-modal",
  );
  const valuesState = { group: null, kind: "all", query: "" };
  const kindLabel = (kind) =>
    translate(`resource_groups.kind_label.${kind}`, kind);

  function renderValues() {
    const { group, kind, query } = valuesState;
    const list = document.getElementById("resource-values-list");
    const entries = (group?.entries || []).filter(
      (entry) =>
        (kind === "all" || entry.kind === kind) &&
        (!query ||
          `${entry.value} ${entry.comment || ""}`
            .toLocaleLowerCase()
            .includes(query)),
    );
    list.replaceChildren();
    entries.forEach((entry) => {
      const item = document.createElement("li");
      item.className = "d-flex flex-wrap align-items-baseline gap-2";
      const value = document.createElement("code");
      value.textContent = entry.value;
      item.append(value);
      if (kind === "all") {
        const chip = document.createElement("span");
        chip.className = "tag-chip";
        chip.textContent = kindLabel(entry.kind);
        item.append(chip);
      }
      if (entry.comment) {
        const comment = document.createElement("span");
        comment.className = "text-muted small";
        comment.textContent = `— ${entry.comment}`;
        item.append(comment);
      }
      list.append(item);
    });
    document.getElementById("resource-values-empty").hidden =
      entries.length > 0;
    const plugins = (kind === "all" ? kindsOf(group) : [kind]).flatMap(
      (name) => kindPlugins[name] || [],
    );
    document.getElementById("resource-values-compat").textContent =
      plugins.length
        ? translate(
            "resource_groups.values_compat",
            `Compatible with: ${[...new Set(plugins)].join(", ")}`,
            {
              plugins: [...new Set(plugins)]
                .map((plugin) => pluginLabels[plugin] || plugin)
                .join(", "),
            },
          )
        : "";
  }

  const kindsOf = (group) => [
    ...new Set((group?.entries || []).map((entry) => entry.kind)),
  ];

  function renderKindTabs() {
    const tabs = document.getElementById("resource-values-kinds");
    tabs.replaceChildren();
    const make = (kind, label, total) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `nav-link d-flex justify-content-between gap-3${valuesState.kind === kind ? " active" : ""}`;
      button.setAttribute("role", "tab");
      button.setAttribute("aria-selected", String(valuesState.kind === kind));
      const text = document.createElement("span");
      text.textContent = label;
      const number = document.createElement("span");
      number.textContent = String(total);
      button.append(text, number);
      button.addEventListener("click", () => {
        valuesState.kind = kind;
        renderKindTabs();
        renderValues();
      });
      tabs.append(button);
    };
    const entries = valuesState.group?.entries || [];
    make("all", translate("resource_groups.all_kinds", "All"), entries.length);
    kindsOf(valuesState.group).forEach((kind) =>
      make(
        kind,
        kindLabel(kind),
        entries.filter((entry) => entry.kind === kind).length,
      ),
    );
  }

  function openValues(groupId, trigger) {
    const group = groups.get(groupId);
    if (!group || !valuesModalElement) return;
    valuesState.group = group;
    valuesState.kind = "all";
    valuesState.query = "";
    document.getElementById("resource-values-filter").value = "";
    document.getElementById("resource-group-values-modal-title").textContent =
      translate("resource_groups.values_title", `Values of @${group.name}`, {
        name: `@${group.name}`,
      });
    renderKindTabs();
    renderValues();
    showModal(
      bootstrap.Modal.getOrCreateInstance(valuesModalElement),
      valuesModalElement,
      trigger,
    );
  }

  document
    .getElementById("resource-values-filter")
    ?.addEventListener("input", (event) => {
      valuesState.query = event.target.value.trim().toLocaleLowerCase();
      renderValues();
    });
  document
    .getElementById("resource-values-copy")
    ?.addEventListener("click", async (event) => {
      const { group, kind, query } = valuesState;
      const text = (group?.entries || [])
        .filter(
          (entry) =>
            (kind === "all" || entry.kind === kind) &&
            (!query || entry.value.toLocaleLowerCase().includes(query)),
        )
        .map((entry) => entry.value)
        .join("\n");
      const button = event.currentTarget;
      try {
        await navigator.clipboard.writeText(text);
        const label = button.querySelector("span");
        const previous = label?.textContent;
        if (label)
          label.textContent = translate(
            "resource_groups.values_copied",
            "Copied",
          );
        setTimeout(() => {
          if (label && previous) label.textContent = previous;
        }, 1500);
      } catch (error) {
        // Clipboard refused (insecure context): nothing to copy into, nothing to report.
      }
    });

  rows.forEach((row) => {
    row
      .querySelectorAll(".resource-group-values-open")
      .forEach((button) =>
        button.addEventListener("click", (event) =>
          openValues(row.dataset.groupId, event.currentTarget),
        ),
      );
    row
      .querySelector(".resource-group-edit")
      ?.addEventListener("click", (event) =>
        openEditor(row.dataset.groupId, event.currentTarget),
      );
    row
      .querySelector(".resource-group-clone")
      ?.addEventListener("click", (event) => {
        const group = groups.get(row.dataset.groupId);
        document.getElementById("resource-group-clone-source").value = group.id;
        document.getElementById("resource-group-clone-alias").value =
          `${group.name}-copy`.slice(0, 64);
        document.getElementById("resource-group-clone-copy").textContent =
          translate(
            "resource_groups.clone_copy",
            `Create an editable copy of @${group.name}.`,
            { name: group.name },
          );
        const modalElement = document.getElementById(
          "resource-group-clone-modal",
        );
        showModal(
          bootstrap.Modal.getOrCreateInstance(modalElement),
          modalElement,
          event.currentTarget,
        );
      });
    row
      .querySelector(".resource-group-delete")
      ?.addEventListener("click", (event) => {
        const group = groups.get(row.dataset.groupId);
        document.getElementById("resource-group-delete-id").value = group.id;
        document.getElementById("resource-group-delete-copy").textContent =
          translate(
            "resource_groups.delete_confirm",
            `Delete @${group.name}? This cannot be undone.`,
            { name: group.name },
          );
        const modalElement = document.getElementById(
          "resource-group-delete-modal",
        );
        showModal(
          bootstrap.Modal.getOrCreateInstance(modalElement),
          modalElement,
          event.currentTarget,
        );
      });
    row
      .querySelector(".resource-group-usage")
      ?.addEventListener("click", async (event) => {
        const modalElement = document.getElementById(
          "resource-group-usage-modal",
        );
        const modal = bootstrap.Modal.getOrCreateInstance(modalElement);
        const loading = document.getElementById("resource-group-usage-loading");
        const error = document.getElementById("resource-group-usage-error");
        const empty = document.getElementById("resource-group-usage-empty");
        const list = document.getElementById("resource-group-reference-list");
        loading.hidden = false;
        error.hidden = true;
        empty.hidden = true;
        list.hidden = true;
        list.replaceChildren();
        showModal(modal, modalElement, event.currentTarget);
        try {
          const response = await fetch(row.dataset.referencesUrl, {
            headers: { "X-Requested-With": "XMLHttpRequest" },
          });
          const payload = await response.json();
          if (!response.ok)
            throw new Error(
              payload.message ||
                translate(
                  "resource_groups.references_error",
                  "Could not load references",
                ),
            );
          payload.references.forEach((reference) => {
            const item = document.createElement("li");
            item.className =
              "list-group-item px-0 d-flex flex-wrap align-items-center gap-2";
            // Scope first (a service, a template or the global configuration), then the setting.
            const scope = document.createElement("span");
            if (reference.scope === "service") {
              scope.className = "svc-code";
              scope.textContent = reference.service_id;
            } else if (reference.scope === "template") {
              scope.className = "svc-scope";
              scope.textContent = translate(
                "resource_groups.template_configuration",
                `Template ${reference.template_id}`,
                { template: reference.template_id },
              );
            } else {
              scope.className = "svc-scope";
              scope.textContent = translate(
                "resource_groups.global_configuration",
                "Global configuration",
              );
            }
            const setting = document.createElement("code");
            setting.textContent =
              reference.setting_id +
              (reference.suffix ? `_${reference.suffix}` : "");
            item.append(scope, setting);
            list.appendChild(item);
          });
          empty.hidden = Boolean(payload.references.length);
          list.hidden = !payload.references.length;
        } catch (exception) {
          error.textContent = exception.message;
          error.hidden = false;
        } finally {
          loading.hidden = true;
        }
      });
  });

  document
    .getElementById("resource-group-new")
    ?.addEventListener("click", (event) =>
      openEditor(null, event.currentTarget),
    );
  document
    .getElementById("resource-group-empty-new")
    ?.addEventListener("click", (event) =>
      openEditor(null, event.currentTarget),
    );
  document
    .getElementById("resource-group-add-entry")
    ?.addEventListener("click", () => {
      addEntry();
      entryRows.lastElementChild
        ?.querySelector(".resource-entry-value")
        ?.focus();
    });

  entryRows?.addEventListener("click", (event) => {
    const row = event.target.closest("tr");
    if (!row) return;
    if (event.target.closest(".resource-entry-remove")) row.remove();
    if (
      event.target.closest(".resource-entry-up") &&
      row.previousElementSibling
    )
      row.parentElement.insertBefore(row, row.previousElementSibling);
    if (event.target.closest(".resource-entry-down") && row.nextElementSibling)
      row.parentElement.insertBefore(row.nextElementSibling, row);
    syncEntryEmpty();
  });

  document
    .getElementById("resource-group-form")
    ?.addEventListener("submit", () => {
      entriesInput.value = JSON.stringify(
        Array.from(entryRows.children).map((row, index) => ({
          kind: row.querySelector(".resource-entry-kind").value,
          value: row.querySelector(".resource-entry-value").value.trim(),
          comment: row.querySelector(".resource-entry-comment").value.trim(),
          order: index + 1,
        })),
      );
    });

  // A refused save comes back with what was posted (js/components/form-retry.js refills the plain
  // fields and reopens the modal); the entry rows are built here, so this rebuilds them from the
  // posted JSON and puts the editor back in the create/edit state it was posted from (QA-UI M28).
  document
    .getElementById("resource-group-form")
    ?.addEventListener("bw:form-retry", (event) => {
      const fields = event.detail?.fields || {};
      const group = fields.group_id ? groups.get(fields.group_id) : null;
      let entries = [];
      try {
        entries = JSON.parse(fields.entries || "[]");
      } catch (_error) {
        entries = [];
      }
      aliasInput.readOnly = Boolean(group);
      entryRows.replaceChildren();
      (Array.isArray(entries) ? entries : []).forEach(addEntry);
      syncEntryEmpty();
      const title = document.getElementById("resource-group-editor-title");
      if (title)
        title.textContent = group
          ? translate("resource_groups.editor_edit", `Edit @${group.name}`, {
              name: group.name,
            })
          : translate("resource_groups.editor_new", "New resource group");
    });

  function showImportError(message = "") {
    importError.textContent = message;
    importError.hidden = !message;
  }

  function importValues(content) {
    const kind = document.getElementById("resource-group-bulk-kind").value;
    const values = content
      .split(/[\r\n,;\t]+/)
      .map((value) => value.trim())
      .filter(Boolean);
    if (entryRows.children.length + values.length > maxEntries) {
      showImportError(
        translate(
          "resource_groups.max_entries",
          `A resource group cannot contain more than ${maxEntries} entries.`,
          { max: maxEntries },
        ),
      );
      return;
    }
    const existing = new Set(
      Array.from(entryRows.children).map(
        (row) =>
          `${row.querySelector(".resource-entry-kind").value}\0${row
            .querySelector(".resource-entry-value")
            .value.trim()}`,
      ),
    );
    values.forEach((value) => {
      const key = `${kind}\0${value}`;
      if (!existing.has(key)) {
        addEntry({ kind, value });
        existing.add(key);
      }
    });
    showImportError();
  }

  document
    .getElementById("resource-group-add-bulk")
    ?.addEventListener("click", () => {
      const input = document.getElementById("resource-group-bulk-values");
      importValues(input.value);
      input.value = "";
    });
  document
    .getElementById("resource-group-import-trigger")
    ?.addEventListener("click", () =>
      document.getElementById("resource-group-import-file").click(),
    );
  document
    .getElementById("resource-group-import-file")
    ?.addEventListener("change", async (event) => {
      const file = event.target.files?.[0];
      event.target.value = "";
      if (!file) return;
      if (file.size > 256 * 1024) {
        showImportError(
          translate(
            "resource_groups.import_size",
            "TXT/CSV imports are limited to 256 KiB.",
          ),
        );
        return;
      }
      if (!/\.(txt|csv)$/i.test(file.name)) {
        showImportError(
          translate(
            "resource_groups.import_extension",
            "Choose a .txt or .csv file.",
          ),
        );
        return;
      }
      importValues(await file.text());
    });

  const search = document.getElementById("resource-groups-search");
  const count = document.getElementById("resource-groups-count");
  function filterRows() {
    const query = search.value.trim().toLocaleLowerCase();
    let visible = 0;
    rows.forEach((row) => {
      const group = groups.get(row.dataset.groupId);
      // Name, description and kinds are in the row; the values only live in the data.
      const values = (group?.entries || [])
        .map((entry) => `${entry.value} ${entry.comment || ""}`)
        .join(" ");
      const matches = `${row.textContent} ${values}`
        .toLocaleLowerCase()
        .includes(query);
      row.hidden = !matches;
      if (matches) visible += 1;
    });
    if (count)
      count.textContent = translate(
        "resource_groups.showing_count",
        `Showing ${visible} of ${rows.length} groups`,
        { visible, total: rows.length },
      );
  }
  search?.addEventListener("input", filterRows);
  document
    .getElementById("resource-groups-search-clear")
    ?.addEventListener("click", () => {
      search.value = "";
      filterRows();
      search.focus();
    });
});
