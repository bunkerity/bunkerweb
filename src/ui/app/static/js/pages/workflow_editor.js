/* Security workflow rule editor.
 *
 * Ordered cards, not a canvas: a workflow is a list of rules evaluated top to bottom, and
 * the first effective match wins, so the vertical order on screen *is* the semantics.
 *
 * The editor never decides what is valid. It serialises the cards into the canonical
 * definition and asks the API, which runs the same validator the database and the compiler
 * run — so "it validates here" means "it will save and it will compile".
 *
 * PRO extension point: condition and action types come from window.BW_WORKFLOW_TYPES. A PRO
 * bundle pushes its own entries before DOMContentLoaded and gets them in the same selectors,
 * on the same page — no fork, no second editor.
 */
(function () {
  "use strict";

  window.BW_WORKFLOW_TYPES = window.BW_WORKFLOW_TYPES || {
    conditions: [
      {
        op: "ip",
        label: "IP / CIDR",
        kind: "list",
        placeholder: "203.0.113.0/24",
      },
      { op: "country", label: "Country", kind: "list", placeholder: "FR" },
      { op: "asn", label: "ASN", kind: "list", placeholder: "64496" },
      { op: "method", label: "HTTP method", kind: "list", placeholder: "POST" },
      { op: "uri", label: "URI", kind: "uri" },
      { op: "group", label: "Resource group", kind: "group" },
    ],
    actions: [
      { type: "challenge", label: "Show a challenge" },
      { type: "block", label: "Block" },
      { type: "redirect", label: "Redirect" },
    ],
  };

  // Mirrors workflow_schema.MAX_TREE_DEPTH; the API refuses anything deeper anyway, this
  // only stops the operator building something that cannot be saved.
  var MAX_DEPTH = 5;
  var CHALLENGE_PROVIDERS = [
    "cookie",
    "javascript",
    "captcha",
    "recaptcha",
    "hcaptcha",
    "turnstile",
    "mcaptcha",
    "capjs",
  ];
  var REDIRECT_STATUSES = [301, 302, 303, 307, 308];
  var GROUP_KINDS = ["ip", "country", "asn"];

  var rulesEl,
    emptyEl,
    validationEl,
    readonly = false,
    groups = {},
    validateTimer = null;

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function option(value, label, selected) {
    var node = el("option", null, label);
    node.value = value;
    if (selected) node.selected = true;
    return node;
  }

  function conditionSpec(op) {
    var list = window.BW_WORKFLOW_TYPES.conditions;
    for (var i = 0; i < list.length; i++) {
      if (list[i].op === op) return list[i];
    }
    return list[0];
  }

  // ---- node rendering --------------------------------------------------------------

  function renderNode(node, depth) {
    if (node && (node.op === "all" || node.op === "any"))
      return renderCombinator(node, depth);
    if (node && node.op === "not") return renderNot(node, depth);
    return renderLeaf(node || { op: "ip", values: [] });
  }

  function nodeToolbar(container, depth, onAddLeaf, onAddGroup, onRemove) {
    var bar = el("div", "d-flex gap-2 mt-2");
    var addLeaf = el(
      "button",
      "btn btn-outline-secondary btn-sm",
      "+ condition",
    );
    addLeaf.type = "button";
    addLeaf.addEventListener("click", onAddLeaf);
    bar.appendChild(addLeaf);

    var addGroup = el("button", "btn btn-outline-secondary btn-sm", "+ group");
    addGroup.type = "button";
    // Nothing deeper than MAX_DEPTH can be saved, so the button turns itself off rather
    // than letting the operator build a tree the API will reject.
    if (depth >= MAX_DEPTH - 1) addGroup.disabled = true;
    addGroup.addEventListener("click", onAddGroup);
    bar.appendChild(addGroup);

    if (onRemove) {
      var remove = el(
        "button",
        "btn btn-outline-danger btn-sm ms-auto",
        "remove group",
      );
      remove.type = "button";
      remove.addEventListener("click", onRemove);
      bar.appendChild(remove);
    }
    container.appendChild(bar);
  }

  function renderCombinator(node, depth) {
    var wrapper = el(
      "fieldset",
      "wf-node wf-combinator border-start ps-3 py-2",
    );
    wrapper.dataset.op = node.op;
    wrapper.dataset.depth = String(depth);

    var head = el("div", "d-flex align-items-center gap-2 mb-2");
    var select = el(
      "select",
      "form-select form-select-sm w-auto wf-combinator-op",
    );
    select.appendChild(option("all", "Match ALL of", node.op === "all"));
    select.appendChild(option("any", "Match ANY of", node.op === "any"));
    select.addEventListener("change", function () {
      wrapper.dataset.op = select.value;
      scheduleValidate();
    });
    head.appendChild(select);
    wrapper.appendChild(head);

    var children = el("div", "wf-children");
    (node.nodes || []).forEach(function (child) {
      children.appendChild(renderNode(child, depth + 1));
    });
    wrapper.appendChild(children);

    nodeToolbar(
      wrapper,
      depth,
      function () {
        children.appendChild(renderLeaf({ op: "ip", values: [] }));
        scheduleValidate();
      },
      function () {
        children.appendChild(
          renderCombinator(
            { op: "all", nodes: [{ op: "ip", values: [] }] },
            depth + 1,
          ),
        );
        scheduleValidate();
      },
      depth > 1
        ? function () {
            wrapper.remove();
            scheduleValidate();
          }
        : null,
    );
    return wrapper;
  }

  function renderNot(node, depth) {
    // NOT holds exactly one child, so it renders as a modifier on that child rather than as
    // a container the operator could accidentally leave empty.
    var inner = renderNode(node.node, depth);
    inner.dataset.negated = "yes";
    var toggle = inner.querySelector(".wf-negate");
    if (toggle) toggle.checked = true;
    return inner;
  }

  function renderLeaf(node) {
    var wrapper = el(
      "div",
      "wf-node wf-leaf d-flex flex-wrap gap-2 align-items-center mb-2",
    );
    wrapper.dataset.op = node.op;

    var negate = el("div", "form-check form-switch mb-0");
    var negateInput = el("input", "form-check-input wf-negate");
    negateInput.type = "checkbox";
    negateInput.setAttribute("role", "switch");
    negateInput.setAttribute("aria-label", "Negate this condition");
    negate.appendChild(negateInput);
    var negateLabel = el("label", "form-check-label small", "not");
    negate.appendChild(negateLabel);
    negateInput.addEventListener("change", function () {
      wrapper.dataset.negated = negateInput.checked ? "yes" : "";
      scheduleValidate();
    });
    wrapper.appendChild(negate);

    var opSelect = el("select", "form-select form-select-sm w-auto wf-leaf-op");
    window.BW_WORKFLOW_TYPES.conditions.forEach(function (spec) {
      opSelect.appendChild(option(spec.op, spec.label, spec.op === node.op));
    });
    wrapper.appendChild(opSelect);

    var args = el(
      "div",
      "wf-leaf-args d-flex flex-wrap gap-2 align-items-center flex-grow-1",
    );
    wrapper.appendChild(args);

    var remove = el("button", "btn btn-outline-danger btn-sm", "×");
    remove.type = "button";
    remove.setAttribute("aria-label", "Remove this condition");
    remove.addEventListener("click", function () {
      wrapper.remove();
      scheduleValidate();
    });
    wrapper.appendChild(remove);

    opSelect.addEventListener("change", function () {
      wrapper.dataset.op = opSelect.value;
      renderLeafArgs(args, { op: opSelect.value });
      scheduleValidate();
    });
    renderLeafArgs(args, node);
    return wrapper;
  }

  function renderLeafArgs(container, node) {
    container.innerHTML = "";
    var spec = conditionSpec(node.op);

    if (spec.kind === "uri") {
      var match = el(
        "select",
        "form-select form-select-sm w-auto wf-uri-match",
      );
      ["exact", "prefix", "regex"].forEach(function (value) {
        match.appendChild(option(value, value, node.match === value));
      });
      match.addEventListener("change", scheduleValidate);
      container.appendChild(match);

      var value = el(
        "input",
        "form-control form-control-sm wf-uri-value flex-grow-1",
      );
      value.placeholder = "/login";
      value.value = node.value || "";
      value.addEventListener("input", scheduleValidate);
      container.appendChild(value);
      return;
    }

    if (spec.kind === "group") {
      var kind = el(
        "select",
        "form-select form-select-sm w-auto wf-group-kind",
      );
      GROUP_KINDS.forEach(function (value) {
        kind.appendChild(option(value, value, node.kind === value));
      });
      container.appendChild(kind);

      var picker = el(
        "select",
        "form-select form-select-sm wf-group-id flex-grow-1",
      );
      var refresh = function () {
        picker.innerHTML = "";
        var selectedKind = kind.value;
        var found = false;
        Object.keys(groups).forEach(function (groupId) {
          var entries = (groups[groupId] || {}).entries || [];
          var holdsKind = entries.some(function (entry) {
            return entry.kind === selectedKind;
          });
          // Only groups actually holding that kind are offered: a reference to an empty
          // one is refused by the validator rather than quietly matching nothing.
          if (!holdsKind) return;
          found = true;
          picker.appendChild(
            option(
              groupId,
              (groups[groupId] || {}).name || groupId,
              node.group_id === groupId,
            ),
          );
        });
        if (!found)
          picker.appendChild(
            option("", "no group holds " + selectedKind + " entries", true),
          );
      };
      kind.addEventListener("change", function () {
        refresh();
        scheduleValidate();
      });
      picker.addEventListener("change", scheduleValidate);
      refresh();
      container.appendChild(picker);
      return;
    }

    var values = el(
      "input",
      "form-control form-control-sm wf-values flex-grow-1",
    );
    values.placeholder = spec.placeholder || "";
    values.value = (node.values || []).join(" ");
    values.addEventListener("input", scheduleValidate);
    container.appendChild(values);
    var help = el("span", "form-text", "space separated");
    container.appendChild(help);
  }

  // ---- serialisation ---------------------------------------------------------------

  function serializeNode(node) {
    var payload;
    if (node.classList.contains("wf-combinator")) {
      var children = node.querySelector(".wf-children");
      var nodes = [];
      Array.prototype.forEach.call(children.children, function (child) {
        if (child.classList.contains("wf-node"))
          nodes.push(serializeNode(child));
      });
      payload = { op: node.dataset.op || "all", nodes: nodes };
    } else {
      var op = node.dataset.op;
      if (op === "uri") {
        payload = {
          op: "uri",
          match: node.querySelector(".wf-uri-match").value,
          value: node.querySelector(".wf-uri-value").value.trim(),
        };
      } else if (op === "group") {
        payload = {
          op: "group",
          kind: node.querySelector(".wf-group-kind").value,
          group_id: node.querySelector(".wf-group-id").value,
        };
      } else {
        var raw = node.querySelector(".wf-values").value.trim();
        payload = { op: op, values: raw ? raw.split(/\s+/) : [] };
      }
    }
    if (node.dataset.negated === "yes") return { op: "not", node: payload };
    return payload;
  }

  function serializeRule(card) {
    var conditionRoot = card.querySelector(".wf-rule-condition > .wf-node");
    var rule = {
      id: card.dataset.ruleId,
      name: card.querySelector(".wf-rule-name").value.trim(),
      enabled: card.querySelector(".wf-rule-enabled").checked,
      condition: conditionRoot ? serializeNode(conditionRoot) : null,
      threshold: null,
      action: serializeAction(card),
    };
    if (card.querySelector(".wf-threshold-enabled").checked) {
      rule.threshold = {
        count: parseInt(card.querySelector(".wf-threshold-count").value, 10),
        window: parseInt(card.querySelector(".wf-threshold-window").value, 10),
        key: "ip",
      };
    }
    return rule;
  }

  function serializeAction(card) {
    var type = card.querySelector(".wf-action-type").value;
    var args = card.querySelector(".wf-action-args");
    if (type === "challenge")
      return {
        type: "challenge",
        provider: args.querySelector(".wf-provider").value,
      };
    if (type === "redirect") {
      return {
        type: "redirect",
        url: args.querySelector(".wf-redirect-url").value.trim(),
        status: parseInt(args.querySelector(".wf-redirect-status").value, 10),
      };
    }
    var status = args.querySelector(".wf-block-status");
    // An unset status means "use the instance's configured deny status".
    return status && status.checked
      ? { type: "block", status: 429 }
      : { type: "block" };
  }

  function serialize() {
    var rules = [];
    Array.prototype.forEach.call(
      rulesEl.querySelectorAll(".wf-rule"),
      function (card) {
        rules.push(serializeRule(card));
      },
    );
    return { schema_version: 1, rules: rules };
  }

  // ---- action arguments ------------------------------------------------------------

  function renderActionArgs(card, action) {
    var container = card.querySelector(".wf-action-args");
    container.innerHTML = "";
    var type = card.querySelector(".wf-action-type").value;

    if (type === "challenge") {
      var label = el("label", "form-label small", "Provider");
      container.appendChild(label);
      var provider = el("select", "form-select form-select-sm wf-provider");
      CHALLENGE_PROVIDERS.forEach(function (value) {
        provider.appendChild(
          option(value, value, action && action.provider === value),
        );
      });
      provider.addEventListener("change", scheduleValidate);
      container.appendChild(provider);
      return;
    }

    if (type === "redirect") {
      var row = el("div", "row g-2");
      var urlCol = el("div", "col-8");
      var url = el("input", "form-control form-control-sm wf-redirect-url");
      url.placeholder = "https://example.com/denied";
      url.value = (action && action.url) || "";
      url.addEventListener("input", scheduleValidate);
      urlCol.appendChild(url);
      row.appendChild(urlCol);

      var statusCol = el("div", "col-4");
      var status = el(
        "select",
        "form-select form-select-sm wf-redirect-status",
      );
      REDIRECT_STATUSES.forEach(function (value) {
        status.appendChild(
          option(
            String(value),
            String(value),
            action && action.status === value,
          ),
        );
      });
      status.addEventListener("change", scheduleValidate);
      statusCol.appendChild(status);
      row.appendChild(statusCol);
      container.appendChild(row);
      return;
    }

    var check = el("div", "form-check form-switch");
    var input = el("input", "form-check-input wf-block-status");
    input.type = "checkbox";
    input.setAttribute("role", "switch");
    input.checked = !!(action && action.status === 429);
    input.addEventListener("change", scheduleValidate);
    check.appendChild(input);
    check.appendChild(
      el(
        "label",
        "form-check-label small",
        "Answer 429 instead of the deny status",
      ),
    );
    container.appendChild(check);
  }

  // ---- rule cards ------------------------------------------------------------------

  function newRuleId() {
    if (window.crypto && window.crypto.randomUUID)
      return window.crypto.randomUUID().replace(/-/g, "");
    // Ids only have to be unique inside one workflow, never secret.
    return (
      "r" +
      Date.now().toString(16) +
      Math.floor(Math.random() * 1e6).toString(16)
    );
  }

  function addRule(rule) {
    var template = document.getElementById("wf-rule-template");
    var card = template.content.firstElementChild.cloneNode(true);
    card.dataset.ruleId = (rule && rule.id) || newRuleId();
    card.querySelector(".wf-rule-name").value = (rule && rule.name) || "";
    card.querySelector(".wf-rule-enabled").checked =
      !rule || rule.enabled !== false;

    card.querySelector(".wf-rule-condition").appendChild(
      renderNode(
        (rule && rule.condition) || {
          op: "all",
          nodes: [{ op: "ip", values: [] }],
        },
        1,
      ),
    );

    var thresholdToggle = card.querySelector(".wf-threshold-enabled");
    var thresholdFields = card.querySelectorAll(".wf-threshold-fields");
    var syncThreshold = function () {
      Array.prototype.forEach.call(thresholdFields, function (field) {
        field.classList.toggle("d-none", !thresholdToggle.checked);
      });
    };
    if (rule && rule.threshold) {
      thresholdToggle.checked = true;
      card.querySelector(".wf-threshold-count").value = rule.threshold.count;
      card.querySelector(".wf-threshold-window").value = rule.threshold.window;
    }
    syncThreshold();
    thresholdToggle.addEventListener("change", function () {
      syncThreshold();
      scheduleValidate();
    });

    var actionSelect = card.querySelector(".wf-action-type");
    window.BW_WORKFLOW_TYPES.actions.forEach(function (spec) {
      actionSelect.appendChild(
        option(
          spec.type,
          spec.label,
          rule && rule.action && rule.action.type === spec.type,
        ),
      );
    });
    actionSelect.addEventListener("change", function () {
      renderActionArgs(card, null);
      scheduleValidate();
    });
    renderActionArgs(card, rule && rule.action);

    card
      .querySelector(".wf-rule-name")
      .addEventListener("input", scheduleValidate);
    card
      .querySelector(".wf-rule-enabled")
      .addEventListener("change", scheduleValidate);
    card
      .querySelector(".wf-rule-remove")
      .addEventListener("click", function () {
        card.remove();
        syncEmpty();
        scheduleValidate();
      });
    card.querySelector(".wf-rule-up").addEventListener("click", function () {
      var previous = card.previousElementSibling;
      if (previous) rulesEl.insertBefore(card, previous);
      scheduleValidate();
    });
    card.querySelector(".wf-rule-down").addEventListener("click", function () {
      var next = card.nextElementSibling;
      if (next) rulesEl.insertBefore(next, card);
      scheduleValidate();
    });

    if (readonly) {
      Array.prototype.forEach.call(
        card.querySelectorAll("input, select, button, textarea"),
        function (field) {
          field.disabled = true;
        },
      );
    }

    rulesEl.appendChild(card);
    syncEmpty();
    return card;
  }

  function syncEmpty() {
    emptyEl.classList.toggle(
      "d-none",
      rulesEl.querySelectorAll(".wf-rule").length > 0,
    );
  }

  // ---- validation ------------------------------------------------------------------

  function scheduleValidate() {
    if (validateTimer) window.clearTimeout(validateTimer);
    validateTimer = window.setTimeout(validate, 400);
  }

  function clearErrors() {
    Array.prototype.forEach.call(
      rulesEl.querySelectorAll(".wf-rule-errors"),
      function (node) {
        node.textContent = "";
      },
    );
    Array.prototype.forEach.call(
      rulesEl.querySelectorAll(".wf-rule-summary"),
      function (node) {
        node.textContent = "";
      },
    );
  }

  function ruleCardAt(index) {
    return rulesEl.querySelectorAll(".wf-rule")[index] || null;
  }

  function paintErrors(errors) {
    (errors || []).forEach(function (error) {
      // Paths look like rules[2].condition.nodes[1]; the leading index is what tells us
      // which card owns the message.
      var match = /^rules\[(\d+)\]/.exec(error.path || "");
      var card = match ? ruleCardAt(parseInt(match[1], 10)) : null;
      var target = card ? card.querySelector(".wf-rule-errors") : validationEl;
      var line = el("div", null, (error.path || "") + " — " + error.message);
      if (target === validationEl) line.className = "alert alert-danger py-2";
      target.appendChild(line);
    });
  }

  function validate() {
    clearErrors();
    validationEl.innerHTML = "";
    fetch(document.getElementById("wf-validate-url").value, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRFToken": document.getElementById("wf-csrf").value,
      },
      body: JSON.stringify({ definition: serialize() }),
    })
      .then(function (response) {
        return response.json();
      })
      .then(function (body) {
        if (body.status !== "success") {
          validationEl.appendChild(
            el(
              "div",
              "alert alert-warning py-2",
              body.message || "Could not validate",
            ),
          );
          return;
        }
        if (body.valid) {
          (body.summaries || []).forEach(function (summary, index) {
            var card = ruleCardAt(index);
            if (card)
              card.querySelector(".wf-rule-summary").textContent =
                summary.summary;
          });
          return;
        }
        paintErrors(body.errors);
      })
      .catch(function () {
        validationEl.appendChild(
          el(
            "div",
            "alert alert-warning py-2",
            "Could not reach the validation endpoint",
          ),
        );
      });
  }

  function save() {
    var button = document.getElementById("wf-save");
    button.disabled = true;
    fetch(document.getElementById("wf-save-url").value, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRFToken": document.getElementById("wf-csrf").value,
      },
      body: JSON.stringify({ definition: serialize() }),
    })
      .then(function (response) {
        return response.json();
      })
      .then(function (body) {
        if (body.status === "success") {
          window.location.reload();
          return;
        }
        validationEl.innerHTML = "";
        validationEl.appendChild(
          el(
            "div",
            "alert alert-danger py-2",
            body.message || "Could not save",
          ),
        );
        button.disabled = false;
      })
      .catch(function () {
        validationEl.innerHTML = "";
        validationEl.appendChild(
          el(
            "div",
            "alert alert-danger py-2",
            "Could not reach the save endpoint",
          ),
        );
        button.disabled = false;
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    rulesEl = document.getElementById("wf-rules");
    emptyEl = document.getElementById("wf-empty");
    validationEl = document.getElementById("wf-validation");
    if (!rulesEl) return;

    readonly = document.getElementById("wf-readonly").value === "yes";
    try {
      groups = JSON.parse(document.getElementById("wf-groups").value || "{}");
    } catch (error) {
      groups = {};
    }

    var definition = { rules: [] };
    try {
      definition = JSON.parse(
        document.getElementById("wf-definition").value || "{}",
      );
    } catch (error) {
      definition = { rules: [] };
    }
    (definition.rules || []).forEach(addRule);
    syncEmpty();

    var addButton = document.getElementById("wf-add-rule");
    if (addButton) {
      addButton.addEventListener("click", function () {
        addRule(null);
        scheduleValidate();
      });
    }
    var saveButton = document.getElementById("wf-save");
    if (saveButton) saveButton.addEventListener("click", save);

    if (definition.rules && definition.rules.length) validate();
  });
})();
