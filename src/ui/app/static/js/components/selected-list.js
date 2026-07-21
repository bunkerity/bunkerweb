window.BWSelectedList = window.BWSelectedList || {};

(function (api) {
  "use strict";
  if (window.__bwSelectedListInit) return;
  window.__bwSelectedListInit = true;

  const translate = (key, fallback, options) =>
    typeof i18next === "undefined"
      ? fallback
      : i18next.t(key, { defaultValue: fallback, ...options });

  const element = (tag, classes, text) => {
    const node = document.createElement(tag);
    if (classes) node.className = classes;
    if (text != null) node.textContent = text;
    return node;
  };

  const plainText = (value) => {
    if (value == null) return "";
    return new DOMParser().parseFromString(String(value), "text/html").body
      .textContent;
  };

  function resolveHost(target) {
    if (!target) return null;
    const node =
      typeof target === "string" ? document.querySelector(target) : target;
    if (!node) return null;
    return node.matches("[data-selected-host]")
      ? node
      : node.querySelector("[data-selected-host]");
  }

  function countText(count, entity) {
    return translate(
      "datatable.selected_list_count",
      `${count} ${entity} selected`,
      { count, entity },
    );
  }

  function emptyText(entity) {
    return translate(
      "datatable.selected_list_empty",
      `No ${entity} selected.`,
      { entity },
    );
  }

  function makeCell(value, column, header = false) {
    const cell = element(
      "li",
      `list-group-item bw-selected-list-cell${header ? " bg-secondary text-white" : ""}`,
    );
    cell.setAttribute("role", "listitem");
    const body = element("div", "ms-2 me-auto");
    const content = column.bold || header ? element("div", "fw-bold") : body;
    content.textContent = plainText(value);
    if (header && column.i18n) content.dataset.i18n = column.i18n;
    if (content !== body) body.append(content);
    cell.append(body);
    return cell;
  }

  function makeColumns(rows, columns) {
    const block = element("div");
    block.dataset.selectedColumns = "";
    const header = element("ul", "list-group list-group-horizontal w-100");
    header.setAttribute("role", "list");
    columns.forEach((column) =>
      header.append(makeCell(column.label || "", column, true)),
    );
    block.append(header);

    const list = element("div", "overflow-auto");
    list.dataset.selectedList = "";
    rows.forEach((row) => {
      const line = element("ul", "list-group list-group-horizontal w-100");
      line.setAttribute("role", "list");
      columns.forEach((column) =>
        line.append(makeCell(row[column.key], column)),
      );
      list.append(line);
    });
    block.append(list);
    return block;
  }

  function makeSimple(rows, options, label) {
    const list = element("ul", "list-group overflow-auto");
    list.dataset.selectedList = "";
    list.setAttribute("role", "list");
    list.setAttribute("aria-label", label);
    rows.forEach((row) => {
      const item = element(
        "li",
        "list-group-item d-flex align-items-center justify-content-between gap-2",
      );
      item.setAttribute("role", "listitem");
      const text = element("div", "d-flex align-items-center gap-2");
      const iconName = row.icon || options.icon || "bx-chevron-right";
      if (/^bx[a-z0-9-]*$/.test(iconName)) {
        const icon = element("i", `bx ${iconName}`);
        icon.setAttribute("aria-hidden", "true");
        text.append(icon);
      }
      const labels = element("div");
      labels.append(
        element("div", "fw-semibold", plainText(row.label ?? row.id)),
      );
      if (row.sub)
        labels.append(element("div", "text-muted", plainText(row.sub)));
      text.append(labels);
      item.append(text);
      if (row.badge) {
        const variant = /^[a-z0-9-]+$/.test(row.badge_color || "")
          ? row.badge_color
          : "secondary";
        item.append(
          element(
            "span",
            `badge rounded-pill bg-label-${variant}`,
            plainText(row.badge),
          ),
        );
      }
      list.append(item);
    });
    return list;
  }

  function render(target, rows = [], options = {}) {
    const host = resolveHost(target);
    if (!host) return null;
    const idKey = options.idKey || host.dataset.idKey || "id";
    const entity = options.entity || host.dataset.entity || "items";
    const hiddenMode = options.hiddenMode || host.dataset.hiddenMode || "ids";
    const label = options.title || countText(rows.length, entity);
    Object.assign(host.dataset, { idKey, entity, hiddenMode });

    const count = host.querySelector("[data-selected-count]");
    if (count) count.textContent = label;
    host
      .querySelector(
        "[data-selected-list], [data-selected-columns], [data-selected-empty]",
      )
      ?.remove();

    let block;
    if (!rows.length) {
      block = element(
        "p",
        "text-muted mb-0",
        options.emptyText || emptyText(entity),
      );
      block.dataset.selectedEmpty = "";
    } else if (options.columns) {
      block = makeColumns(rows, options.columns);
    } else {
      block = makeSimple(rows, options, label);
    }

    const input = host.querySelector("[data-selected-input]");
    host.insertBefore(block, input);
    if (input && hiddenMode !== "none") {
      const ids = rows.map((row) => row[idKey]);
      input.value =
        hiddenMode === "csv"
          ? ids.join(",")
          : JSON.stringify(hiddenMode === "items" ? rows : ids);
      input.dispatchEvent(new Event("change", { bubbles: true }));
    }
    if (typeof applyTranslations === "function") applyTranslations();
    return host;
  }

  function clear(target) {
    const host = resolveHost(target);
    return host
      ? render(host, [], {
          entity: host.dataset.entity,
          idKey: host.dataset.idKey,
          hiddenMode: host.dataset.hiddenMode,
        })
      : null;
  }

  function getIds(target) {
    const value = resolveHost(target)?.querySelector(
      "[data-selected-input]",
    )?.value;
    if (!value) return [];
    try {
      const parsed = JSON.parse(value);
      return Array.isArray(parsed) ? parsed : [];
    } catch (_error) {
      return value.split(",").filter(Boolean);
    }
  }

  function fromDataTable(table, options = {}) {
    const idKey = options.idKey || "id";
    try {
      return table
        .rows({ selected: true })
        .data()
        .toArray()
        .map((row) =>
          options.columns
            ? { ...row, id: row[idKey] }
            : {
                id: row[idKey],
                label: row[options.labelKey || "label"],
                sub: row[options.subKey || "sub"],
                icon: row[options.iconKey || "icon"],
                badge: row[options.badgeKey || "badge"],
                badge_color: row[options.badgeColorKey || "badge_color"],
              },
        );
    } catch (_error) {
      return [];
    }
  }

  function fromCheckboxes(source) {
    const root =
      typeof source === "string" ? document.querySelector(source) : source;
    if (!root) return [];
    return Array.from(root.querySelectorAll("[data-row-select]:checked")).map(
      (checkbox) => ({
        id: checkbox.dataset.id ?? checkbox.value,
        label: checkbox.dataset.label,
        sub: checkbox.dataset.sub,
        icon: checkbox.dataset.icon,
        badge: checkbox.dataset.badge,
        badge_color: checkbox.dataset.badgeColor,
      }),
    );
  }

  function readSource(source, options) {
    const root =
      typeof source === "string" ? document.querySelector(source) : source;
    if (!root) return [];
    const table = root.matches("table") ? root : root.querySelector("table");
    const jq = window.jQuery || window.$;
    if (table && jq?.fn?.dataTable && jq.fn.dataTable.isDataTable(table)) {
      return fromDataTable(jq(table).DataTable(), options);
    }
    return fromCheckboxes(root);
  }

  $(document).on("click", "[data-selected-populate]", function () {
    let columns;
    try {
      columns = this.dataset.selectedColumns
        ? JSON.parse(this.dataset.selectedColumns)
        : null;
    } catch (_error) {
      columns = null;
    }
    const options = {
      entity: this.dataset.selectedEntity,
      idKey: this.dataset.selectedIdKey,
      hiddenMode: this.dataset.selectedHiddenMode,
      icon: this.dataset.selectedIcon,
      emptyText: this.dataset.selectedEmptyText,
      labelKey: this.dataset.selectedLabelKey,
      subKey: this.dataset.selectedSubKey,
      columns,
    };
    const host = resolveHost(this.dataset.selectedTarget);
    if (host && this.dataset.selectedSource) {
      render(host, readSource(this.dataset.selectedSource, options), options);
    }
  });

  $(document).on("hidden.bs.modal", (event) => {
    event.target.querySelectorAll("[data-selected-host]").forEach(clear);
  });

  Object.assign(api, {
    render,
    populate: render,
    clear,
    getIds,
    fromCheckboxes,
    fromDataTable,
    readSource,
  });
})(window.BWSelectedList);
