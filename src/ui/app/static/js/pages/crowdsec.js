function createCrowdSecPageState() {
  let connection = "";
  let generation = 0;
  const sequences = new Map();

  const snapshotConnection = (source) =>
    Object.freeze({
      id: source.id,
      instance: source.instance,
      services: Array.isArray(source.services) ? [...source.services] : [],
      lapi_url: source.lapi_url,
      management_configured: Boolean(source.management_configured),
    });

  return {
    switchConnection(next) {
      connection = next || "";
      generation += 1;
      sequences.clear();
    },
    connection() {
      return connection;
    },
    matchesConnection(id) {
      return connection === id;
    },
    capture(channel, context = {}) {
      const sequence = (sequences.get(channel) || 0) + 1;
      sequences.set(channel, sequence);
      return Object.freeze({
        channel,
        connection,
        generation,
        sequence,
        context: JSON.stringify(context),
      });
    },
    isCurrent(token) {
      return Boolean(
        token &&
        token.connection === connection &&
        token.generation === generation &&
        sequences.get(token.channel) === token.sequence,
      );
    },
    bindAction(decision, source) {
      return Object.freeze({
        connection: snapshotConnection(source),
        decision: Object.freeze({
          id: decision.id,
          scope: decision.scope,
          value: decision.value,
          type: decision.type,
          origin: decision.origin,
          scenario: decision.scenario,
        }),
      });
    },
    snapshotConnection,
  };
}

function partitionCrowdSecConnections(items) {
  const cards = Array.isArray(items)
    ? items.filter((connection) => connection && typeof connection === "object")
    : [];
  return {
    cards,
    selectable: cards.filter((connection) => connection.id),
  };
}

function getCrowdSecReportSnapshot(report, limit = 20) {
  const nested =
    report.data &&
    typeof report.data === "object" &&
    report.data.crowdsec &&
    typeof report.data.crowdsec === "object"
      ? report.data.crowdsec
      : null;
  const candidate = report.crowdsec || nested || report.data;
  if (
    !candidate ||
    typeof candidate !== "object" ||
    !candidate.captured_at ||
    !["lapi", "appsec", "failure_policy"].includes(candidate.source)
  ) {
    return null;
  }
  const decisions = Array.isArray(candidate.decisions)
    ? candidate.decisions.filter(
        (decision) => decision && typeof decision === "object",
      )
    : [];
  return {
    captured_at: candidate.captured_at,
    source: candidate.source,
    remediation: candidate.remediation,
    service_scope: candidate.service_scope,
    matched_target: candidate.matched_target,
    metadataAvailable: candidate.metadata_available === true,
    total: decisions.length,
    limit,
    truncated: decisions.length > limit,
    decisions: decisions.slice(0, limit).map((decision) => ({
      id: decision.id,
      origin: decision.origin,
      scenario: decision.scenario,
      target: decision.value,
      scope: decision.scope,
      expires_at: decision.expires_at,
    })),
  };
}

function getCrowdSecSection(payload, section) {
  const items = Array.isArray(payload[section]) ? payload[section] : [];
  const error = payload.errors && payload.errors[section];
  const totalValue = Number(payload[`${section}_total`]);
  const limitValue = Number(payload.limits && payload.limits[section]);
  const total = Number.isFinite(totalValue) ? totalValue : items.length;
  const limit = Number.isFinite(limitValue) ? limitValue : items.length;
  return {
    available: !error,
    error: error || "",
    items,
    total,
    shown: items.length,
    limit,
    truncated: total > items.length,
    // A source that reports no total and filled its page may be hiding more.
    pageBounded:
      !Number.isFinite(totalValue) &&
      Number.isFinite(limitValue) &&
      items.length >= limitValue,
  };
}

function getCrowdSecRemovalParameters(removal) {
  return {
    connection: removal.connection.id,
    decision_id: removal.decision.id,
    scope: removal.decision.scope,
    value: removal.decision.value,
    decision_type: removal.decision.type,
  };
}

function getCrowdSecBanExpiry(ban, observedAt) {
  if (ban.permanent) return null;
  const remaining = Number(ban.exp);
  const observed = Number(observedAt);
  return Number.isFinite(remaining) &&
    remaining >= 0 &&
    Number.isFinite(observed)
    ? observed + remaining
    : null;
}

