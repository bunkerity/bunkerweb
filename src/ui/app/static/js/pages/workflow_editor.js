/* Security workflow rule editor — the bw-flow rule ladder.
 *
 * A workflow is an ORDERED list of rules evaluated top to bottom and the first effective
 * match wins, so the vertical order on screen *is* the semantics. The ladder draws exactly
 * that and nothing more: no canvas, no branching, no parallel path, no trigger — the
 * evaluation engine has none of those, and drawing one would promise a capability that
 * does not exist.
 *
 * The editor never decides what is valid. It serialises the ladder into the canonical
 * definition and asks the API, which runs the same validator the database and the compiler
 * run — so "it validates here" means "it will save and it will compile". Error paths come
 * back addressing one node (rules[2].condition.nodes[1].values[3]) and are painted onto
 * that exact node.
 *
 * Two addressing schemes live side by side, each doing one job:
 *   data-wf-node  the SCHEMA path — what the API's error paths address.
 *   data-wf-key   a client-side node identity — what mutations act on, so nothing has to
 *                 parse a path back into a tree.
 *
 * NOT is unary in the schema ({op:"not", node:{...}}), but reads best as a "None of" group.
 * The view keeps a NOT group and serialises it as not(any(...)) — identical semantics, and
 * it round-trips.
 *
 * PRO extension point: condition and action types come from window.BW_WORKFLOW_TYPES. A PRO
 * bundle pushes its own entries before DOMContentLoaded and gets them in the same menus, on
 * the same page — no fork, no second editor.
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
      { op: "asn", label: "ASN", kind: "list", placeholder: "AS64496" },
      { op: "method", label: "HTTP method", kind: "list", placeholder: "POST" },
      { op: "uri", label: "URI", kind: "uri" },
      {
        op: "group",
        label: translate("workflows.aria.resourceGroup", "Resource group"),
        kind: "group",
      },
    ],
    actions: [
      { type: "challenge", label: "Challenge", blurb: "Prove it is human" },
      { type: "block", label: "Block", blurb: "Deny the request" },
      { type: "redirect", label: "Redirect", blurb: "Send it elsewhere" },
    ],
  };

  // Mirrors workflow_schema.py. The API refuses anything past these anyway; the editor only
  // uses them to stop an operator building something that can never be saved.
  var MAX_DEPTH = 5;
  var MAX_RULES = 50;
  var MAX_PREDICATES_PER_RULE = 32;
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
  // A block rule normally answers the instance's configured deny status; 429 is the single
  // documented override, for a rule whose whole purpose is capping a rate.
  var BLOCK_STATUSES = [429];
  var GROUP_KINDS = ["ip", "country", "asn"];
  var URI_MATCHES = {
    exact: "is exactly",
    prefix: "starts with",
    regex: "matches the regex",
  };
  var VALUE_CAP = 8;

  var LEAF_META = {
    ip: { icon: "bx-network-chart", verb: "is in", mono: true },
    country: { icon: "bx-flag", verb: "is" },
    asn: { icon: "bx-sitemap", verb: "is", mono: true },
    method: { icon: "bx-transfer", verb: "is" },
    uri: { icon: "bx-link", verb: "matches", mono: true },
    group: { icon: "bx-collection", verb: "is in the group" },
  };
  var ACTION_META = {
    block: { icon: "bx-block", tone: "t-block" },
    redirect: { icon: "bx-log-out-circle", tone: "t-redirect" },
    challenge: { icon: "bx-shield-quarter", tone: "t-challenge" },
  };
  var OPS = { all: "All of", any: "Any of", not: "None of" };

  var STATE = {
    rules: [],
    open: null,
    shown: null,
    errors: {},
    errorList: [],
    summaries: {},
    readonly: false,
    groups: {},
    // Which workflow this page edits, so a test result can tell this workflow's rules from
    // the other workflows attached to the same service.
    workflowId: "",
    // Last test result, or null. Pins the ladder's dimming and feeds the verdict chips.
    test: null,
  };

  var ladderEl, emptyEl, panelEl, liveEl, capEl;
  var validateTimer = null;
  var keySeed = 0;
  var dragId = null;

  // ---- helpers ---------------------------------------------------------------------

  function esc(value) {
    return String(value === null || value === undefined ? "" : value).replace(
      /[&<>"']/g,
      function (char) {
        return {
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        }[char];
      },
    );
  }

  function conditionSpec(op) {
    var list = window.BW_WORKFLOW_TYPES.conditions;
    for (var i = 0; i < list.length; i++) {
      if (list[i].op === op) return list[i];
    }
    return list[0];
  }

  function leafMeta(op) {
    return LEAF_META[op] || { icon: "bx-filter-alt", verb: "matches" };
  }

  function actionMeta(type) {
    return ACTION_META[type] || { icon: "bx-run", tone: "t-block" };
  }

  function newId() {
    if (window.crypto && window.crypto.randomUUID)
      return window.crypto.randomUUID().replace(/-/g, "");
    // Ids only have to be unique inside one workflow, never secret.
    return (
      "r" +
      Date.now().toString(16) +
      Math.floor(Math.random() * 1e6).toString(16)
    );
  }

  /* Same helper five other pages already carry (groups.js, upstreams.js, redirects.js,
     certificates.js, service-resources.js). escapeValue is off because every value that ends
     up in markup has already been through esc() — letting i18next escape it again yields
     &amp;lt; in a rule name. */
  function interpolate(text, options) {
    if (!options) return text;
    return String(text).replace(/\{\{(\w+)\}\}/g, function (whole, name) {
      return Object.prototype.hasOwnProperty.call(options, name)
        ? String(options[name])
        : whole;
    });
  }

  function translate(key, fallback, options) {
    if (typeof i18next === "undefined" || !i18next.isInitialized)
      // This file is deferred and the ladder draws before i18next finishes its async init,
      // so the fallback path is a normal first paint, not an edge case. Interpolate it the
      // same way i18next would or the operator reads a literal "Rule {{n}}".
      return interpolate(fallback, options);
    var settings = {
      defaultValue: fallback,
      interpolation: { escapeValue: false },
    };
    for (var name in options || {}) {
      if (Object.prototype.hasOwnProperty.call(options, name))
        settings[name] = options[name];
    }
    return i18next.t(key, settings);
  }

  /* The ladder is rebuilt from scratch on every mutation, so the global pass that i18n.js
     runs once at init is undone the moment anything changes. Without re-running it here
     every data-i18n this file emits renders its English fallback, in all 17 locales. */
  function runTranslations() {
    if (
      typeof window !== "undefined" &&
      typeof window.applyTranslations === "function"
    ) {
      window.applyTranslations();
    } else if (typeof applyTranslations === "function") {
      applyTranslations();
    }
  }

  /* A rule with no name still has to be referable in an announcement. */
  function ruleLabel(rule) {
    return (
      (rule && rule.name && rule.name.trim()) ||
      translate("workflows.say.theRule", "The rule")
    );
  }

  function say(message) {
    if (liveEl) liveEl.textContent = message;
  }

  // ---- view model ------------------------------------------------------------------

  function key(node) {
    node._k = "n" + ++keySeed;
    return node;
  }

  /* Schema -> view. The only rewrite is NOT: the schema holds exactly one child, the view
     holds a "None of" group, and not(any(...)) is the canonical form of both. An older
     not(<leaf>) becomes a one-child group, which serialises back as not(any([leaf])) — the
     same meaning, so nothing is lost. */
  function fromSchema(node) {
    if (!node || typeof node !== "object") return key({ op: "ip", values: [] });
    if (node.op === "all" || node.op === "any") {
      return key({ op: node.op, nodes: (node.nodes || []).map(fromSchema) });
    }
    if (node.op === "not") {
      var inner = node.node;
      if (inner && inner.op === "any")
        return key({ op: "not", nodes: (inner.nodes || []).map(fromSchema) });
      return key({ op: "not", nodes: inner ? [fromSchema(inner)] : [] });
    }
    if (node.op === "uri")
      return key({
        op: "uri",
        match: node.match || "prefix",
        value: node.value || "",
      });
    if (node.op === "group")
      return key({
        op: "group",
        kind: node.kind || "ip",
        group_id: node.group_id || "",
      });
    return key({
      op: node.op || "ip",
      values: (node.values || []).map(String),
    });
  }

  function toSchema(node) {
    if (node.op === "all" || node.op === "any") {
      return { op: node.op, nodes: node.nodes.map(toSchema) };
    }
    if (node.op === "not") {
      return {
        op: "not",
        node: { op: "any", nodes: node.nodes.map(toSchema) },
      };
    }
    if (node.op === "uri")
      return { op: "uri", match: node.match, value: node.value };
    if (node.op === "group")
      return { op: "group", kind: node.kind, group_id: node.group_id };
    return { op: node.op, values: node.values.slice() };
  }

  function serialize() {
    return {
      schema_version: 1,
      rules: STATE.rules.map(function (rule) {
        return {
          id: rule.id,
          name: rule.name,
          enabled: rule.enabled,
          condition: toSchema(rule.condition),
          threshold: rule.threshold
            ? {
                count: rule.threshold.count,
                window: rule.threshold.window,
                key: "ip",
              }
            : null,
          action: Object.assign({}, rule.action),
        };
      }),
    };
  }

  /* The serialised form as the server last confirmed it. Compared against serialize() rather
     than tracked with a flag so that undoing an edit by hand really does leave the page clean.
     Seeded AFTER fromSchemaRule normalisation — the NOT rewrite and the injected
     threshold.key would otherwise make an untouched page look dirty the moment it loads. */
  var savedJson = null;

  function markSaved() {
    savedJson = JSON.stringify(serialize());
  }

  function isDirty() {
    return savedJson !== null && JSON.stringify(serialize()) !== savedJson;
  }

  function isGroup(node) {
    return node.op === "all" || node.op === "any" || node.op === "not";
  }

  /* The model layer, exported on its own so it can be exercised without a DOM — the
     serialiser is the one thing here that, if it drifts from workflow_schema.py, makes every
     save fail. tests/unit/ui/test_workflow_editor_roundtrip.py runs it through the real
     validator. PRO bundles reuse it to seed rules. */
  window.BW_WORKFLOW_MODEL = {
    fromSchema: fromSchema,
    toSchema: toSchema,
    convertLeaf: convertLeaf,
  };

  /* Walks the whole ladder for one node key and returns it with its parent, so a mutation
     never has to parse a path back into a tree. */
  function locate(nodeKey) {
    var found = null;
    STATE.rules.forEach(function (rule) {
      if (found) return;
      (function walk(node, parent, index) {
        if (found) return;
        if (node._k === nodeKey) {
          found = { rule: rule, node: node, parent: parent, index: index };
          return;
        }
        if (isGroup(node))
          node.nodes.forEach(function (child, i) {
            walk(child, node, i);
          });
      })(rule.condition, null, -1);
    });
    return found;
  }

  function ruleById(id) {
    for (var i = 0; i < STATE.rules.length; i++) {
      if (STATE.rules[i].id === id) return STATE.rules[i];
    }
    return null;
  }

  function countLeaves(node) {
    return isGroup(node)
      ? node.nodes.reduce(function (total, child) {
          return total + countLeaves(child);
        }, 0)
      : 1;
  }

  function countRegex(rule) {
    return (function walk(node) {
      if (isGroup(node))
        return node.nodes.reduce(function (total, child) {
          return total + walk(child);
        }, 0);
      return node.op === "uri" && node.match === "regex" ? 1 : 0;
    })(rule.condition);
  }

  function newLeaf(op) {
    if (op === "uri") return key({ op: "uri", match: "prefix", value: "/" });
    if (op === "group")
      return key({ op: "group", kind: "ip", group_id: firstGroupFor("ip") });
    return key({ op: op, values: [] });
  }

  /* Switching a predicate's type used to replace the node outright, so picking "ASN" on a
     leaf holding forty typed addresses dropped all forty with no warning and no undo.
     ip/country/asn/method are all plain value lists, so the list survives the switch; what no
     longer belongs is flagged by the validator within 400ms — shown, not silently deleted.
     uri and group are deliberately not bridged: one holds a single string, the other a group
     reference, and carrying either across produces junk that is invalid on arrival. */
  function convertLeaf(node, op) {
    var next = newLeaf(op);
    if (next.values && node && node.values && node.values.length)
      next.values = node.values.slice();
    return next;
  }

  function carriesValues(node, op) {
    return !!(node && node.values && node.values.length && newLeaf(op).values);
  }

  function newRule() {
    return {
      id: newId(),
      name: "",
      enabled: true,
      condition: key({ op: "all", nodes: [newLeaf("uri")] }),
      threshold: null,
      action: { type: "block" },
    };
  }

  /* Only groups actually holding that kind are offered: a reference to one that holds none
     is refused by the validator rather than quietly matching nothing. */
  function groupsFor(kind) {
    return Object.keys(STATE.groups).filter(function (id) {
      return ((STATE.groups[id] || {}).entries || []).some(function (entry) {
        return entry.kind === kind;
      });
    });
  }

  function firstGroupFor(kind) {
    return groupsFor(kind)[0] || "";
  }

  function groupName(id) {
    return (STATE.groups[id] || {}).name || id;
  }

  // ---- rendering -------------------------------------------------------------------

  function errId(path) {
    return (
      "wf-err-" +
      String(path)
        .replace(/[^a-zA-Z0-9]+/g, "-")
        .replace(/^-|-$/g, "")
    );
  }

  function errorAt(path) {
    // A NOT group is not(any(...)) in the schema, so an error raised on the inner ANY
    // belongs to the group the operator can actually see.
    return STATE.errors[path] || STATE.errors[path + ".node"] || null;
  }

  function errBlock(path, message) {
    return (
      '<div class="bw-flow-err" id="' +
      errId(path) +
      '">' +
      '<i class="bx bx-error-circle" aria-hidden="true"></i><span>' +
      esc(message) +
      "</span></div>"
    );
  }

  function invalidAttrs(path, message) {
    return message
      ? ' aria-invalid="true" aria-describedby="' + errId(path) + '"'
      : "";
  }

  function selectHtml(cls, options, value, label) {
    var body = options
      .map(function (item) {
        var optValue = typeof item === "object" ? item.value : item;
        var optLabel = typeof item === "object" ? item.label : item;
        return (
          '<option value="' +
          esc(optValue) +
          '"' +
          (String(optValue) === String(value) ? " selected" : "") +
          ">" +
          esc(optLabel) +
          "</option>"
        );
      })
      .join("");
    return (
      '<select class="' +
      cls +
      '" aria-label="' +
      esc(label) +
      '"' +
      (STATE.readonly ? " disabled" : "") +
      ">" +
      body +
      "</select>"
    );
  }

  function valueChips(node, path) {
    var values = node.values || [];
    var open = STATE.shown.has(node._k);
    var list = open ? values : values.slice(0, VALUE_CAP);
    var messages = [];
    var html = list
      .map(function (value, index) {
        var valuePath = path + ".values[" + index + "]";
        var message = STATE.errors[valuePath];
        if (message) messages.push(errBlock(valuePath, message));
        var remove = STATE.readonly
          ? ""
          : '<button type="button" class="bw-flow-val-rm" data-wf-rmval="' +
            node._k +
            ":" +
            index +
            '" aria-label="' +
            esc(translate("workflows.aria.removeValue", "Remove value")) +
            " " +
            esc(value) +
            '">' +
            '<i class="bx bx-x" aria-hidden="true"></i></button>';
        // A flagged chip is focusable and names its own message, so the reason reaches
        // keyboard and screen-reader users instead of living in a colour alone.
        return (
          '<span class="bw-flow-val' +
          (message ? " bw-flow-invalid" : "") +
          '" data-wf-node="' +
          esc(valuePath) +
          '"' +
          (message ? ' tabindex="0"' : ' tabindex="-1"') +
          invalidAttrs(valuePath, message) +
          ">" +
          esc(value) +
          remove +
          "</span>"
        );
      })
      .join("");
    if (values.length > VALUE_CAP) {
      html +=
        '<button type="button" class="bw-flow-more" data-wf-morevals="' +
        node._k +
        '">' +
        (open
          ? translate("workflows.values.fewer", "Show fewer")
          : translate("workflows.values.more", "+{{n}} more", {
              n: values.length - VALUE_CAP,
            })) +
        "</button>";
    }
    if (!STATE.readonly) {
      html +=
        '<button type="button" class="bw-flow-add" data-wf-addval="' +
        node._k +
        '">' +
        '<i class="bx bx-plus" aria-hidden="true"></i><span data-i18n="workflows.value.add">Value</span></button>';
    }
    return '<div class="bw-flow-vals">' + html + "</div>" + messages.join("");
  }

  function leafBody(node, path) {
    if (node.op === "uri") {
      var valueMessage = STATE.errors[path + ".value"];
      if (STATE.readonly) {
        return (
          '<div class="bw-flow-vals"><span class="bw-flow-val' +
          (node.match === "regex" ? " is-regex" : "") +
          '">' +
          esc(node.value) +
          "</span></div>"
        );
      }
      return (
        '<div class="bw-flow-vals">' +
        '<input class="bw-flow-val-input' +
        (node.match === "regex" ? " is-regex" : "") +
        (valueMessage ? " bw-flow-invalid" : "") +
        '"' +
        ' data-wf-uri="' +
        node._k +
        '" data-wf-node="' +
        esc(path + ".value") +
        '" value="' +
        esc(node.value) +
        '"' +
        ' spellcheck="false" aria-label="' +
        esc(translate("workflows.aria.uriValue", "URI value")) +
        '"' +
        invalidAttrs(path + ".value", valueMessage) +
        ">" +
        "</div>" +
        (valueMessage ? errBlock(path + ".value", valueMessage) : "")
      );
    }
    if (node.op === "group") {
      var available = groupsFor(node.kind);
      var idMessage =
        STATE.errors[path + ".group_id"] || STATE.errors[path + ".kind"];
      var picker = available.length
        ? selectHtml(
            "bw-flow-val-input",
            available.map(function (id) {
              return { value: id, label: groupName(id) };
            }),
            node.group_id,
            translate("workflows.aria.resourceGroup", "Resource group"),
          )
        : '<span class="bw-flow-val">' +
          esc(
            translate(
              "workflows.tree.noGroupHolds",
              "no group holds {{kind}} entries",
              { kind: node.kind },
            ),
          ) +
          " entries</span>";
      return (
        '<div class="bw-flow-vals" data-wf-group="' +
        node._k +
        '" data-wf-node="' +
        esc(path + ".group_id") +
        '"' +
        invalidAttrs(path + ".group_id", idMessage) +
        ">" +
        selectHtml(
          "bw-flow-pred-op-select",
          GROUP_KINDS,
          node.kind,
          translate("workflows.aria.groupKind", "Group kind"),
        ) +
        picker +
        "</div>" +
        (idMessage ? errBlock(path + ".group_id", idMessage) : "")
      );
    }
    return valueChips(node, path);
  }

  function predicate(node, path) {
    var meta = leafMeta(node.op);
    var spec = conditionSpec(node.op);
    var message = errorAt(path);
    var verb =
      node.op === "uri"
        ? STATE.readonly
          ? URI_MATCHES[node.match] || "matches"
          : selectHtml(
              "bw-flow-pred-op-select",
              Object.keys(URI_MATCHES).map(function (k) {
                return { value: k, label: URI_MATCHES[k] };
              }),
              node.match,
              translate("workflows.aria.uriMatch", "URI match mode"),
            )
        : node.op === "group"
          ? translate("workflows.verb.isIn", "is in")
          : (node.values || []).length > 1
            ? translate("workflows.verb.isOneOf", "is one of")
            : translate("workflows.verb." + node.op, meta.verb);
    var typePicker = STATE.readonly
      ? "<span>" + esc(spec.label) + "</span>"
      : selectHtml(
          "bw-flow-pred-type-select",
          window.BW_WORKFLOW_TYPES.conditions.map(function (item) {
            return { value: item.op, label: item.label };
          }),
          node.op,
          translate("workflows.aria.conditionType", "Condition type"),
        );
    return (
      '<div class="bw-flow-pred' +
      (message ? " bw-flow-invalid" : "") +
      '" data-wf-node="' +
      esc(path) +
      '" data-wf-key="' +
      node._k +
      '"' +
      invalidAttrs(path, message) +
      ' tabindex="-1">' +
      '<span class="bw-flow-pred-type"><i class="bx ' +
      meta.icon +
      '" aria-hidden="true"></i>' +
      typePicker +
      "</span>" +
      '<span class="bw-flow-pred-op">' +
      verb +
      "</span>" +
      leafBody(node, path) +
      (STATE.readonly
        ? ""
        : '<button type="button" class="bw-flow-pred-rm" data-wf-rmnode="' +
          node._k +
          '" title="' +
          esc(translate("workflows.aria.removeCondition", "Remove condition")) +
          '" aria-label="' +
          esc(translate("workflows.aria.removeCondition", "Remove condition")) +
          '">' +
          '<i class="bx bx-trash" aria-hidden="true"></i></button>') +
      (message ? errBlock(path, message) : "") +
      "</div>"
    );
  }

  /* Schema depth, not view depth: a NOT group costs two levels because it serialises as
     not(any(...)). The button turns itself off at the cap rather than letting the operator
     build a tree the API will reject. */
  function childPath(node, path, index) {
    return node.op === "not"
      ? path + ".node.nodes[" + index + "]"
      : path + ".nodes[" + index + "]";
  }

  function cost(node) {
    return node.op === "not" ? 2 : 1;
  }

  function group(node, path, depth) {
    var message = errorAt(path);
    var children = node.nodes || [];
    var childDepth = depth + cost(node);
    var opLabel = OPS[node.op];
    var opButton = STATE.readonly
      ? '<span class="bw-flow-op op-' +
        node.op +
        `" data-i18n="workflows.tree.${node.op}">` +
        opLabel +
        "</span>"
      : '<button type="button" class="bw-flow-op op-' +
        node.op +
        '" data-wf-op="' +
        node._k +
        '"' +
        ' aria-label="' +
        esc(
          translate(
            "workflows.aria.combinator",
            "Change combinator, currently",
          ),
        ) +
        " " +
        esc(opLabel) +
        '">' +
        `<span data-i18n="workflows.tree.${node.op}">` +
        opLabel +
        "</span>" +
        '<i class="bx bx-chevron-down" aria-hidden="true"></i></button>';
    var meta =
      node.op === "not"
        ? translate(
            "workflows.tree.noneMeta",
            "matches when none of these are true",
          )
        : translate(
            node.op === "all"
              ? "workflows.tree.allMeta"
              : "workflows.tree.anyMeta",
            node.op === "all"
              ? "{{count}} condition(s) — all must be true"
              : "{{count}} condition(s) — at least one must be true",
            { count: children.length },
          );
    var join =
      node.op === "all"
        ? translate("workflows.tree.and", "and")
        : translate("workflows.tree.or", "or");
    var canNest = childDepth + 1 <= MAX_DEPTH;
    return (
      '<div class="bw-flow-group' +
      (message ? " bw-flow-invalid" : "") +
      '" data-depth="' +
      depth +
      '" data-wf-node="' +
      esc(path) +
      '" data-wf-key="' +
      node._k +
      '"' +
      invalidAttrs(path, message) +
      ' tabindex="-1">' +
      '<div class="bw-flow-group-head">' +
      opButton +
      '<span class="bw-flow-group-meta">' +
      esc(meta) +
      "</span></div>" +
      '<div class="bw-flow-kids">' +
      children
        .map(function (child, index) {
          var kidPath = childPath(node, path, index);
          return (
            '<div class="bw-flow-kid">' +
            (index > 0 ? '<div class="bw-flow-join">' + join + "</div>" : "") +
            (isGroup(child)
              ? group(child, kidPath, childDepth)
              : predicate(child, kidPath)) +
            "</div>"
          );
        })
        .join("") +
      (children.length
        ? ""
        : '<div class="bw-flow-group-meta" data-i18n="workflows.tree.empty">Empty group — add a condition, it cannot be saved like this.</div>') +
      "</div>" +
      (STATE.readonly
        ? ""
        : '<div class="bw-flow-addrow">' +
          '<button type="button" class="bw-flow-add" data-wf-addpred="' +
          node._k +
          '">' +
          '<i class="bx bx-plus" aria-hidden="true"></i><span data-i18n="workflows.tree.addCondition">Condition</span></button>' +
          '<button type="button" class="bw-flow-add" data-wf-addgroup="' +
          node._k +
          '"' +
          (canNest ? "" : " disabled") +
          ">" +
          '<i class="bx bx-layer-plus" aria-hidden="true"></i><span data-i18n="workflows.tree.addGroup">Group</span></button>' +
          (depth > 1
            ? '<button type="button" class="bw-flow-add" data-wf-rmnode="' +
              node._k +
              '">' +
              '<i class="bx bx-trash" aria-hidden="true"></i><span data-i18n="workflows.tree.removeGroup">Remove group</span></button>'
            : "") +
          "</div>") +
      (message ? errBlock(path, message) : "") +
      "</div>"
    );
  }

  /* The threshold is part of the "if": below it the rule simply does not match and
     evaluation continues downward. It is never an action. */
  function gate(rule, path) {
    if (!rule.threshold) {
      if (STATE.readonly) return "";
      return (
        '<div class="bw-flow-addrow"><button type="button" class="bw-flow-add" data-wf-addgate="' +
        esc(rule.id) +
        '">' +
        '<i class="bx bx-filter" aria-hidden="true"></i>' +
        '<span data-i18n="workflows.threshold">Only above a rate</span></button></div>'
      );
    }
    var message = errorAt(path + ".threshold");
    var disabled = STATE.readonly ? " disabled" : "";
    return (
      '<div class="bw-flow-gate' +
      (message ? " bw-flow-invalid" : "") +
      '" data-wf-node="' +
      esc(path + ".threshold") +
      '"' +
      invalidAttrs(path + ".threshold", message) +
      ' tabindex="-1">' +
      '<div class="bw-flow-gate-row">' +
      '<i class="bx bx-filter" aria-hidden="true"></i>' +
      '<span data-i18n="workflows.gate.and">and only once the same client IP has made more than</span>' +
      '<input class="bw-flow-gate-num" type="number" min="1" max="100000" value="' +
      esc(rule.threshold.count) +
      '"' +
      ' data-wf-gate="count" aria-label="' +
      esc(translate("workflows.aria.requestCount", "Request count")) +
      '"' +
      disabled +
      ">" +
      '<span data-i18n="workflows.threshold_count">Requests</span>' +
      '<input class="bw-flow-gate-num" type="number" min="1" max="86400" value="' +
      esc(rule.threshold.window) +
      '"' +
      ' data-wf-gate="window" aria-label="' +
      esc(translate("workflows.aria.window", "Window in seconds")) +
      '"' +
      disabled +
      ">" +
      '<span data-i18n="workflows.threshold_window">Per (seconds)</span>' +
      '<span class="bw-flow-chip" data-i18n="workflows.gate.chip">match gate</span>' +
      "</div>" +
      (STATE.readonly
        ? ""
        : '<button type="button" class="bw-flow-pred-rm" data-wf-rmgate="' +
          esc(rule.id) +
          '" title="' +
          esc(translate("workflows.aria.removeThreshold", "Remove threshold")) +
          '" aria-label="' +
          esc(
            translate(
              "workflows.aria.removeThresholdLong",
              "Remove rate threshold",
            ),
          ) +
          '">' +
          '<i class="bx bx-trash" aria-hidden="true"></i></button>') +
      '<p class="bw-flow-gate-help" data-i18n="workflows.gate.help">Counted per client IP. Below the threshold this rule does not match at all and evaluation carries on to the next rule — it never rate-limits on its own.</p>' +
      (message ? errBlock(path + ".threshold", message) : "") +
      "</div>"
    );
  }

  function actionParams(rule, path) {
    var action = rule.action;
    var disabled = STATE.readonly ? " disabled" : "";
    if (action.type === "redirect") {
      var urlMessage = STATE.errors[path + ".action.url"];
      return (
        '<div class="bw-flow-field" style="flex:1">' +
        '<label for="wf-act-url" data-i18n="workflows.act_url">Destination URL</label>' +
        '<input id="wf-act-url" class="mono' +
        (urlMessage ? " bw-flow-invalid" : "") +
        '" type="text" value="' +
        esc(action.url || "") +
        '"' +
        ' placeholder="https://example.com/denied" data-wf-param="url" spellcheck="false"' +
        ' data-wf-node="' +
        esc(path + ".action.url") +
        '"' +
        invalidAttrs(path + ".action.url", urlMessage) +
        disabled +
        ">" +
        (urlMessage ? errBlock(path + ".action.url", urlMessage) : "") +
        "</div>" +
        '<div class="bw-flow-field"><label for="wf-act-code" data-i18n="workflows.act_code">Status</label>' +
        selectHtml(
          "wf-act-status-select",
          REDIRECT_STATUSES,
          action.status || 302,
          translate("workflows.aria.redirectStatus", "Redirect status"),
        ) +
        "</div>"
      );
    }
    if (action.type === "challenge") {
      return (
        '<div class="bw-flow-field"><label for="wf-act-provider" data-i18n="workflows.act_provider">Antibot provider</label>' +
        selectHtml(
          "wf-act-provider-select",
          CHALLENGE_PROVIDERS,
          action.provider || "javascript",
          translate("workflows.aria.provider", "Antibot provider"),
        ) +
        "</div>"
      );
    }
    if (action.type === "block") {
      var options = [
        {
          value: "",
          label: translate(
            "workflows.act_denyDefault",
            "The instance's deny status",
          ),
        },
      ].concat(
        BLOCK_STATUSES.map(function (status) {
          return { value: status, label: String(status) };
        }),
      );
      return (
        '<div class="bw-flow-field"><label for="wf-act-status" data-i18n="workflows.act_status">Deny status</label>' +
        selectHtml(
          "wf-act-status-select",
          options,
          action.status === undefined || action.status === null
            ? ""
            : action.status,
          translate("workflows.aria.denyStatus", "Deny status"),
        ) +
        "</div>"
      );
    }
    return "";
  }

  function actionEditor(rule, path) {
    var message =
      STATE.errors[path + ".action"] || STATE.errors[path + ".action.type"];
    var picks = window.BW_WORKFLOW_TYPES.actions
      .map(function (spec) {
        var meta = actionMeta(spec.type);
        return (
          '<button type="button" class="bw-flow-pick" role="radio" aria-checked="' +
          (rule.action.type === spec.type ? "true" : "false") +
          '"' +
          ' data-wf-action="' +
          esc(spec.type) +
          '"' +
          (STATE.readonly ? " disabled" : "") +
          ">" +
          '<i class="bx ' +
          meta.icon +
          '" aria-hidden="true"></i>' +
          "<span><b" +
          // Only the built-in actions have a key. Emitting one for a PRO-registered type
          // would make i18next replace the label with the literal "workflows.act_<type>".
          (ACTION_META[spec.type]
            ? ` data-i18n="workflows.act_${esc(spec.type)}"`
            : "") +
          ">" +
          esc(spec.label) +
          "</b>" +
          "<span>" +
          esc(spec.blurb || "") +
          "</span></span></button>"
        );
      })
      .join("");
    return (
      '<div role="radiogroup" aria-label="' +
      esc(translate("workflows.aria.terminalAction", "Terminal action")) +
      '"><div class="bw-flow-acts">' +
      picks +
      "</div>" +
      '<div class="bw-flow-params" data-wf-node="' +
      esc(path + ".action") +
      '"' +
      invalidAttrs(path + ".action", message) +
      ' tabindex="-1">' +
      actionParams(rule, path) +
      "</div>" +
      (message ? errBlock(path + ".action", message) : "") +
      '<div class="bw-flow-terminalnote"><i class="bx bx-stop-circle" aria-hidden="true"></i>' +
      '<span data-i18n="workflows.act_terminal">One action per rule, and it ends evaluation — there is no true / false path out of a rule.</span></div>' +
      "</div>"
    );
  }

  function actionBadge(rule) {
    var meta = actionMeta(rule.action.type);
    var param =
      rule.action.type === "challenge"
        ? rule.action.provider || ""
        : rule.action.type === "redirect"
          ? rule.action.status || 302
          : rule.action.status ||
            translate("workflows.act_denyShort", "deny status");
    return (
      '<span class="bw-flow-act ' +
      meta.tone +
      (rule.enabled ? "" : " is-off") +
      '">' +
      '<i class="bx ' +
      meta.icon +
      '" aria-hidden="true"></i>' +
      "<span" +
      (ACTION_META[rule.action.type]
        ? ` data-i18n="workflows.act_${esc(rule.action.type)}"`
        : "") +
      ">" +
      esc(rule.action.type) +
      "</span>" +
      '<span class="p">' +
      esc(param) +
      "</span></span>"
    );
  }

  function ruleNode(rule, index) {
    var path = "rules[" + index + "]";
    var open = STATE.open.has(rule.id);
    var position = index + 1;
    var classes = ["bw-flow-node", "bw-flow-rule"];
    if (open) classes.push("is-open");
    if (!rule.enabled) classes.push("is-off");

    var name = STATE.readonly
      ? '<span class="bw-flow-head-name">' +
        (rule.name
          ? esc(rule.name)
          : '<span class="bw-flow-untitled" data-i18n="workflows.untitled">Untitled rule</span>') +
        "</span>"
      : '<input class="bw-flow-name-input wf-rule-name" maxlength="128" placeholder="' +
        esc(translate("workflows.rule.namePlaceholder", "Rule name")) +
        '" value="' +
        esc(rule.name) +
        '"' +
        ' data-wf-name="' +
        esc(rule.id) +
        '" aria-label="' +
        esc(
          translate("workflows.aria.ruleName", "Name of rule {{n}}", {
            n: position,
          }),
        ) +
        '">';

    var caret =
      '<button type="button" class="bw-flow-iconbtn" data-wf-toggleopen="' +
      esc(rule.id) +
      '" aria-expanded="' +
      (open ? "true" : "false") +
      '"' +
      ' title="' +
      (open
        ? translate("workflows.aria.collapse", "Collapse")
        : translate("workflows.aria.expand", "Expand")) +
      ' rule" aria-label="' +
      (open
        ? translate("workflows.aria.collapse", "Collapse")
        : translate("workflows.aria.expand", "Expand")) +
      " rule " +
      position +
      '">' +
      '<i class="bx bx-chevron-down bw-flow-caret" aria-hidden="true"></i></button>';
    var tools = STATE.readonly
      ? caret
      : '<button type="button" class="bw-flow-grip" data-wf-grip="' +
        esc(rule.id) +
        '" aria-hidden="true" tabindex="-1" title="' +
        esc(translate("workflows.aria.drag", "Drag to reorder")) +
        '">' +
        '<i class="bx bx-grid-vertical"></i></button>' +
        '<button type="button" class="bw-flow-iconbtn" data-wf-move="up:' +
        esc(rule.id) +
        '"' +
        (index === 0 ? " disabled" : "") +
        ' title="' +
        esc(translate("workflows.aria.moveUp", "Move up — runs earlier")) +
        '" aria-label="' +
        esc(translate("workflows.aria.moveRule", "Move rule")) +
        " " +
        position +
        ' up"><i class="bx bx-up-arrow-alt" aria-hidden="true"></i></button>' +
        '<button type="button" class="bw-flow-iconbtn" data-wf-move="down:' +
        esc(rule.id) +
        '"' +
        (index === STATE.rules.length - 1 ? " disabled" : "") +
        ' title="' +
        esc(translate("workflows.aria.moveDown", "Move down — runs later")) +
        '" aria-label="' +
        esc(translate("workflows.aria.moveRule", "Move rule")) +
        " " +
        position +
        ' down"><i class="bx bx-down-arrow-alt" aria-hidden="true"></i></button>' +
        '<button type="button" class="bw-flow-iconbtn" data-wf-menu="' +
        esc(rule.id) +
        '" aria-haspopup="menu" title="' +
        esc(translate("workflows.aria.more", "More")) +
        '"' +
        ' aria-label="More actions for rule ' +
        position +
        '"><i class="bx bx-dots-horizontal-rounded" aria-hidden="true"></i></button>' +
        caret;

    var summary = STATE.summaries[rule.id];
    var head =
      '<div class="bw-flow-head"><div class="bw-flow-head-main">' +
      '<div class="bw-flow-head-name">' +
      name +
      (rule.enabled
        ? ""
        : '<span class="bw-flow-chip" data-i18n="workflows.rule.disabled">Disabled</span>') +
      // Filled by paintTest(); empty until a test has run, so it costs nothing otherwise.
      '<span data-wf-verdict="' +
      esc(rule.id) +
      '"></span>' +
      "</div>" +
      '<div class="bw-flow-head-sum' +
      (summary ? "" : " is-pending") +
      '" data-wf-summary="' +
      esc(rule.id) +
      '">' +
      esc(summary || "Not validated yet") +
      "</div></div>" +
      actionBadge(rule) +
      '<div class="bw-flow-tools">' +
      tools +
      "</div></div>";

    var body = open
      ? '<div class="bw-flow-body">' +
        '<div class="bw-flow-clause is-if"><div class="bw-flow-clause-lbl" data-i18n="workflows.rule.if">If</div><div class="bw-flow-clause-main">' +
        group(rule.condition, path + ".condition", 1) +
        gate(rule, path) +
        "</div></div>" +
        '<div class="bw-flow-clause is-then"><div class="bw-flow-clause-lbl" data-i18n="workflows.action">Then</div><div class="bw-flow-clause-main">' +
        actionEditor(rule, path) +
        "</div></div></div>"
      : "";

    var foot = rule.enabled
      ? '<div class="bw-flow-foot"><i class="bx bx-check-circle" aria-hidden="true"></i>' +
        '<span><strong data-i18n="workflows.rule.onMatch">If it matches</strong>' +
        '<span data-i18n="workflows.rule.stopTail">, evaluation stops here — no rule below is reached.</span></span></div>'
      : '<div class="bw-flow-foot"><i class="bx bx-minus-circle" aria-hidden="true"></i>' +
        '<span data-i18n="workflows.rule.skipped">Disabled — skipped entirely, as if it were not in the list.</span></div>';

    return (
      '<article class="' +
      classes.join(" ") +
      '" data-wf-rule="' +
      esc(rule.id) +
      '" data-wf-node="' +
      esc(path) +
      '" tabindex="-1"' +
      ' aria-label="Rule ' +
      position +
      " of " +
      STATE.rules.length +
      " — " +
      esc(rule.name || "untitled") +
      '">' +
      head +
      body +
      foot +
      "</article>"
    );
  }

  function link(label, index) {
    return (
      '<div class="bw-flow-link" data-wf-link="' +
      index +
      '"><div class="bw-flow-link-line"></div>' +
      (label
        ? '<div class="bw-flow-link-lbl"><i class="bx bx-down-arrow-alt" aria-hidden="true"></i>' +
          '<span data-i18n="workflows.link.noMatch">' +
          label +
          "</span></div>"
        : "") +
      "</div>"
    );
  }

  function terminal(kind, title, subtitle, icon, i18n) {
    return (
      '<div class="bw-flow-item"><div class="bw-flow-rail"><span class="bw-flow-dot' +
      (kind === "end" ? " is-end" : "") +
      '"></span></div>' +
      '<div class="bw-flow-terminal' +
      (kind === "end" ? " is-end" : "") +
      '">' +
      '<span class="bw-flow-terminal-ic"><i class="bx ' +
      icon +
      '" aria-hidden="true"></i></span>' +
      '<div><strong data-i18n="' +
      i18n +
      '">' +
      title +
      '</strong><small data-i18n="' +
      i18n.replace("_title", "_sub") +
      '">' +
      subtitle +
      "</small></div></div></div>"
    );
  }

  function ladderHtml() {
    var html =
      '<div class="bw-flow"' +
      (STATE.readonly ? ' data-readonly="1"' : "") +
      " data-wf-ladder>";
    html += terminal(
      "entry",
      "Every request to an attached service",
      "Workflows run in attachment order; rules inside this one run top to bottom.",
      "bx-log-in-circle",
      "workflows.entry_title",
    );
    STATE.rules.forEach(function (rule, index) {
      html += link(index === 0 ? "" : "no match", index);
      html +=
        '<div class="bw-flow-item" data-wf-item="' +
        esc(rule.id) +
        '" data-wf-index="' +
        index +
        '">' +
        '<div class="bw-flow-rail">' +
        (STATE.readonly
          ? '<span class="bw-flow-mark' +
            (rule.enabled ? "" : " is-off") +
            '" aria-hidden="true">' +
            (index + 1) +
            "</span>"
          : '<button type="button" class="bw-flow-mark' +
            (rule.enabled ? "" : " is-off") +
            '" data-wf-pos="' +
            esc(rule.id) +
            '" aria-haspopup="menu"' +
            ' title="Position ' +
            (index + 1) +
            " of " +
            STATE.rules.length +
            ' — click to move"' +
            ' aria-label="Rule ' +
            (index + 1) +
            " of " +
            STATE.rules.length +
            ', change position">' +
            (index + 1) +
            "</button>") +
        "</div>" +
        ruleNode(rule, index) +
        "</div>";
    });
    html += link("no match", STATE.rules.length);
    html += terminal(
      "end",
      "No rule matched",
      "The request continues to the next attached workflow, then to the rest of the security stack.",
      "bx-log-out-circle",
      "workflows.exit_title",
    );
    return html + "</div>";
  }

  function capHtml() {
    var count = STATE.rules.length;
    if (!count) return "";
    // MAX_PREDICATES_PER_RULE is a per-rule cap, so the figure shown against it is the worst
    // single rule, never the workflow-wide sum.
    var worst = Math.max.apply(
      null,
      STATE.rules.map(function (rule) {
        return countLeaves(rule.condition);
      }),
    );
    var regexes = STATE.rules.reduce(function (total, rule) {
      return total + countRegex(rule);
    }, 0);
    var options = {
      count: count,
      maxRules: MAX_RULES,
      worst: worst,
      maxPredicates: MAX_PREDICATES_PER_RULE,
      regexes: regexes,
    };
    return (
      '<i class="bx bx-info-circle" aria-hidden="true"></i>' +
      '<span data-i18n="workflows.capacity" data-i18n-options=\'' +
      esc(JSON.stringify(options)) +
      "'>" +
      count +
      " of " +
      MAX_RULES +
      " rules · largest rule uses " +
      worst +
      " of " +
      MAX_PREDICATES_PER_RULE +
      " predicates · " +
      regexes +
      " regex" +
      (regexes === 1 ? "" : "es") +
      " in this workflow</span>"
    );
  }

  function render(focusSelector) {
    var count = STATE.rules.length;
    ladderEl.innerHTML = count ? ladderHtml() : "";
    ladderEl.classList.toggle("d-none", !count);
    emptyEl.classList.toggle("d-none", count > 0);
    capEl.innerHTML = capHtml();
    var addButton = document.getElementById("wf-add-rule");
    if (addButton && !STATE.readonly) addButton.disabled = count >= MAX_RULES;
    runTranslations();
    if (focusSelector) {
      var target = document.querySelector(focusSelector);
      if (target) target.focus({ preventScroll: true });
    }
  }

  // ---- validation painting ---------------------------------------------------------

  /* "rules[2].condition.nodes[1].values[3]" is an address, not a place. The operator gets the
     coordinate the ladder actually shows them; the raw path stays as the button's title so
     support can still ask for it. */
  function ruleIndexOf(path) {
    var match = /^rules\[(\d+)\]/.exec(path || "");
    return match ? parseInt(match[1], 10) : -1;
  }

  function errorLocation(path) {
    var index = ruleIndexOf(path);
    if (index < 0 || !STATE.rules[index])
      // Budget and provider refusals are a property of the whole document, not of one node.
      return translate("workflows.errors.whole", "This workflow");
    var rule = STATE.rules[index];
    var name = rule.name && rule.name.trim();
    return name
      ? translate("workflows.errors.ruleNamed", "Rule {{n}} — {{name}}", {
          n: index + 1,
          name: name,
        })
      : translate("workflows.errors.rule", "Rule {{n}}", { n: index + 1 });
  }

  function panelHtml() {
    if (!STATE.errorList.length) return "";
    var count = STATE.errorList.length;
    return (
      '<div class="alert alert-danger wf-errors" role="alert">' +
      '<strong data-i18n="workflows.errors.count" data-i18n-options=\'' +
      esc(JSON.stringify({ count: count })) +
      "'>" +
      count +
      (count === 1
        ? " problem blocks the save."
        : " problems block the save.") +
      "</strong> " +
      '<span data-i18n="workflows.errors.body">Nothing is applied — the running policy is unchanged.</span>' +
      "<ol>" +
      STATE.errorList
        .map(function (error) {
          var jumpable = ruleIndexOf(error.path) >= 0;
          var label =
            '<span class="wf-err-where">' +
            esc(errorLocation(error.path)) +
            "</span>" +
            esc(error.message);
          // A non-jumpable path had a live button that did nothing when clicked.
          return jumpable
            ? '<li><button type="button" class="wf-err-jump" data-wf-jump="' +
                esc(error.path) +
                '" title="' +
                esc(error.path + " · " + error.code) +
                '">' +
                label +
                "</button></li>"
            : '<li><span class="wf-err-static" title="' +
                esc(error.path + " · " + error.code) +
                '">' +
                label +
                "</span></li>";
        })
        .join("") +
      "</ol></div>"
    );
  }

  /* Paints the API's answer without re-rendering: a re-render while someone is typing in a
     value would take the caret with it. */
  function paint() {
    Array.prototype.forEach.call(
      ladderEl.querySelectorAll(".bw-flow-invalid"),
      function (node) {
        node.classList.remove("bw-flow-invalid");
        node.removeAttribute("aria-invalid");
        node.removeAttribute("aria-describedby");
      },
    );
    Array.prototype.forEach.call(
      ladderEl.querySelectorAll(".bw-flow-err"),
      function (node) {
        node.remove();
      },
    );

    Object.keys(STATE.errors).forEach(function (path) {
      var target = nodeAt(path);
      if (!target) return;
      target.classList.add("bw-flow-invalid");
      target.setAttribute("aria-invalid", "true");
      target.setAttribute("aria-describedby", errId(path));
      if (target.classList.contains("bw-flow-val"))
        target.setAttribute("tabindex", "0");
      var block = document.createElement("div");
      block.innerHTML = errBlock(path, STATE.errors[path]);
      var host =
        target.closest(
          ".bw-flow-pred, .bw-flow-group, .bw-flow-gate, .bw-flow-params, .bw-flow-field",
        ) || target;
      host.appendChild(block.firstChild);
    });

    STATE.rules.forEach(function (rule) {
      var host = ladderEl.querySelector(
        '[data-wf-summary="' + CSS.escape(rule.id) + '"]',
      );
      if (!host) return;
      var summary = STATE.summaries[rule.id];
      // Server summaries are English by design (workflow_schema.summarize_rule); only the
      // placeholder shown before the first validation is ours to translate.
      host.textContent =
        summary || translate("workflows.not_validated", "Not validated yet");
      host.classList.toggle("is-pending", !summary);
    });

    panelEl.innerHTML = panelHtml();
    // paint() writes its own markup too — the error panel and every inline message — so the
    // translation pass has to cover it, not just render().
    runTranslations();
  }

  /* An error path addresses a schema node; the closest rendered ancestor owns the message
     when the exact node has no element of its own (an unset URI value, for instance). */
  function nodeAt(path) {
    var probe = path;
    while (probe) {
      var found = ladderEl.querySelector(
        '[data-wf-node="' + CSS.escape(probe) + '"]',
      );
      if (found) return found;
      var cut = probe.replace(/(\.[a-z_]+|\[\d+\])$/, "");
      if (cut === probe) return null;
      probe = cut;
    }
    return null;
  }

  function jump(path) {
    var match = /^rules\[(\d+)\]/.exec(path);
    if (!match) return;
    var rule = STATE.rules[parseInt(match[1], 10)];
    if (!rule) return;
    STATE.open.add(rule.id);
    // A long value list may be hiding the offending chip — reveal it.
    var valueMatch = /\.values\[(\d+)\]$/.exec(path);
    if (valueMatch) {
      var owner = nodeOwnerKey(path.replace(/\.values\[\d+\]$/, ""));
      if (owner) STATE.shown.add(owner);
    }
    render();
    paint();
    // setTimeout, not requestAnimationFrame: rAF never fires while the page is in a hidden
    // or background frame, which would silently drop the landing.
    window.setTimeout(function () {
      var element = nodeAt(path);
      if (!element) return;
      var rect = element.getBoundingClientRect();
      if (rect.top < 80 || rect.bottom > window.innerHeight - 40) {
        window.scrollTo({ top: rect.top + window.scrollY - 160 });
      }
      element.classList.remove("bw-flow-flash");
      void element.offsetWidth;
      element.classList.add("bw-flow-flash");
      // Land on a real control inside the offending node when there is one, so keyboard and
      // screen-reader users can act on it — never on a destructive button.
      var focusable = element.matches("input, select")
        ? element
        : element.querySelector("input, select") || element;
      focusable.focus();
      // Never read the raw schema path aloud — announce where the operator now is.
      say(
        translate("workflows.say.jumped", "{{where}}: {{message}}", {
          where: errorLocation(path),
          message: STATE.errors[path] || "",
        }),
      );
    }, 0);
  }

  function nodeOwnerKey(path) {
    var element = ladderEl.querySelector(
      '[data-wf-node="' + CSS.escape(path) + '"]',
    );
    return element ? element.getAttribute("data-wf-key") : null;
  }

  // ---- mutations -------------------------------------------------------------------

  function touch(focusSelector) {
    // A verdict describes the ladder that produced it. The moment a rule changes it is
    // stale, and a stale verdict on a security rule is worse than none.
    if (STATE.test) clearTest();
    render(focusSelector);
    paint();
    scheduleValidate();
  }

  function moveRule(id, to, how) {
    var from = STATE.rules.findIndex(function (rule) {
      return rule.id === id;
    });
    if (from === -1) return;
    var total = STATE.rules.length;
    to = Math.max(0, Math.min(total - 1, to));
    if (to === from) return;
    var moved = STATE.rules.splice(from, 1)[0];
    STATE.rules.splice(to, 0, moved);
    touch('[data-wf-rule="' + CSS.escape(id) + '"]');
    // The announcement names the consequence, not the mechanic: position alone does not tell
    // an operator which rule now shadows which.
    var where =
      to === 0
        ? translate("workflows.say.runsFirst", "first")
        : to === total - 1
          ? translate("workflows.say.runsLast", "last")
          : translate("workflows.say.runsAfter", "after {{name}}", {
              name:
                (STATE.rules[to - 1].name || "").trim() ||
                translate("workflows.say.ruleAbove", "the rule above"),
            });
    say(
      translate(
        "workflows.say.moved",
        "{{name}} moved to position {{to}} of {{total}}{{how}}. It now runs {{where}}.",
        {
          name: ruleLabel(moved),
          to: to + 1,
          total: total,
          how: how ? " — " + translate("workflows.say.via." + how, how) : "",
          where: where,
        },
      ),
    );
  }

  function removeNode(nodeKey) {
    var hit = locate(nodeKey);
    if (!hit || !hit.parent) return;
    hit.parent.nodes.splice(hit.index, 1);
    touch();
  }

  // ---- popovers --------------------------------------------------------------------

  function closeMenus() {
    Array.prototype.forEach.call(
      document.querySelectorAll(".bw-flow-menu"),
      function (menu) {
        menu.remove();
      },
    );
  }

  function placeMenu(menu, anchor, alignRight) {
    var rect = anchor.getBoundingClientRect();
    document.body.appendChild(menu);
    var top = rect.bottom + window.scrollY + 6;
    if (rect.bottom + menu.offsetHeight + 12 > window.innerHeight) {
      top = Math.max(
        window.scrollY + 8,
        rect.top + window.scrollY - menu.offsetHeight - 6,
      );
    }
    menu.style.top = top + "px";
    menu.style.left =
      (alignRight
        ? Math.max(8, rect.right + window.scrollX - menu.offsetWidth)
        : rect.left + window.scrollX) + "px";
    var first = menu.querySelector("button:not([disabled])");
    if (first) first.focus();
  }

  function menuElement(dataset) {
    var menu = document.createElement("div");
    menu.className = "bw-flow-menu";
    menu.setAttribute("role", "menu");
    Object.keys(dataset).forEach(function (name) {
      menu.dataset[name] = dataset[name];
    });
    return menu;
  }

  function positionMenu(anchor, id) {
    closeMenus();
    var index = STATE.rules.findIndex(function (rule) {
      return rule.id === id;
    });
    var total = STATE.rules.length;
    var menu = menuElement({ rule: id });
    menu.innerHTML =
      '<div class="bw-flow-menu-hd">Runs at position ' +
      (index + 1) +
      " of " +
      total +
      "</div>" +
      '<button type="button" role="menuitem" data-wf-moveto="0"' +
      (index === 0 ? " disabled" : "") +
      ">" +
      '<i class="bx bx-chevrons-up" aria-hidden="true"></i><span data-i18n="workflows.move.first">Run first</span></button>' +
      '<button type="button" role="menuitem" data-wf-moveto="' +
      (total - 1) +
      '"' +
      (index === total - 1 ? " disabled" : "") +
      ">" +
      '<i class="bx bx-chevrons-down" aria-hidden="true"></i><span data-i18n="workflows.move.last">Run last</span></button>' +
      '<div class="sep"></div>' +
      STATE.rules
        .map(function (rule, position) {
          return (
            '<button type="button" role="menuitem" data-wf-moveto="' +
            position +
            '"' +
            (position === index ? " disabled" : "") +
            ">" +
            '<i class="bx ' +
            (position < index
              ? "bx-up-arrow-alt"
              : position > index
                ? "bx-down-arrow-alt"
                : "bx-check") +
            '" aria-hidden="true"></i>' +
            "<span>" +
            (position === index ? "Stays at" : "Move to") +
            " position " +
            (position + 1) +
            "</span>" +
            '<span class="n">' +
            esc((rule.name || "untitled").slice(0, 18)) +
            "</span></button>"
          );
        })
        .join("");
    placeMenu(menu, anchor);
  }

  function ruleMenu(anchor, id) {
    closeMenus();
    var index = STATE.rules.findIndex(function (rule) {
      return rule.id === id;
    });
    var rule = STATE.rules[index];
    var menu = menuElement({ rule: id });
    menu.innerHTML =
      '<button type="button" role="menuitem" data-wf-act="toggle"><i class="bx ' +
      (rule.enabled ? "bx-pause-circle" : "bx-play-circle") +
      '" aria-hidden="true"></i>' +
      // One key for a two-state label would translate a disabled rule's item as "Disable
      // rule". Pick the key, not just the fallback text.
      (rule.enabled
        ? '<span data-i18n="workflows.menu.disable">Disable rule</span>'
        : '<span data-i18n="workflows.menu.enable">Enable rule</span>') +
      "</button>" +
      '<button type="button" role="menuitem" data-wf-act="duplicate"' +
      (STATE.rules.length >= MAX_RULES ? " disabled" : "") +
      ">" +
      '<i class="bx bx-duplicate" aria-hidden="true"></i><span data-i18n="workflows.menu.duplicate">Duplicate below</span></button>' +
      '<div class="sep"></div>' +
      '<button type="button" role="menuitem" data-wf-act="top"' +
      (index === 0 ? " disabled" : "") +
      ">" +
      '<i class="bx bx-chevrons-up" aria-hidden="true"></i><span data-i18n="workflows.menu.top">Run first</span></button>' +
      '<button type="button" role="menuitem" data-wf-act="bottom"' +
      (index === STATE.rules.length - 1 ? " disabled" : "") +
      ">" +
      '<i class="bx bx-chevrons-down" aria-hidden="true"></i><span data-i18n="workflows.menu.bottom">Run last</span></button>' +
      '<div class="sep"></div>' +
      '<button type="button" role="menuitem" class="danger" data-wf-act="delete">' +
      '<i class="bx bx-trash" aria-hidden="true"></i><span data-i18n="workflows.menu.delete">Delete rule</span></button>';
    placeMenu(menu, anchor, true);
  }

  function opMenu(anchor, nodeKey) {
    closeMenus();
    var hit = locate(nodeKey);
    if (!hit) return;
    var menu = menuElement({ node: nodeKey });
    var items = [
      ["all", "All of", "Matches only when every condition inside is true."],
      ["any", "Any of", "Matches as soon as one condition inside is true."],
      [
        "not",
        "None of",
        "Matches when none of the conditions inside are true.",
      ],
    ];
    menu.innerHTML = items
      .map(function (item) {
        return (
          '<button type="button" role="menuitem" data-wf-setop="' +
          item[0] +
          '"' +
          (hit.node.op === item[0] ? " disabled" : "") +
          ">" +
          '<i class="bx ' +
          (hit.node.op === item[0] ? "bx-check" : "bx-radio-circle") +
          '" aria-hidden="true"></i>' +
          `<span><b data-i18n="workflows.tree.${item[0]}">` +
          item[1] +
          "</b></span></button>"
        );
      })
      .join("");
    placeMenu(menu, anchor);
  }

  function addConditionMenu(anchor, nodeKey) {
    closeMenus();
    var menu = menuElement({ node: nodeKey });
    menu.innerHTML = window.BW_WORKFLOW_TYPES.conditions
      .map(function (spec) {
        return (
          '<button type="button" role="menuitem" data-wf-newpred="' +
          esc(spec.op) +
          '">' +
          '<i class="bx ' +
          leafMeta(spec.op).icon +
          '" aria-hidden="true"></i><span>' +
          esc(spec.label) +
          "</span></button>"
        );
      })
      .join("");
    placeMenu(menu, anchor);
  }

  // ---- inline value entry ----------------------------------------------------------

  function inlineValue(host, nodeKey) {
    var hit = locate(nodeKey);
    if (!hit) return;
    var input = document.createElement("input");
    input.type = "text";
    input.className = "bw-flow-val-input";
    input.setAttribute("aria-label", "New value");
    input.placeholder = conditionSpec(hit.node.op).placeholder || "";
    host.replaceWith(input);
    input.focus();
    var done = false;
    var commit = function (keep) {
      if (done) return;
      done = true;
      var value = input.value.trim();
      if (keep && value) hit.node.values.push(value);
      touch();
    };
    input.addEventListener("keydown", function (event) {
      if (event.key === "Enter") {
        event.preventDefault();
        commit(true);
      }
      if (event.key === "Escape") {
        event.preventDefault();
        commit(false);
      }
    });
    input.addEventListener("blur", function () {
      commit(true);
    });
  }

  // ---- API -------------------------------------------------------------------------

  function post(url, body) {
    return fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRFToken": document.getElementById("wf-csrf").value,
      },
      body: JSON.stringify(body),
    }).then(function (response) {
      return response.json();
    });
  }

  function scheduleValidate() {
    if (validateTimer) window.clearTimeout(validateTimer);
    validateTimer = window.setTimeout(validate, 400);
  }

  function setErrors(errors) {
    STATE.errorList = errors || [];
    STATE.errors = {};
    STATE.errorList.forEach(function (error) {
      STATE.errors[error.path] = error.message;
    });
  }

  function validate() {
    if (!STATE.rules.length) {
      setErrors([]);
      STATE.summaries = {};
      paint();
      return;
    }
    post(document.getElementById("wf-validate-url").value, {
      definition: serialize(),
    })
      .then(function (body) {
        if (body.status !== "success") {
          panelEl.innerHTML =
            '<div class="alert alert-warning" role="alert">' +
            esc(
              body.message ||
                translate("workflows.err.validate", "Could not validate"),
            ) +
            "</div>";
          return;
        }
        if (body.valid) {
          setErrors([]);
          STATE.summaries = {};
          (body.summaries || []).forEach(function (entry, index) {
            var rule = STATE.rules[index];
            if (rule) STATE.summaries[rule.id] = entry.summary;
          });
        } else {
          setErrors(body.errors);
        }
        paint();
      })
      .catch(function () {
        panelEl.innerHTML =
          '<div class="alert alert-warning" role="alert">' +
          esc(
            translate(
              "workflows.err.validateUnreachable",
              "Could not reach the validation endpoint",
            ),
          ) +
          "</div>";
      });
  }

  function save() {
    var button = document.getElementById("wf-save");
    button.disabled = true;
    post(document.getElementById("wf-save-url").value, {
      definition: serialize(),
    })
      .then(function (body) {
        if (body.status === "success") {
          /* No reload. It only existed to surface a server flash, which an XHR endpoint
             should not be setting anyway — and it cost the operator their scroll position
             and every rule's open/closed state on every save. The API re-validates on save,
             so "success" means the client state IS the stored state. */
          markSaved();
          panelEl.innerHTML = "";
          button.disabled = false;
          say(
            translate(
              "workflows.say.saved",
              "Rules saved and pushed to the attached services.",
            ),
          );
          validate();
          return;
        }
        panelEl.innerHTML =
          '<div class="alert alert-danger" role="alert">' +
          esc(
            body.message || translate("workflows.err.save", "Could not save"),
          ) +
          "</div>";
        button.disabled = false;
      })
      .catch(function () {
        panelEl.innerHTML =
          '<div class="alert alert-danger" role="alert">' +
          esc(
            translate(
              "workflows.err.saveUnreachable",
              "Could not reach the save endpoint",
            ),
          ) +
          "</div>";
        button.disabled = false;
      });
  }

  // ---- the rule tester ---------------------------------------------------------------

  /* The rule the last test stopped on, so the ladder keeps showing its verdict when the
     pointer leaves. null when no test has run or the answer reached no rule. */
  function pinnedTrace() {
    return STATE.test && typeof STATE.test.ruleIndex === "number"
      ? STATE.test.ruleIndex
      : null;
  }

  function testFacts() {
    var value = function (id) {
      var el = document.getElementById(id);
      return el ? el.value.trim() : "";
    };
    return {
      remote_addr: value("wf-test-ip"),
      uri: value("wf-test-uri") || "/",
      request_method: value("wf-test-method") || "GET",
      geo: value("wf-test-geo") || "resolved",
      country: value("wf-test-country"),
      asn: value("wf-test-asn") === "" ? null : Number(value("wf-test-asn")),
      request_number: Number(value("wf-test-number") || 1),
      whitelisted: !!(document.getElementById("wf-test-whitelisted") || {})
        .checked,
    };
  }

  function runTest() {
    var button = document.getElementById("wf-test-run");
    var out = document.getElementById("wf-test-result");
    if (!out) return;

    /* Refuse a non-numeric ASN here rather than let Number() turn it into NaN: that reaches
       the API as null, which means "the lookup failed" — so a typo would come back as a
       confident UNKNOWN instead of an error. */
    var asn = (document.getElementById("wf-test-asn") || {}).value || "";
    if (asn.trim() !== "" && !/^[0-9]+$/.test(asn.trim())) {
      out.innerHTML =
        '<div class="alert alert-warning" role="alert">' +
        esc(
          translate("workflows.test.asn_invalid", "The ASN must be a number"),
        ) +
        "</div>";
      return;
    }

    if (button) button.disabled = true;
    out.innerHTML =
      '<p class="text-muted small" data-i18n="status.loading">Loading...</p>';
    runTranslations();

    post(document.getElementById("wf-test-url").value, {
      definition: serialize(),
      service_id:
        (document.getElementById("wf-test-service") || {}).value || "",
      request: testFacts(),
    })
      .then(function (body) {
        if (button) button.disabled = false;
        if (body.status !== "success") {
          out.innerHTML =
            '<div class="alert alert-danger" role="alert">' +
            esc(
              body.message ||
                translate("workflows.test.failed", "Could not run the test"),
            ) +
            "</div>";
          return;
        }
        if (body.valid === false) {
          // Same error shape /validate returns, so the ladder paints it with what it has.
          setErrors(body.errors || []);
          paint();
          out.innerHTML =
            '<div class="alert alert-warning" role="alert">' +
            esc(
              translate(
                "workflows.test.invalid",
                "Fix the problems above before testing.",
              ),
            ) +
            "</div>";
          return;
        }
        applyTest(body);
      })
      .catch(function () {
        if (button) button.disabled = false;
        out.innerHTML =
          '<div class="alert alert-danger" role="alert">' +
          esc(
            translate(
              "workflows.test.unreachable",
              "Could not reach the test endpoint",
            ),
          ) +
          "</div>";
      });
  }

  /* The answer lands in two places on purpose: the headline and the assumptions go in the
     drawer, the per-rule verdicts go on the ladder itself — which is where the operator is
     actually looking. */
  function applyTest(body) {
    var mine = null;
    (body.workflows || []).forEach(function (workflow) {
      if (workflow.id === STATE.workflowId) mine = workflow;
    });
    var outcome = body.outcome || {};
    var ruleIndex =
      outcome.type === "match" &&
      mine &&
      outcome.workflow_id === STATE.workflowId
        ? outcome.rule_index
        : null;

    STATE.test = { ruleIndex: ruleIndex, byRule: {}, outcome: outcome };
    (mine ? mine.rules || [] : []).forEach(function (rule) {
      STATE.test.byRule[rule.id] = rule;
    });

    document.getElementById("wf-test-result").innerHTML = testResultHtml(body);
    render();
    paint();
    paintTest();
    runTranslations();
    say(testHeadline(body));
  }

  function testHeadline(body) {
    var outcome = body.outcome || {};
    if (outcome.type === "whitelisted")
      return translate(
        "workflows.test.out_whitelisted",
        "Whitelisted — the whole workflow is skipped and no rule is evaluated.",
      );
    if (outcome.type === "not_attached")
      return translate(
        "workflows.test.out_not_attached",
        "This workflow is attached to no service, so there is no ladder to evaluate.",
      );
    if (outcome.type === "service_draft")
      return translate(
        "workflows.test.out_draft",
        "This service is a draft — no workflow is compiled for it yet.",
      );
    if (outcome.type !== "match")
      return translate(
        "workflows.test.out_no_match",
        "No rule matched. The request continues to the rest of the security stack.",
      );
    return translate(
      "workflows.test.out_match",
      "{{workflow}} · {{rule}} matched and {{action}} the request.",
      {
        workflow: outcome.workflow_name || "",
        rule: outcome.rule_name || outcome.rule_id,
        action: outcome.action ? outcome.action.type : "",
      },
    );
  }

  var ASSUMPTION_TEXT = {
    rate_counter:
      "Request number {{request_number}} is your input, not a measurement.",
    not_whitelisted: "Assumes the client is not whitelisted.",
    regex_budget: "Assumes the instance's regex budget is not exhausted.",
  };

  function testResultHtml(body) {
    var outcome = body.outcome || {};
    var service = body.service;
    var matched = outcome.type === "match";
    var tone = matched ? "alert-primary" : "alert-secondary";

    var detail = "";
    if (matched) {
      if (outcome.terminates === false)
        detail = translate(
          "workflows.test.detail_challenge",
          "The challenge takes over; the rest of the security stack still runs.",
        );
      else
        detail = translate(
          "workflows.test.detail_status",
          "The client sees {{status}}.",
          { status: outcome.effective_status },
        );
      if (outcome.enforced === false)
        detail +=
          " " +
          translate(
            "workflows.test.detail_detect",
            "This service is in detect mode, so nothing is actually enforced.",
          );
    }

    var assumptions = (body.assumptions || [])
      .map(function (item) {
        var fallback = ASSUMPTION_TEXT[item.code];
        if (!fallback) return "";
        return (
          "<li>" +
          esc(
            translate(
              "workflows.test.assume_" + item.code,
              fallback,
              item.detail || {},
            ),
          ) +
          "</li>"
        );
      })
      .join("");

    return (
      '<div class="alert ' +
      tone +
      '" role="alert"><strong>' +
      esc(testHeadline(body)) +
      "</strong>" +
      (detail ? '<div class="small mt-1">' + esc(detail) + "</div>" : "") +
      "</div>" +
      (assumptions
        ? '<p class="wf-test-assume-hd" data-i18n="workflows.test.assumptions">Assumptions</p><ul class="wf-test-assume">' +
          assumptions +
          "</ul>"
        : "") +
      otherWorkflowsHtml(body, service)
    );
  }

  /* The ladder only holds this workflow, so a rule in another one that shadows it would be
     invisible without this. */
  function otherWorkflowsHtml(body, service) {
    var others = (body.workflows || []).filter(function (workflow) {
      return workflow.id !== STATE.workflowId;
    });
    if (!others.length) return "";
    var rows = others
      .map(function (workflow) {
        var matched = workflow.rules.some(function (rule) {
          return rule.state === "match";
        });
        var unreached = workflow.rules.every(function (rule) {
          return rule.state === "unreached" || rule.state === "disabled";
        });
        var note = matched
          ? translate("workflows.test.other_matched", "matched here")
          : unreached
            ? translate("workflows.test.other_unreached", "not reached")
            : translate("workflows.test.other_no_match", "no rule matched");
        return (
          "<li><span>" +
          esc(workflow.name || workflow.id) +
          "</span><span>" +
          esc(note) +
          "</span></li>"
        );
      })
      .join("");
    return (
      '<p class="wf-test-assume-hd" data-i18n="workflows.test.other_workflows">Other workflows on ' +
      esc(service ? service.id : "") +
      '</p><ul class="wf-test-others">' +
      rows +
      "</ul>"
    );
  }

  /* Verdict chips on the ladder, plus the dimming that says "never reached" — reusing the
     vocabulary the hover trace already taught, rather than a second visual language. */
  function paintTest() {
    if (!STATE.test) return;
    trace(pinnedTrace());
    STATE.rules.forEach(function (rule) {
      var verdict = STATE.test.byRule[rule.id];
      if (!verdict) return;
      var card = ladderEl.querySelector(
        '[data-wf-rule="' + CSS.escape(rule.id) + '"]',
      );
      if (!card) return;
      var host = card.querySelector("[data-wf-verdict]");
      if (!host) return;
      host.innerHTML = verdictHtml(verdict);
      var item = card.closest("[data-wf-item]");
      if (item) item.classList.toggle("is-tested", verdict.state === "match");
    });
  }

  function verdictHtml(verdict) {
    if (verdict.state === "match")
      return '<span class="wf-verdict is-match" data-i18n="workflows.test.v_match">MATCHED</span>';
    if (verdict.state === "true_gate_closed") {
      var gate = verdict.gate || {};
      return (
        '<span class="wf-verdict is-gate">' +
        esc(
          translate(
            "workflows.test.v_gate",
            "conditions match · gate closed at {{n}} of {{count}}",
            { n: gate.request_number, count: gate.count },
          ),
        ) +
        "</span>"
      );
    }
    if (verdict.state === "unknown")
      return (
        '<span class="wf-verdict is-unknown" title="' +
        esc(
          translate(
            "workflows.test.v_unknown_help",
            "A fact this rule needs could not be determined, so it can never match.",
          ),
        ) +
        '" data-i18n="workflows.test.v_unknown">UNKNOWN</span>'
      );
    return "";
  }

  function clearTest() {
    STATE.test = null;
    trace(null);
    var out = document.getElementById("wf-test-result");
    if (out) out.innerHTML = "";
    Array.prototype.forEach.call(
      ladderEl.querySelectorAll("[data-wf-verdict]"),
      function (host) {
        host.innerHTML = "";
      },
    );
    Array.prototype.forEach.call(
      ladderEl.querySelectorAll(".is-tested"),
      function (item) {
        item.classList.remove("is-tested");
      },
    );
  }

  // ---- wiring ----------------------------------------------------------------------

  function ruleFromEvent(target) {
    var card = target.closest("[data-wf-rule]");
    return card ? ruleById(card.dataset.wfRule) : null;
  }

  function trace(index) {
    var ladder = ladderEl.querySelector("[data-wf-ladder]");
    if (!ladder) return;
    var items = ladder.querySelectorAll("[data-wf-item]");
    var links = ladder.querySelectorAll("[data-wf-link]");
    if (index === null) {
      ladder.classList.remove("is-tracing");
      Array.prototype.forEach.call(items, function (el) {
        el.classList.remove("is-dead", "is-above");
      });
      Array.prototype.forEach.call(links, function (el) {
        el.classList.remove("is-dead", "is-above");
      });
      return;
    }
    ladder.classList.add("is-tracing");
    Array.prototype.forEach.call(items, function (el) {
      var position = parseInt(el.dataset.wfIndex, 10);
      el.classList.toggle("is-dead", position > index);
      el.classList.toggle("is-above", position < index);
    });
    Array.prototype.forEach.call(links, function (el) {
      var position = parseInt(el.dataset.wfLink, 10);
      el.classList.toggle("is-dead", position > index);
      el.classList.toggle("is-above", position <= index);
    });
  }

  function wireLadder(root) {
    root.addEventListener("click", function (event) {
      var target = event.target;
      var hit = function (selector) {
        return target.closest(selector);
      };

      var jumpButton = hit("[data-wf-jump]");
      if (jumpButton) return jump(jumpButton.dataset.wfJump);

      var toggle = hit("[data-wf-toggleopen]");
      if (toggle) {
        var id = toggle.dataset.wfToggleopen;
        STATE.open.has(id) ? STATE.open.delete(id) : STATE.open.add(id);
        render('[data-wf-toggleopen="' + CSS.escape(id) + '"]');
        paint();
        return;
      }

      var move = hit("[data-wf-move]");
      if (move) {
        var parts = move.dataset.wfMove.split(":");
        var index = STATE.rules.findIndex(function (rule) {
          return rule.id === parts[1];
        });
        return moveRule(parts[1], parts[0] === "up" ? index - 1 : index + 1);
      }

      var position = hit("[data-wf-pos]");
      if (position) return positionMenu(position, position.dataset.wfPos);
      var more = hit("[data-wf-menu]");
      if (more) return ruleMenu(more, more.dataset.wfMenu);
      var op = hit("[data-wf-op]");
      if (op) return opMenu(op, op.dataset.wfOp);
      var addCondition = hit("[data-wf-addpred]");
      if (addCondition)
        return addConditionMenu(addCondition, addCondition.dataset.wfAddpred);

      var addGroup = hit("[data-wf-addgroup]");
      if (addGroup && !addGroup.disabled) {
        var groupHit = locate(addGroup.dataset.wfAddgroup);
        if (groupHit) {
          groupHit.node.nodes.push(
            key({ op: "any", nodes: [newLeaf("country")] }),
          );
          touch();
        }
        return;
      }

      var addGate = hit("[data-wf-addgate]");
      if (addGate) {
        var gated = ruleById(addGate.dataset.wfAddgate);
        if (gated) {
          gated.threshold = { count: 10, window: 60, key: "ip" };
          touch();
          say(
            translate(
              "workflows.say.gateAdded",
              "Rate threshold added to the match. Below it the rule does not match and evaluation continues.",
            ),
          );
        }
        return;
      }

      var removeGate = hit("[data-wf-rmgate]");
      if (removeGate) {
        var ungated = ruleById(removeGate.dataset.wfRmgate);
        if (ungated) {
          ungated.threshold = null;
          touch();
        }
        return;
      }

      var removeNodeButton = hit("[data-wf-rmnode]");
      if (removeNodeButton)
        return removeNode(removeNodeButton.dataset.wfRmnode);

      var removeValue = hit("[data-wf-rmval]");
      if (removeValue) {
        var split = removeValue.dataset.wfRmval.split(":");
        var valueHit = locate(split[0]);
        if (valueHit) {
          valueHit.node.values.splice(parseInt(split[1], 10), 1);
          touch();
          if (!valueHit.node.values.length)
            say(
              translate(
                "workflows.say.lastValueRemoved",
                "Last value removed — this condition cannot be saved until it holds one.",
              ),
            );
        }
        return;
      }

      var moreValues = hit("[data-wf-morevals]");
      if (moreValues) {
        var valueKey = moreValues.dataset.wfMorevals;
        STATE.shown.has(valueKey)
          ? STATE.shown.delete(valueKey)
          : STATE.shown.add(valueKey);
        render();
        paint();
        return;
      }

      var addValue = hit("[data-wf-addval]");
      if (addValue) return inlineValue(addValue, addValue.dataset.wfAddval);

      var action = hit("[data-wf-action]");
      if (action && !action.disabled) {
        var actionRule = ruleFromEvent(action);
        if (!actionRule || actionRule.action.type === action.dataset.wfAction)
          return;
        var type = action.dataset.wfAction;
        /* Remember what was typed for the action being left, and restore whatever was typed
           for the one being picked, so redirect -> challenge -> redirect gives the URL back
           instead of an empty box. Stashed on the RULE, not the action: serialize() spreads
           rule.action onto the wire, and toSchemaRule/fromSchemaRule (which Duplicate goes
           through) copy the action too — either would carry this bookkeeping into the API. */
        actionRule._params = actionRule._params || {};
        actionRule._params[actionRule.action.type] = actionRule.action;
        var kept = actionRule._params[type] || {};
        actionRule.action =
          type === "redirect"
            ? {
                type: "redirect",
                url: kept.url || "",
                status: kept.status || 302,
              }
            : type === "challenge"
              ? { type: "challenge", provider: kept.provider || "javascript" }
              : { type: "block" };
        touch();
        say(
          translate(
            "workflows.say.actionChanged",
            "Action changed to {{type}}. It is still the only action, and it still stops evaluation.",
            { type: type },
          ),
        );
        return;
      }

      // Clicking the head background — not a control — toggles the rule.
      var head = hit(".bw-flow-head");
      if (head && !target.closest("button, input, select, a, .bw-flow-act")) {
        var card = head.closest("[data-wf-rule]");
        if (card) {
          var cardId = card.dataset.wfRule;
          STATE.open.has(cardId)
            ? STATE.open.delete(cardId)
            : STATE.open.add(cardId);
          render();
          paint();
        }
      }
    });

    // Typing never re-renders: the model is updated in place and the API's answer is
    // painted onto the existing DOM, so the caret stays where the operator put it.
    root.addEventListener("input", function (event) {
      var target = event.target;
      var name = target.closest("[data-wf-name]");
      if (name) {
        var named = ruleById(name.dataset.wfName);
        if (named) named.name = name.value;
        return scheduleValidate();
      }
      var uri = target.closest("[data-wf-uri]");
      if (uri) {
        var uriHit = locate(uri.dataset.wfUri);
        if (uriHit) uriHit.node.value = uri.value;
        return scheduleValidate();
      }
      var param = target.closest("[data-wf-param]");
      if (param) {
        var paramRule = ruleFromEvent(param);
        if (paramRule) paramRule.action[param.dataset.wfParam] = param.value;
        return scheduleValidate();
      }
      var gateInput = target.closest("[data-wf-gate]");
      if (gateInput) {
        var gateRule = ruleFromEvent(gateInput);
        if (gateRule && gateRule.threshold) {
          gateRule.threshold[gateInput.dataset.wfGate] = Math.max(
            1,
            parseInt(gateInput.value, 10) || 1,
          );
        }
        scheduleValidate();
      }
    });

    root.addEventListener("change", function (event) {
      var target = event.target;
      if (target.classList.contains("bw-flow-pred-type-select")) {
        var typeHit = locate(target.closest("[data-wf-key]").dataset.wfKey);
        if (typeHit && typeHit.parent) {
          var had = (typeHit.node.values || []).length;
          var kept = carriesValues(typeHit.node, target.value);
          typeHit.parent.nodes[typeHit.index] = convertLeaf(
            typeHit.node,
            target.value,
          );
          touch();
          if (had && !kept)
            say(
              translate(
                "workflows.say.valuesDropped",
                "Condition changed to {{type}} — the {{count}} value(s) it held could not carry over.",
                { type: target.value, count: had },
              ),
            );
        }
        return;
      }
      if (target.classList.contains("bw-flow-pred-op-select")) {
        var host = target.closest("[data-wf-key]");
        var opHit = host ? locate(host.dataset.wfKey) : null;
        if (!opHit) return;
        if (opHit.node.op === "uri") opHit.node.match = target.value;
        else if (opHit.node.op === "group") {
          opHit.node.kind = target.value;
          opHit.node.group_id = firstGroupFor(target.value);
        }
        touch();
        return;
      }
      if (
        target.closest("[data-wf-group]") &&
        target.classList.contains("bw-flow-val-input")
      ) {
        var groupHit = locate(target.closest("[data-wf-key]").dataset.wfKey);
        if (groupHit) {
          groupHit.node.group_id = target.value;
          touch();
        }
        return;
      }
      if (target.classList.contains("wf-act-status-select")) {
        var statusRule = ruleFromEvent(target);
        if (statusRule) {
          if (statusRule.action.type === "block") {
            if (target.value === "") delete statusRule.action.status;
            else statusRule.action.status = parseInt(target.value, 10);
          } else {
            statusRule.action.status = parseInt(target.value, 10);
          }
          touch();
        }
        return;
      }
      if (target.classList.contains("wf-act-provider-select")) {
        var providerRule = ruleFromEvent(target);
        if (providerRule) {
          providerRule.action.provider = target.value;
          touch();
        }
      }
    });

    // Reordering must not depend on a pointer: the arrows, the numbered marker menu and
    // Alt + ↑ / ↓ all reach the same move, and every move is announced.
    root.addEventListener("keydown", function (event) {
      if (
        !event.altKey ||
        (event.key !== "ArrowUp" && event.key !== "ArrowDown")
      )
        return;
      var card = event.target.closest("[data-wf-rule]");
      if (!card || STATE.readonly) return;
      event.preventDefault();
      var id = card.dataset.wfRule;
      var index = STATE.rules.findIndex(function (rule) {
        return rule.id === id;
      });
      moveRule(id, event.key === "ArrowUp" ? index - 1 : index + 1, "keyboard");
    });

    // Hovering a rule dims everything it would shadow — first-match-wins, without a graph.
    // Releasing falls back to the pinned test result rather than clearing, so a verdict on
    // screen survives a stray pointer crossing the ladder.
    root.addEventListener("pointerover", function (event) {
      var item = event.target.closest("[data-wf-item]");
      trace(item ? parseInt(item.dataset.wfIndex, 10) : pinnedTrace());
    });
    root.addEventListener("pointerleave", function () {
      trace(pinnedTrace());
    });
    root.addEventListener("focusin", function (event) {
      var item = event.target.closest("[data-wf-item]");
      if (item) trace(parseInt(item.dataset.wfIndex, 10));
    });
    // Without this the dimming stuck on after tabbing out of the ladder.
    root.addEventListener("focusout", function (event) {
      var next = event.relatedTarget;
      if (!next || !next.closest("[data-wf-item]")) trace(pinnedTrace());
    });

    root.addEventListener("pointerdown", function (event) {
      var grip = event.target.closest("[data-wf-grip]");
      if (!grip) return;
      var item = grip.closest("[data-wf-item]");
      if (item) item.setAttribute("draggable", "true");
    });
    root.addEventListener("dragstart", function (event) {
      var item = event.target.closest("[data-wf-item]");
      if (!item) return;
      dragId = item.dataset.wfItem;
      item.classList.add("is-dragging");
      if (event.dataTransfer) {
        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData("text/plain", dragId);
      }
    });
    root.addEventListener("dragover", function (event) {
      var item = event.target.closest("[data-wf-item]");
      if (!dragId || !item || item.dataset.wfItem === dragId) return;
      event.preventDefault();
      var rect = item.getBoundingClientRect();
      var after = event.clientY > rect.top + rect.height / 2;
      Array.prototype.forEach.call(
        root.querySelectorAll(".is-dropbefore, .is-dropafter"),
        function (el) {
          el.classList.remove("is-dropbefore", "is-dropafter");
        },
      );
      item.classList.add(after ? "is-dropafter" : "is-dropbefore");
    });
    root.addEventListener("drop", function (event) {
      var item = event.target.closest("[data-wf-item]");
      if (!dragId || !item) return;
      event.preventDefault();
      var to = STATE.rules.findIndex(function (rule) {
        return rule.id === item.dataset.wfItem;
      });
      var from = STATE.rules.findIndex(function (rule) {
        return rule.id === dragId;
      });
      var target = item.classList.contains("is-dropafter") ? to + 1 : to;
      if (from < target) target -= 1;
      moveRule(dragId, target, "drag");
      dragId = null;
    });
    root.addEventListener("dragend", function () {
      Array.prototype.forEach.call(
        root.querySelectorAll(".is-dragging, .is-dropbefore, .is-dropafter"),
        function (el) {
          el.classList.remove("is-dragging", "is-dropbefore", "is-dropafter");
        },
      );
      Array.prototype.forEach.call(
        root.querySelectorAll("[data-wf-item][draggable]"),
        function (el) {
          el.removeAttribute("draggable");
        },
      );
      dragId = null;
    });
  }

  /* The menus live on <body>, so their actions are wired on the document rather than on the
     ladder they were opened from. */
  function wireMenus() {
    document.addEventListener("click", function (event) {
      var target = event.target;

      var moveTo = target.closest("[data-wf-moveto]");
      if (moveTo && !moveTo.disabled) {
        var host = moveTo.closest(".bw-flow-menu");
        closeMenus();
        return moveRule(
          host.dataset.rule,
          parseInt(moveTo.dataset.wfMoveto, 10),
        );
      }

      var setOp = target.closest("[data-wf-setop]");
      if (setOp && !setOp.disabled) {
        var opHost = setOp.closest(".bw-flow-menu");
        var opHit = locate(opHost.dataset.node);
        closeMenus();
        if (opHit) {
          opHit.node.op = setOp.dataset.wfSetop;
          touch();
        }
        return;
      }

      var newPred = target.closest("[data-wf-newpred]");
      if (newPred) {
        var predHost = newPred.closest(".bw-flow-menu");
        var predHit = locate(predHost.dataset.node);
        closeMenus();
        if (predHit) {
          if (countLeaves(predHit.rule.condition) >= MAX_PREDICATES_PER_RULE) {
            say(
              translate(
                "workflows.say.predicateCap",
                "This rule already holds {{max}} conditions, the maximum.",
                { max: MAX_PREDICATES_PER_RULE },
              ),
            );
            return;
          }
          predHit.node.nodes.push(newLeaf(newPred.dataset.wfNewpred));
          touch();
        }
        return;
      }

      var ruleAction = target.closest("[data-wf-act]");
      if (ruleAction && !ruleAction.disabled) {
        var actHost = ruleAction.closest(".bw-flow-menu");
        var id = actHost.dataset.rule;
        var index = STATE.rules.findIndex(function (rule) {
          return rule.id === id;
        });
        var rule = STATE.rules[index];
        closeMenus();
        if (!rule) return;
        switch (ruleAction.dataset.wfAct) {
          case "toggle":
            rule.enabled = !rule.enabled;
            touch();
            say(
              rule.enabled
                ? translate(
                    "workflows.say.ruleEnabled",
                    "{{name}} enabled — it is evaluated again at position {{n}}.",
                    { name: ruleLabel(rule), n: index + 1 },
                  )
                : translate(
                    "workflows.say.ruleDisabled",
                    "{{name}} disabled — it is skipped entirely and rules below it now see those requests.",
                    { name: ruleLabel(rule) },
                  ),
            );
            break;
          case "duplicate": {
            if (STATE.rules.length >= MAX_RULES) return;
            var copy = fromSchemaRule(toSchemaRule(rule));
            copy.id = newId();
            copy.name =
              (rule.name || translate("workflows.rule.noun", "Rule")) +
              translate("workflows.copySuffix", " (copy)");
            STATE.rules.splice(index + 1, 0, copy);
            touch();
            say(
              translate(
                "workflows.say.duplicated",
                "Copy inserted at position {{n}}. It can never match while the original above it is enabled.",
                { n: index + 2 },
              ),
            );
            break;
          }
          case "top":
            moveRule(id, 0);
            break;
          case "bottom":
            moveRule(id, STATE.rules.length - 1);
            break;
          case "delete":
            if (
              window.confirm(
                translate(
                  "workflows.confirm.deleteRule",
                  "Delete this rule? Everything below it moves up one position.",
                ),
              )
            ) {
              STATE.rules.splice(index, 1);
              STATE.open.delete(id);
              touch();
              say(
                translate(
                  "workflows.say.deleted",
                  "Rule deleted. {{count}} rules remain.",
                  { count: STATE.rules.length },
                ),
              );
            }
            break;
        }
        return;
      }

      if (
        !target.closest(
          ".bw-flow-menu, [data-wf-pos], [data-wf-menu], [data-wf-op], [data-wf-addpred]",
        )
      )
        closeMenus();
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") closeMenus();
    });
  }

  function toSchemaRule(rule) {
    return {
      id: rule.id,
      name: rule.name,
      enabled: rule.enabled,
      condition: toSchema(rule.condition),
      threshold: rule.threshold,
      action: rule.action,
    };
  }

  function fromSchemaRule(raw) {
    return {
      id: raw.id || newId(),
      name: raw.name || "",
      enabled: raw.enabled !== false,
      condition: fromSchema(raw.condition || { op: "all", nodes: [] }),
      threshold: raw.threshold
        ? {
            count: raw.threshold.count,
            window: raw.threshold.window,
            key: "ip",
          }
        : null,
      action: Object.assign({}, raw.action || { type: "block" }),
    };
  }

  document.addEventListener("DOMContentLoaded", function () {
    ladderEl = document.getElementById("wf-rules");
    emptyEl = document.getElementById("wf-empty");
    panelEl = document.getElementById("wf-validation");
    liveEl = document.getElementById("wf-live");
    capEl = document.getElementById("wf-cap");
    if (!ladderEl) return;

    STATE.open = new Set();
    STATE.shown = new Set();
    STATE.readonly = document.getElementById("wf-readonly").value === "yes";
    try {
      STATE.groups = JSON.parse(
        document.getElementById("wf-groups").value || "{}",
      );
    } catch (error) {
      STATE.groups = {};
    }

    var definition = { rules: [] };
    try {
      definition = JSON.parse(
        document.getElementById("wf-definition").value || "{}",
      );
    } catch (error) {
      definition = { rules: [] };
    }
    STATE.rules = (definition.rules || []).map(fromSchemaRule);
    markSaved();

    /* A ladder is a lot of work to lose to a stray click on the breadcrumb. Readonly pages
       can never be dirty, so they never prompt. */
    window.addEventListener("beforeunload", function (event) {
      if (STATE.readonly || !isDirty()) return;
      event.preventDefault();
      // Browsers show their own wording; a non-empty returnValue is what triggers the prompt.
      event.returnValue = "";
      return "";
    });

    render();
    wireLadder(ladderEl);
    wireMenus();

    var addButton = document.getElementById("wf-add-rule");
    if (addButton) {
      addButton.addEventListener("click", function () {
        if (STATE.rules.length >= MAX_RULES) return;
        var rule = newRule();
        STATE.rules.push(rule);
        STATE.open.add(rule.id);
        touch('[data-wf-rule="' + CSS.escape(rule.id) + '"]');
        say(
          translate(
            "workflows.say.added",
            "Rule added at position {{n}} — last, so every rule above it is checked first.",
            { n: STATE.rules.length },
          ),
        );
      });
    }
    var saveButton = document.getElementById("wf-save");
    if (saveButton) saveButton.addEventListener("click", save);

    var testUrl = document.getElementById("wf-test-url");
    STATE.workflowId = testUrl
      ? (testUrl.value.match(/workflows\/([^/]+)\/test$/) || ["", ""])[1]
      : "";
    var openTest = document.getElementById("wf-test-open");
    var drawer = document.getElementById("wf-tester");
    if (openTest && drawer && window.bootstrap && bootstrap.Offcanvas) {
      openTest.addEventListener("click", function () {
        bootstrap.Offcanvas.getOrCreateInstance(drawer).show();
      });
    }
    var runButton = document.getElementById("wf-test-run");
    if (runButton) {
      runButton.addEventListener("click", function (event) {
        event.preventDefault();
        runTest();
      });
    }
    var geoSelect = document.getElementById("wf-test-geo");
    if (geoSelect) {
      var syncGeo = function () {
        var fields = document.getElementById("wf-test-geo-fields");
        // country/asn are only meaningful when the lookup resolved; local and unavailable
        // both derive their facts, so showing the inputs would invite a contradiction.
        if (fields)
          fields.classList.toggle("d-none", geoSelect.value !== "resolved");
      };
      geoSelect.addEventListener("change", syncGeo);
      syncGeo();
    }

    /* This file is deferred, so it can render before i18next has fetched its catalogue, and
       a later language change does not rebuild the ladder on its own. Both events therefore
       have to repaint, or the editor stays in whatever language it first drew. */
    if (window.i18next && typeof i18next.on === "function") {
      var refresh = function () {
        render();
        paint();
      };
      i18next.on("initialized", refresh);
      i18next.on("languageChanged", refresh);
    }

    if (STATE.rules.length) validate();
  });
})();
