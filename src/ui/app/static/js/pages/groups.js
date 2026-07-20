document.addEventListener("DOMContentLoaded", () => {
  const dataElement = document.getElementById("resource-groups-data");
  const groups = new Map(
    JSON.parse(dataElement?.value || "[]").map((group) => [group.id, group]),
  );
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

  function detailsFor(row) {
    const details = row.nextElementSibling;
    return details?.classList.contains("resource-group-details")
      ? details
      : null;
  }

  function setExpanded(row, expanded) {
    const details = detailsFor(row);
    const toggle = row.querySelector(".resource-group-toggle");
    if (!details || !toggle) return;
    details.hidden = !expanded;
    toggle.setAttribute("aria-expanded", String(expanded));
    toggle.querySelector("i")?.classList.toggle("bx-rotate-90", expanded);
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

  rows.forEach((row) => {
    setExpanded(row, false);
    row
      .querySelector(".resource-group-toggle")
      ?.addEventListener("click", () => {
        const details = detailsFor(row);
        setExpanded(row, Boolean(details?.hidden));
      });
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
            item.className = "list-group-item px-0";
            const setting = document.createElement("code");
            setting.textContent =
              reference.setting_id +
              (reference.suffix ? `_${reference.suffix}` : "");
            const scope = document.createElement("span");
            scope.className = "text-muted small ms-2";
            if (reference.scope === "service") {
              scope.textContent = reference.service_id;
            } else if (reference.scope === "template") {
              scope.textContent = translate(
                "resource_groups.template_configuration",
                `Template ${reference.template_id}`,
                { template: reference.template_id },
              );
            } else {
              scope.textContent = translate(
                "resource_groups.global_configuration",
                "Global configuration",
              );
            }
            item.append(setting, scope);
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
      const details = detailsFor(row);
      const matches = `${row.textContent} ${details?.textContent || ""}`
        .toLocaleLowerCase()
        .includes(query);
      row.hidden = !matches;
      if (!matches && details) details.hidden = true;
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

  const expandAll = document.getElementById("resource-groups-expand-all");
  expandAll?.addEventListener("click", () => {
    const visibleRows = rows.filter((row) => !row.hidden);
    const shouldExpand = visibleRows.some((row) => detailsFor(row)?.hidden);
    visibleRows.forEach((row) => setExpanded(row, shouldExpand));
    expandAll.setAttribute("aria-pressed", String(shouldExpand));
    expandAll.querySelector("span").textContent = shouldExpand
      ? translate("resource_groups.collapse_all", "Collapse all")
      : translate("resource_groups.expand_all", "Expand all");
  });
});