document.addEventListener("DOMContentLoaded", () => {
  const t =
    typeof i18next !== "undefined"
      ? i18next.t.bind(i18next)
      : (key, options) => (options && options.defaultValue) || key;
  const byId = (id) => document.getElementById(id);
  const urls = JSON.parse(byId("crowdsec-urls").value);
  const connectionGroup = byId("crowdsec-connections");
  const decisionsBody = byId("crowdsec-decisions-body");
  const isAdmin = byId("is-admin").value === "True";
  const isReadOnly = byId("is-read-only").value === "True";
  const pageParams = new URLSearchParams(window.location.search);
  const pageSize = 50;
  let connections = [];
  let decisionOffset = 0;
  let allowlistOffset = 0;
  let pendingRemoval = null;
  let modalTrigger = null;
  const pageState = createCrowdSecPageState();

  const element = (tag, className, value) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (value !== undefined && value !== null) node.textContent = String(value);
    return node;
  };

  const translated = (key, fallback, options = {}) =>
    t(key, {
      defaultValue: fallback,
      ...options,
      interpolation: { ...options.interpolation, escapeValue: false },
    });

  const formatObserved = (value) => {
    const number = Number(value);
    if (!Number.isFinite(number))
      return translated("crowdsec.unknown", "Unknown");
    return new Date(number * 1000).toLocaleString();
  };

  const formatTime = (value) => {
    if (value === undefined || value === null || value === "")
      return translated("crowdsec.unknown", "Unknown");
    const numeric = Number(value);
    const parsed = Number.isFinite(numeric)
      ? new Date(numeric * 1000)
      : new Date(value);
    return Number.isFinite(parsed.getTime())
      ? parsed.toLocaleString()
      : String(value);
  };

  const showMessage = (message, level = "danger") => {
    const box = byId("crowdsec-message");
    box.className = `alert alert-${level}`;
    box.textContent = message;
  };

  const clearMessage = () => {
    const box = byId("crowdsec-message");
    box.className = "alert d-none";
    box.textContent = "";
  };

  const fetchJson = async (url, options) => {
    const response = await fetch(url, options);
    let body;
    try {
      body = await response.json();
    } catch (_error) {
      body = {};
    }
    if (!response.ok) {
      throw new Error(
        body.error ||
          translated("crowdsec.error.request", "The CrowdSec request failed."),
      );
    }
    return body;
  };

  const selectedConnection = () =>
    connections.find((connection) => connection.id === pageState.connection());

  const preferredConnection = () => {
    const url = new URL(window.location.href);
    const candidates = [
      new URLSearchParams(url.hash.slice(1)).get("connection"),
      url.searchParams.get("connection"),
    ];
    return (
      candidates.find((id) =>
        connections.some((connection) => connection.id === id),
      ) ||
      connections[0]?.id ||
      ""
    );
  };

  const connectionLabel = (connection) => {
    const services = Array.isArray(connection.services)
      ? connection.services.join(", ")
      : translated("crowdsec.connection.global", "all services");
    return `${connection.instance || "?"} · ${services}`;
  };

  const appendDetail = (parent, label, value, valueClass = "") => {
    const row = element("div", "d-flex justify-content-between gap-3 small");
    row.append(
      element("span", "text-muted", label),
      element("span", `text-end crowdsec-meta ${valueClass}`.trim(), value),
    );
    parent.append(row);
  };

  const renderConnection = (connection, index) => {
    const column = element("div", "col-12 col-md-6");
    const card = element("article", "card h-100 crowdsec-connection-card");
    const body = element("div", "card-body");
    const header = element("div", "d-flex justify-content-between gap-2 mb-3");
    const radio = element("input", "form-check-input flex-shrink-0");
    radio.type = "radio";
    radio.name = "crowdsec-connection";
    radio.id = `crowdsec-connection-${index}`;
    radio.value = connection.id || "";
    radio.disabled = !connection.id;
    const title = element("h5", "card-title mb-0 flex-grow-1");
    const label = element(
      "label",
      radio.disabled ? "mb-0" : "stretched-link mb-0",
      connectionLabel(connection),
    );
    label.htmlFor = radio.id;
    title.append(label);
    header.append(radio, title);
    const reachable =
      connection.status === "up" || connection.status === "success";
    const failed = connection.status === "error";
    const badge = element(
      "span",
      `badge bg-${reachable ? "success" : failed ? "danger" : "warning text-dark"} align-self-start`,
      reachable
        ? translated("crowdsec.connection.connected", "Connected")
        : failed
          ? translated(
              "crowdsec.connection.connection_error",
              "Connection error",
            )
          : translated("crowdsec.unknown", "Unknown"),
    );
    header.append(badge);
    body.append(header);
    if (connection.lapi_url) {
      body.append(
        element(
          "p",
          "small text-muted crowdsec-meta mb-3",
          `${translated("crowdsec.connection.local_api", "Local API")}: ${connection.lapi_url}`,
        ),
      );
    }
    appendDetail(
      body,
      translated("crowdsec.connection.mode", "Mode"),
      connection.mode || "-",
    );
    appendDetail(
      body,
      translated("crowdsec.connection.management", "Management"),
      connection.management_configured
        ? translated("crowdsec.connection.configured", "Configured")
        : translated("crowdsec.connection.read_only", "Read only"),
    );
    const syncStatus = {
      current: [
        translated("crowdsec.connection.sync_current", "Up to date"),
        "badge bg-success",
      ],
      stale: [
        translated("crowdsec.connection.sync_stale", "Stale"),
        "badge bg-warning text-dark",
      ],
      not_synchronized: [
        translated(
          "crowdsec.connection.sync_not_synchronized",
          "Not synchronized yet",
        ),
        "badge bg-warning text-dark",
      ],
    }[connection.sync_status] || [
      translated("crowdsec.unknown", "Unknown"),
      "badge bg-secondary",
    ];
    appendDetail(
      body,
      translated("crowdsec.connection.sync", "Decision sync"),
      syncStatus[0],
      syncStatus[1],
    );
    if (connection.last_successful_sync) {
      appendDetail(
        body,
        translated("crowdsec.connection.last_sync", "Last successful sync"),
        formatObserved(connection.last_successful_sync),
      );
    }
    if (connection.last_sync_error || connection.error) {
      body.append(
        element(
          "div",
          "alert alert-warning small mt-3 mb-0",
          connection.last_sync_error || connection.error,
        ),
      );
    }
    if (connection.appsec_last_observed) {
      const appsec = connection.appsec_last_observed;
      appendDetail(
        body,
        translated("crowdsec.connection.appsec", "Last AppSec observation"),
        `${formatObserved(appsec.at)} · ${appsec.status || appsec.action || translated("crowdsec.unknown", "Unknown")}`,
      );
      if (appsec.error) {
        body.append(
          element("div", "alert alert-warning small mt-3 mb-0", appsec.error),
        );
      }
    }
    const selectedLabel = element(
      "div",
      "crowdsec-selected-label small fw-semibold text-primary mt-3 invisible",
      translated("crowdsec.connection.selected", "Selected connection"),
    );
    selectedLabel.dataset.i18n = "crowdsec.connection.selected";
    body.append(selectedLabel);
    card.append(body);
    column.append(card);
    return column;
  };

  const renderConnections = (payload) => {
    const container = byId("crowdsec-connections");
    const errors = byId("crowdsec-instance-errors");
    container.replaceChildren();
    errors.replaceChildren();
    const connectionViews = partitionCrowdSecConnections(payload.connections);
    connections = connectionViews.selectable;
    Object.entries(payload.errors || {}).forEach(([instance, message]) => {
      errors.append(
        element("div", "alert alert-danger mb-2", `${instance}: ${message}`),
      );
    });
    connectionViews.cards.forEach((connection, index) =>
      container.append(renderConnection(connection, index)),
    );
    if (!connectionViews.cards.length || !connections.length) {
      container.append(
        element(
          "div",
          "alert alert-warning",
          translated(
            "crowdsec.connection.none",
            "No usable CrowdSec connection was found. Check the instance errors and plugin configuration.",
          ),
        ),
      );
    }

    return preferredConnection();
  };

  const emptyState = (message) => element("p", "text-muted mb-0", message);

  const renderSectionUnavailable = (container, message) => {
    container.replaceChildren(
      element(
        "div",
        "alert alert-warning mb-0",
        translated(
          "crowdsec.investigation.unavailable",
          "Unavailable: {{error}}",
          { error: message },
        ),
      ),
    );
  };

  const appendTruncationNotice = (container, section) => {
    if (!section.truncated) return;
    container.append(
      element(
        "p",
        "small text-warning mt-2 mb-0",
        translated(
          "crowdsec.investigation.truncated",
          "Showing {{shown}} of {{total}} results (source limit: {{limit}}).",
          {
            shown: section.shown,
            total: section.total,
            limit: section.limit,
          },
        ),
      ),
    );
  };

  const canRemove = (connection) => {
    return Boolean(
      connection && connection.management_configured && isAdmin && !isReadOnly,
    );
  };

  const openRemoval = (decision, connection, trigger) => {
    if (!pageState.matchesConnection(connection.id)) return;
    pendingRemoval = pageState.bindAction(decision, connection);
    modalTrigger = trigger;
    byId("crowdsec-unban-confirm").checked = false;
    byId("crowdsec-unban-submit").disabled = true;
    byId("crowdsec-unban-selection").textContent = translated(
      "crowdsec.remove.selection",
      "Remove {{scope}} {{value}} ({{type}}), scenario {{scenario}}, origin {{origin}}, from {{source}} ({{engine}})?",
      {
        scope: pendingRemoval.decision.scope || "-",
        value: pendingRemoval.decision.value || "-",
        type: pendingRemoval.decision.type || "-",
        scenario: pendingRemoval.decision.scenario || "-",
        origin: pendingRemoval.decision.origin || "-",
        source: connectionLabel(pendingRemoval.connection),
        engine: pendingRemoval.connection.lapi_url || "-",
      },
    );
    bootstrap.Modal.getOrCreateInstance(byId("crowdsec-unban-modal")).show();
  };

  const removalButton = (decision, connection) => {
    if (!canRemove(connection)) return null;
    const button = element(
      "button",
      "btn btn-sm btn-outline-danger",
      translated("crowdsec.remove.action", "Remove"),
    );
    button.type = "button";
    button.addEventListener("click", () =>
      openRemoval(decision, connection, button),
    );
    return button;
  };

  const renderDecisionRow = (decision, connection) => {
    const row = document.createElement("tr");
    const target = element("td");
    target.append(
      element("span", "badge bg-secondary me-2", decision.scope || "-"),
      element("span", "crowdsec-meta", decision.value || "-"),
    );
    [
      target,
      element("td", "", decision.type || "-"),
      element("td", "", decision.origin || "-"),
      element("td", "crowdsec-meta", decision.scenario || "-"),
      element("td", "", decision.duration || "-"),
    ].forEach((cell) => row.append(cell));
    const action = element("td");
    const button = removalButton(decision, connection);
    if (button) action.append(button);
    row.append(action);
    return row;
  };

  const renderDecisions = (payload, connection) => {
    decisionsBody.replaceChildren();
    const decisions = Array.isArray(payload.decisions) ? payload.decisions : [];
    if (!decisions.length) {
      const cell = element(
        "td",
        "text-muted text-center py-4",
        translated(
          "crowdsec.decisions.none",
          "No active decisions match these filters.",
        ),
      );
      cell.colSpan = 6;
      const row = document.createElement("tr");
      row.append(cell);
      decisionsBody.append(row);
    } else {
      decisions.forEach((decision) =>
        decisionsBody.append(renderDecisionRow(decision, connection)),
      );
    }
    const total = Number(payload.total || 0);
    const countText = translated(
      "crowdsec.decisions.count",
      "Showing {{start}}–{{end}} of {{total}}",
      {
        start: total ? decisionOffset + 1 : 0,
        end: Math.min(decisionOffset + decisions.length, total),
        total,
      },
    );
    byId("crowdsec-decisions-count").textContent = payload.observed_at
      ? `${countText} · ${translated(
          "crowdsec.observed_at",
          "Observed {{time}}",
          {
            time: formatObserved(payload.observed_at),
          },
        )}`
      : countText;
    byId("crowdsec-decisions-prev").disabled = decisionOffset === 0;
    byId("crowdsec-decisions-next").disabled =
      decisionOffset + decisions.length >= total;
  };

  const renderDecisionNotice = (message) => {
    decisionsBody.replaceChildren();
    const cell = element("td", "text-muted text-center py-4", message);
    cell.colSpan = 6;
    const row = document.createElement("tr");
    row.append(cell);
    decisionsBody.append(row);
    byId("crowdsec-decisions-count").textContent = "";
    byId("crowdsec-decisions-prev").disabled = true;
    byId("crowdsec-decisions-next").disabled = true;
  };

  const loadDecisions = async () => {
    const connection = selectedConnection();
    if (!connection) {
      renderDecisionNotice(
        translated(
          "crowdsec.connection.required",
          "Choose a CrowdSec connection first.",
        ),
      );
      return;
    }
    const context = {
      ip: byId("crowdsec-filter-ip").value.trim(),
      origin: byId("crowdsec-filter-origin").value.trim(),
      scenario: byId("crowdsec-filter-scenario").value.trim(),
      offset: String(decisionOffset),
      limit: String(pageSize),
    };
    const requestState = pageState.capture("decisions", context);
    const query = new URLSearchParams({
      connection: connection.id,
      ...context,
    });
    renderDecisionNotice(translated("status.loading", "Loading..."));
    try {
      const payload = await fetchJson(`${urls.decisions}?${query}`);
      if (!pageState.isCurrent(requestState)) return;
      renderDecisions(payload, connection);
    } catch (error) {
      if (!pageState.isCurrent(requestState)) return;
      renderDecisionNotice(error.message);
      showMessage(error.message);
    }
  };

  const fieldList = (fields, className = "row g-2 mb-0") => {
    const list = element("dl", className);
    fields.forEach(([label, value]) => {
      const column = element("div", "col-sm-6 col-xl-3");
      column.append(
        element("dt", "small text-muted fw-normal mb-0", label),
        element("dd", "mb-0 crowdsec-meta", value || "-"),
      );
      list.append(column);
    });
    return list;
  };

  const listCard = (title, details, badge) => {
    const card = element("article", "border rounded p-3 mb-2");
    const header = element(
      "div",
      "d-flex flex-wrap align-items-start justify-content-between gap-2 mb-3",
    );
    header.append(element("h6", "mb-0 crowdsec-meta", title));
    if (badge)
      header.append(element("span", "badge bg-secondary flex-shrink-0", badge));
    card.append(header);
    if (details.length) card.append(fieldList(details));
    return card;
  };

  const investigationGroups = [
    {
      key: "decisions",
      pane: "crowdsec-pane-decisions",
      label: ["crowdsec.investigation.summary_decisions", "CrowdSec decisions"],
      found: ["crowdsec.investigation.summary_active", "{{total}} active"],
      badge: ["crowdsec.current_state", "Current state"],
      badgeClass: "bg-warning text-dark",
      blocking: true,
    },
    {
      key: "bans",
      pane: "crowdsec-pane-bans",
      label: ["crowdsec.investigation.summary_bans", "Local BunkerWeb bans"],
      found: ["crowdsec.investigation.summary_active", "{{total}} active"],
      badge: ["crowdsec.current_state", "Current state"],
      badgeClass: "bg-warning text-dark",
      blocking: true,
    },
    {
      key: "alerts",
      pane: "crowdsec-pane-alerts",
      label: [
        "crowdsec.investigation.summary_alerts",
        "CrowdSec alert evidence",
      ],
      found: [
        "crowdsec.investigation.summary_available",
        "{{total}} available",
      ],
    },
    {
      key: "reports",
      pane: "crowdsec-pane-reports",
      label: ["crowdsec.investigation.summary_reports", "BunkerWeb reports"],
      found: ["crowdsec.investigation.summary_captured", "{{total}} captured"],
      badge: ["crowdsec.captured_history", "Captured history"],
      badgeClass: "bg-secondary",
    },
  ];

  // Unavailable evidence keeps its own tone: it never reads as "nothing found".
  const summaryTone = (group, section) => {
    if (!section.available)
      return [
        "is-unreadable",
        "",
        ["crowdsec.investigation.summary_unreadable", "Could not be read"],
      ];
    if (!section.total)
      return [
        "",
        "text-muted",
        ["crowdsec.investigation.summary_none", "None found"],
      ];
    return [
      group.blocking ? "is-blocking" : "is-evidence",
      group.blocking ? "text-danger" : "",
      group.found,
    ];
  };

  const activateInvestigationPane = (paneId) =>
    document
      .querySelectorAll("#crowdsec-investigation .tab-pane")
      .forEach((pane) => {
        pane.classList.toggle("show", pane.id === paneId);
        pane.classList.toggle("active", pane.id === paneId);
      });

  const renderInvestigationSummary = (sections) => {
    const container = byId("crowdsec-investigation-summary");
    container.replaceChildren();
    const active =
      investigationGroups.find(
        (group) => sections[group.key].available && sections[group.key].total,
      ) ||
      investigationGroups.find((group) => !sections[group.key].available) ||
      investigationGroups[0];
    investigationGroups.forEach((group) => {
      const section = sections[group.key];
      const [border, tone, state] = summaryTone(group, section);
      const selected = group === active;
      const column = element("div", "col");
      const tile = element(
        "button",
        `crowdsec-summary-tile card h-100 p-3 ${border} ${
          selected ? "active" : ""
        }`
          .replace(/\s+/g, " ")
          .trim(),
      );
      tile.type = "button";
      tile.id = `crowdsec-tab-${group.key}`;
      tile.dataset.bsToggle = "tab";
      tile.dataset.bsTarget = `#${group.pane}`;
      tile.setAttribute("role", "tab");
      tile.setAttribute("aria-controls", group.pane);
      tile.setAttribute("aria-selected", String(selected));
      const label = element(
        "span",
        "small text-muted",
        translated(group.label[0], group.label[1]),
      );
      label.dataset.i18n = group.label[0];
      const total = section.pageBounded ? `${section.total}+` : section.total;
      const status = element(
        "span",
        `fw-semibold ${tone}`.trim(),
        translated(state[0], state[1], { total }),
      );
      status.dataset.i18n = state[0];
      status.dataset.i18nOptions = JSON.stringify({ total });
      tile.append(label, status);
      if (group.badge) {
        const badge = element(
          "span",
          `badge ${group.badgeClass} align-self-start mt-2`,
          translated(group.badge[0], group.badge[1]),
        );
        badge.dataset.i18n = group.badge[0];
        tile.append(badge);
      }
      column.append(tile);
      container.append(column);
    });
    activateInvestigationPane(active.pane);
  };

  const renderInvestigationDecisions = (section, connection) => {
    const container = byId("crowdsec-investigation-decisions");
    container.replaceChildren();
    if (!section.available) {
      renderSectionUnavailable(container, section.error);
      return;
    }
    if (!section.items.length) {
      container.append(
        emptyState(
          translated(
            "crowdsec.investigation.no_decisions",
            "No current CrowdSec decision was found.",
          ),
        ),
      );
      return;
    }
    section.items.forEach((decision) => {
      const card = listCard(
        `${decision.scope || "-"} ${decision.value || "-"}`,
        [
          [translated("crowdsec.decision.type", "Type"), decision.type],
          [translated("crowdsec.decision.origin", "Origin"), decision.origin],
          [
            translated("crowdsec.decision.scenario", "Scenario"),
            decision.scenario,
          ],
          [
            translated("crowdsec.decision.duration", "Duration"),
            decision.duration,
          ],
        ],
        translated("crowdsec.current_state", "Current state"),
      );
      const button = removalButton(decision, connection);
      if (button) {
        button.classList.add("mt-3");
        card.append(button);
      }
      container.append(card);
    });
    appendTruncationNotice(container, section);
  };

  const renderBans = (section, observedAt) => {
    const container = byId("crowdsec-investigation-bans");
    container.replaceChildren();
    if (!section.available) {
      renderSectionUnavailable(container, section.error);
      return;
    }
    if (!section.items.length) {
      container.append(
        emptyState(
          translated(
            "crowdsec.investigation.no_bans",
            "No current local ban was found.",
          ),
        ),
      );
      return;
    }
    section.items.forEach((ban) => {
      const expiresAt = getCrowdSecBanExpiry(ban, observedAt);
      container.append(
        listCard(ban.ip || "-", [
          [translated("crowdsec.local_ban.reason", "Reason"), ban.reason],
          [translated("crowdsec.local_ban.service", "Service"), ban.service],
          [
            translated("crowdsec.local_ban.expires", "Expires"),
            ban.permanent
              ? translated("scope.permanent", "Permanent")
              : expiresAt !== null
                ? formatObserved(expiresAt)
                : translated("crowdsec.unknown", "Unknown"),
          ],
        ]),
      );
    });
    appendTruncationNotice(container, section);
  };

  const renderAlertEvidence = (container, alert) => {
    container.replaceChildren();
    const details = listCard(
      alert.message || alert.scenario || `#${alert.id}`,
      [
        [translated("crowdsec.alert.id", "Alert ID"), alert.id],
        [translated("crowdsec.decision.scenario", "Scenario"), alert.scenario],
        [
          translated("crowdsec.alert.started", "Started"),
          formatTime(alert.start_at),
        ],
        [
          translated("crowdsec.alert.stopped", "Stopped"),
          formatTime(alert.stop_at),
        ],
      ],
    );
    (alert.events || []).forEach((event) => {
      const eventBlock = element("div", "border-top pt-2 mt-2 small");
      eventBlock.append(
        element("strong", "d-block mb-1", formatTime(event.timestamp)),
      );
      (event.meta || []).forEach((meta) =>
        appendDetail(eventBlock, meta.key || "-", meta.value || "-"),
      );
      details.append(eventBlock);
    });
    container.append(details);
  };

  const loadAlert = async (alert, connection, container, button) => {
    if (!pageState.matchesConnection(connection.id)) return;
    button.disabled = true;
    const requestState = pageState.capture(`alert:${alert.id}`, {
      alert: alert.id,
      connection: connection.id,
    });
    try {
      const query = new URLSearchParams({ connection: connection.id });
      const payload = await fetchJson(`${urls.alert}/${alert.id}?${query}`);
      if (!pageState.isCurrent(requestState)) return;
      renderAlertEvidence(container, payload.alert || payload);
    } catch (error) {
      if (!pageState.isCurrent(requestState)) return;
      container.append(
        element("div", "alert alert-warning mb-0", error.message),
      );
      button.disabled = false;
    }
  };

  const renderAlerts = (section, connection) => {
    const container = byId("crowdsec-investigation-alerts");
    container.replaceChildren();
    if (!section.available) {
      renderSectionUnavailable(container, section.error);
      return;
    }
    if (!section.items.length) {
      container.append(
        emptyState(
          translated(
            "crowdsec.investigation.no_alerts",
            "No alert evidence is available.",
          ),
        ),
      );
      return;
    }
    section.items.forEach((alert) => {
      const wrapper = element("div");
      const card = listCard(alert.message || alert.scenario || `#${alert.id}`, [
        [translated("crowdsec.alert.id", "Alert ID"), alert.id],
        [
          translated("crowdsec.alert.started", "Started"),
          formatTime(alert.start_at),
        ],
      ]);
      const button = element(
        "button",
        "btn btn-sm btn-outline-primary mt-3",
        translated("crowdsec.alert.load", "Load full evidence"),
      );
      button.type = "button";
      button.addEventListener("click", () =>
        loadAlert(alert, connection, wrapper, button),
      );
      card.append(button);
      wrapper.append(card);
      container.append(wrapper);
    });
    appendTruncationNotice(container, section);
  };

  const reportSourceLabel = (source) =>
    ({
      lapi: translated("reports.crowdsec.source_lapi", "Local API decision"),
      appsec: translated("reports.crowdsec.source_appsec", "AppSec inspection"),
      failure_policy: translated(
        "reports.crowdsec.source_failure_policy",
        "AppSec failure policy",
      ),
    })[source] || translated("crowdsec.report.entry", "Security report");

  // Identifiers and snapshot bookkeeping stay reachable without crowding the card.
  const appendReportTechnical = (card, report, snapshot) => {
    const technical = element("details", "border-top pt-3 mt-3");
    technical.append(
      element(
        "summary",
        "text-muted small",
        translated("reports.crowdsec.technical_details", "Technical details"),
      ),
    );
    const fields = [
      [
        translated("crowdsec.report.identifier", "Report identifier"),
        report.id || report.request_id || report.url,
      ],
    ];
    if (snapshot) {
      fields.push(
        [
          translated("crowdsec.report.captured", "Captured at"),
          formatTime(snapshot.captured_at),
        ],
        [
          translated("crowdsec.report.source", "Captured source"),
          snapshot.source,
        ],
        [
          translated("crowdsec.report.scope", "Captured service scope"),
          snapshot.service_scope,
        ],
        [
          translated("crowdsec.report.matched_target", "Matched target"),
          snapshot.matched_target,
        ],
        [
          translated("crowdsec.report.metadata", "Decision metadata"),
          snapshot.metadataAvailable
            ? translated("crowdsec.report.metadata_complete", "Complete")
            : translated("crowdsec.report.metadata_incomplete", "Incomplete"),
        ],
      );
    }
    technical.append(fieldList(fields, "row g-2 mt-1 mb-0 small"));
    card.append(technical);
  };

  const appendCapturedDecisions = (card, snapshot) => {
    if (!snapshot || !snapshot.decisions.length) return;
    card.append(
      element(
        "h6",
        "mt-3 mb-2",
        translated("crowdsec.report.decisions", "Captured decisions"),
      ),
    );
    snapshot.decisions.forEach((decision) => {
      const captured = element(
        "div",
        "border-start border-3 border-secondary ps-3 py-2 mb-2",
      );
      captured.append(
        element(
          "p",
          "fw-semibold crowdsec-meta mb-2",
          decision.scenario || translated("crowdsec.unknown", "Unknown"),
        ),
      );
      captured.append(
        fieldList(
          [
            [translated("crowdsec.decision.origin", "Origin"), decision.origin],
            [translated("crowdsec.decision.scope", "Scope"), decision.scope],
            [translated("crowdsec.decision.target", "Target"), decision.target],
            [
              translated("crowdsec.decision.expires", "Expires"),
              decision.expires_at
                ? formatTime(decision.expires_at)
                : translated("crowdsec.unknown", "Unknown"),
            ],
            [translated("crowdsec.decision.id", "Decision ID"), decision.id],
          ],
          "row g-2 mb-0 small",
        ),
      );
      card.append(captured);
    });
    appendTruncationNotice(card, {
      shown: snapshot.decisions.length,
      total: snapshot.total,
      limit: snapshot.limit,
      truncated: snapshot.truncated,
    });
  };

  const renderReports = (section) => {
    const container = byId("crowdsec-investigation-reports");
    container.replaceChildren();
    if (!section.available) {
      renderSectionUnavailable(container, section.error);
      return;
    }
    if (!section.items.length) {
      container.append(
        emptyState(
          translated(
            "crowdsec.investigation.no_reports",
            "No recent captured report was found.",
          ),
        ),
      );
      return;
    }
    section.items.forEach((report) => {
      const snapshot = getCrowdSecReportSnapshot(report);
      const fields = [
        [
          translated("crowdsec.report.date", "Report time"),
          Number.isFinite(Number(report.date))
            ? formatObserved(report.date)
            : report.date,
        ],
        [translated("crowdsec.report.service", "Service"), report.server_name],
        [translated("crowdsec.report.reason", "Reason"), report.reason],
      ];
      if (snapshot)
        fields.push([
          translated("crowdsec.report.remediation", "Captured remediation"),
          snapshot.remediation,
        ]);
      const card = listCard(
        snapshot
          ? reportSourceLabel(snapshot.source)
          : translated("crowdsec.report.entry", "Security report"),
        fields,
        translated("crowdsec.captured_history", "Captured history"),
      );
      if (!snapshot || !snapshot.metadataAvailable) {
        card.append(
          element(
            "div",
            "alert alert-warning small mt-3 mb-0",
            snapshot
              ? translated(
                  "crowdsec.report.metadata_warning",
                  "Some captured decision metadata was unavailable at request time.",
                )
              : translated(
                  "crowdsec.report.metadata_unavailable",
                  "CrowdSec snapshot metadata is unavailable for this older report.",
                ),
          ),
        );
      }
      appendCapturedDecisions(card, snapshot);
      appendReportTechnical(card, report, snapshot);
      container.append(card);
    });
    appendTruncationNotice(container, section);
  };

  const loadAllowlists = async () => {
    const container = byId("crowdsec-allowlists");
    const count = byId("crowdsec-allowlists-count");
    const previous = byId("crowdsec-allowlists-prev");
    const next = byId("crowdsec-allowlists-next");
    previous.disabled = next.disabled = true;
    count.textContent = "";
    const connection = selectedConnection();
    if (!connection) {
      container.replaceChildren(
        emptyState(
          translated(
            "crowdsec.connection.required",
            "Choose a CrowdSec connection first.",
          ),
        ),
      );
      return;
    }
    const requestState = pageState.capture("allowlists");
    container.replaceChildren(
      emptyState(translated("status.loading", "Loading...")),
    );
    try {
      const query = new URLSearchParams({
        connection: connection.id,
        offset: allowlistOffset,
        limit: pageSize,
      });
      const payload = await fetchJson(`${urls.allowlists}?${query}`);
      if (!pageState.isCurrent(requestState)) return;
      const total = Number(payload.total || 0);
      if (total > 0 && allowlistOffset >= total) {
        allowlistOffset = 0;
        await loadAllowlists();
        return;
      }
      const items = Array.isArray(payload.allowlists) ? payload.allowlists : [];
      container.replaceChildren();
      if (!items.length)
        container.append(
          emptyState(
            translated(
              "crowdsec.allowlists.empty",
              "No allowlists were found on this engine.",
            ),
          ),
        );
      items.forEach((allowlist) => {
        const details = element("details", "border rounded p-3 mb-2");
        const summary = element("summary", "fw-semibold", allowlist.name);
        summary.append(
          element(
            "span",
            "badge bg-secondary ms-2",
            allowlist.console_managed
              ? translated("crowdsec.allowlists.console", "Console managed")
              : translated("crowdsec.allowlists.local", "Locally managed"),
          ),
        );
        details.append(summary);
        if (allowlist.description)
          details.append(
            element("p", "text-muted mt-2", allowlist.description),
          );
        const entries = Array.isArray(allowlist.items) ? allowlist.items : [];
        if (!entries.length)
          details.append(
            emptyState(
              translated(
                "crowdsec.allowlists.no_entries",
                "No active entries.",
              ),
            ),
          );
        entries.forEach((item) => {
          const raw = item.expiration;
          const never = !raw || raw.startsWith("0001-");
          const date = raw && new Date(raw);
          const expiration = never
            ? translated("crowdsec.allowlists.never", "Never")
            : Number.isFinite(date.getTime())
              ? date.toLocaleString()
              : translated("crowdsec.unknown", "Unknown");
          details.append(
            listCard(item.value, [
              [
                translated("crowdsec.allowlists.comment", "Comment"),
                item.description,
              ],
              [translated("crowdsec.decision.expires", "Expires"), expiration],
            ]),
          );
        });
        appendTruncationNotice(details, {
          shown: entries.length,
          total: allowlist.total,
          limit: allowlist.limit,
          truncated: allowlist.total > entries.length,
        });
        container.append(details);
      });
      count.textContent = translated(
        "crowdsec.decisions.count",
        "Showing {{start}}–{{end}} of {{total}}",
        {
          start: total ? allowlistOffset + 1 : 0,
          end: Math.min(allowlistOffset + items.length, total),
          total,
        },
      );
      previous.disabled = allowlistOffset === 0;
      next.disabled = allowlistOffset + items.length >= total;
    } catch (error) {
      if (!pageState.isCurrent(requestState)) return;
      renderSectionUnavailable(container, error.message);
    }
  };

  const renderAllowlistCheck = (payload) => {
    const container = byId("crowdsec-investigation-allowlist");
    container.replaceChildren();
    const result = payload.allowlist;
    if (!result || typeof result.allowlisted !== "boolean") {
      renderSectionUnavailable(
        container,
        payload.errors?.allowlist ||
          translated(
            "crowdsec.allowlists.unknown",
            "Allowlist status is unavailable.",
          ),
      );
      return;
    }
    if (!result.allowlisted) {
      container.append(
        emptyState(
          translated(
            "crowdsec.allowlists.not_allowed",
            "This IP does not match a CrowdSec allowlist.",
          ),
        ),
      );
      return;
    }
    const notice = element("div", "alert alert-info mb-0");
    notice.append(
      element(
        "strong",
        "d-block",
        translated("crowdsec.allowlists.allowed", "Allowlisted by CrowdSec"),
      ),
    );
    if (result.reason) notice.append(element("p", "my-2", result.reason));
    notice.append(
      element(
        "small",
        "d-block",
        translated(
          "crowdsec.allowlists.impact",
          "This is an engine-wide exception. Local BunkerWeb bans, other protections, or cached decisions can still block this IP.",
        ),
      ),
    );
    container.append(notice);
  };

  const renderInvestigation = (payload, connection, ip) => {
    const section = byId("crowdsec-investigation");
    section.classList.remove("d-none");
    byId("crowdsec-investigation-title").textContent = translated(
      "crowdsec.investigation.result",
      "Investigation for {{ip}}",
      { ip: payload.ip || ip },
    );
    byId("crowdsec-observed-at").textContent = translated(
      "crowdsec.observed_at",
      "Observed {{time}}",
      { time: formatObserved(payload.observed_at) },
    );
    const errors = byId("crowdsec-investigation-errors");
    errors.replaceChildren();
    Object.entries(payload.errors || {}).forEach(([part, message]) => {
      if (part !== "allowlist")
        errors.append(
          element("div", "alert alert-warning", `${part}: ${message}`),
        );
    });
    const sections = {
      decisions: getCrowdSecSection(payload, "decisions"),
      bans: getCrowdSecSection(payload, "bans"),
      alerts: getCrowdSecSection(payload, "alerts"),
      reports: getCrowdSecSection(payload, "reports"),
    };
    renderAllowlistCheck(payload);
    renderInvestigationDecisions(sections.decisions, connection);
    renderBans(sections.bans, payload.observed_at);
    renderAlerts(sections.alerts, connection);
    renderReports(sections.reports);
    renderInvestigationSummary(sections);
    section.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const investigate = async ({ preserveMessage = false } = {}) => {
    const ip = byId("crowdsec-ip").value.trim();
    const connection = selectedConnection();
    if (!connection) {
      showMessage(
        translated(
          "crowdsec.connection.required",
          "Choose a CrowdSec connection first.",
        ),
        "warning",
      );
      connectionGroup.querySelector("input:not(:disabled)")?.focus();
      return;
    }
    if (!preserveMessage) clearMessage();
    clearInvestigation();
    const requestState = pageState.capture("investigation", { ip });
    const query = new URLSearchParams({
      connection: connection.id,
      ip,
    });
    try {
      const payload = await fetchJson(`${urls.investigate}?${query}`);
      if (!pageState.isCurrent(requestState)) return;
      renderInvestigation(payload, connection, ip);
    } catch (error) {
      if (!pageState.isCurrent(requestState)) return;
      showMessage(error.message);
    }
  };

  const clearInvestigation = () => {
    byId("crowdsec-investigation").classList.add("d-none");
    byId("crowdsec-investigation-title").textContent = "";
    byId("crowdsec-observed-at").textContent = "";
    [
      "crowdsec-investigation-errors",
      "crowdsec-investigation-allowlist",
      "crowdsec-investigation-summary",
      "crowdsec-investigation-decisions",
      "crowdsec-investigation-bans",
      "crowdsec-investigation-alerts",
      "crowdsec-investigation-reports",
    ].forEach((id) => byId(id).replaceChildren());
    activateInvestigationPane("crowdsec-pane-decisions");
  };

  const resetPendingRemoval = () => {
    pendingRemoval = null;
    modalTrigger = null;
    byId("crowdsec-unban-confirm").checked = false;
    byId("crowdsec-unban-submit").disabled = true;
    byId("crowdsec-unban-selection").textContent = "";
    const modal = bootstrap.Modal.getInstance(byId("crowdsec-unban-modal"));
    if (modal) modal.hide();
  };

  const selectConnection = (id) => {
    if (!pageState.matchesConnection(id)) {
      pageState.switchConnection(id);
      resetPendingRemoval();
      clearInvestigation();
      decisionOffset = 0;
      allowlistOffset = 0;
    }
    connectionGroup.querySelectorAll('input[type="radio"]').forEach((radio) => {
      radio.checked = Boolean(id && radio.value === id);
      const card = radio.closest(".crowdsec-connection-card");
      card.classList.toggle("is-selected", radio.checked);
      card
        .querySelector(".crowdsec-selected-label")
        .classList.toggle("invisible", !radio.checked);
    });
    if (id) {
      const url = new URL(window.location.href);
      const fragment = new URLSearchParams(url.hash.slice(1));
      fragment.set("connection", id);
      url.hash = fragment.toString();
      url.searchParams.delete("connection");
      if (url.href !== window.location.href) {
        window.history.replaceState(window.history.state, "", url);
      }
    }
  };

  const loadConnections = async () => {
    clearMessage();
    const requestState = pageState.capture("connections");
    try {
      const payload = await fetchJson(urls.connections);
      if (!pageState.isCurrent(requestState)) return;
      selectConnection(renderConnections(payload));
      await Promise.all([loadDecisions(), loadAllowlists()]);
    } catch (error) {
      if (!pageState.isCurrent(requestState)) return;
      selectConnection(renderConnections({ connections: [], errors: {} }));
      showMessage(error.message);
    }
  };

  byId("crowdsec-refresh").addEventListener("click", loadConnections);
  connectionGroup.addEventListener("change", (event) => {
    if (
      !event.target.matches('input[name="crowdsec-connection"]') ||
      !event.target.checked
    )
      return;
    selectConnection(event.target.value);
    loadDecisions();
    loadAllowlists();
  });
  window.addEventListener("hashchange", () => {
    const id = preferredConnection();
    const changed = !pageState.matchesConnection(id);
    selectConnection(id);
    if (changed) {
      loadDecisions();
      loadAllowlists();
    }
  });
  byId("crowdsec-allowlists-refresh").addEventListener("click", loadAllowlists);
  byId("crowdsec-allowlists-prev").addEventListener("click", () => {
    allowlistOffset = Math.max(0, allowlistOffset - pageSize);
    loadAllowlists();
  });
  byId("crowdsec-allowlists-next").addEventListener("click", () => {
    allowlistOffset += pageSize;
    loadAllowlists();
  });
  byId("crowdsec-decision-filters").addEventListener("submit", (event) => {
    event.preventDefault();
    decisionOffset = 0;
    loadDecisions();
  });
  byId("crowdsec-decisions-prev").addEventListener("click", () => {
    decisionOffset = Math.max(0, decisionOffset - pageSize);
    loadDecisions();
  });
  byId("crowdsec-decisions-next").addEventListener("click", () => {
    decisionOffset += pageSize;
    loadDecisions();
  });
  byId("crowdsec-investigate-form").addEventListener("submit", (event) => {
    event.preventDefault();
    investigate();
  });
  byId("crowdsec-unban-confirm").addEventListener("change", (event) => {
    byId("crowdsec-unban-submit").disabled = !event.target.checked;
  });
  byId("crowdsec-unban-modal").addEventListener("shown.bs.modal", () => {
    if (
      !pendingRemoval ||
      !pageState.matchesConnection(pendingRemoval.connection.id)
    ) {
      bootstrap.Modal.getOrCreateInstance(byId("crowdsec-unban-modal")).hide();
    }
  });
  byId("crowdsec-unban-modal").addEventListener("hidden.bs.modal", () => {
    if (modalTrigger && modalTrigger.isConnected) modalTrigger.focus();
    modalTrigger = null;
  });
  byId("crowdsec-unban-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!pendingRemoval || !byId("crowdsec-unban-confirm").checked) return;
    const removal = pendingRemoval;
    if (!pageState.matchesConnection(removal.connection.id)) {
      resetPendingRemoval();
      return;
    }
    const data = new FormData();
    data.append("csrf_token", byId("crowdsec-csrf-token").value);
    data.append("confirmed", "yes");
    Object.entries(getCrowdSecRemovalParameters(removal)).forEach(
      ([key, value]) => data.append(key, value),
    );
    const requestState = pageState.capture("removal", {
      connection: removal.connection.id,
      decision: removal.decision.id,
    });
    const submit = byId("crowdsec-unban-submit");
    submit.disabled = true;
    try {
      const result = await fetchJson(urls.unban, {
        method: "POST",
        body: data,
      });
      if (!pageState.isCurrent(requestState)) return;
      bootstrap.Modal.getInstance(byId("crowdsec-unban-modal")).hide();
      pendingRemoval = null;
      const propagation = result.propagation || {};
      showMessage(
        translated(
          "crowdsec.remove.success",
          "Removed at the CrowdSec source. Propagation is {{status}} ({{mode}}, interval {{interval}}). {{remaining}} other matching decision(s) remain; local bans or AppSec may still block.",
          {
            status: propagation.status || "pending",
            mode: propagation.mode || "-",
            interval: propagation.interval || "-",
            remaining: Array.isArray(result.remaining_decisions)
              ? result.remaining_decisions.length
              : 0,
          },
        ),
        "success",
      );
      await loadDecisions();
      if (!byId("crowdsec-investigation").classList.contains("d-none")) {
        await investigate({ preserveMessage: true });
      }
    } catch (error) {
      if (!pageState.isCurrent(requestState)) return;
      showMessage(error.message);
      submit.disabled = false;
    }
  });

  const linkedIp = pageParams.get("ip");
  if (linkedIp) {
    byId("crowdsec-ip").value = linkedIp;
    byId("crowdsec-filter-ip").value = linkedIp;
  }
  loadConnections().then(() => {
    if (linkedIp && pageState.connection()) investigate();
  });
});
