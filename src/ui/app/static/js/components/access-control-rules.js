// Behaviour for the composite-rule section of the three list settings bodies
// (templates/plugin_bodies/access_control/rules.html, included by blacklist/whitelist/greylist).
//
// ONE FILE, THREE BODIES, AND THAT IS WHY IT IS HERE. `plugin_settings_body_script` resolves
// `static/js/plugin_bodies/<plugin_id>.js` (app/utils.py:358), a strict one-to-one pairing with a
// body of the same name -- a section three bodies share has no such twin, so it sits with the
// other shared widget scripts instead and the PARTIAL pulls it in. It is emitted only where that
// partial is included, so it loads on those three pages and nowhere else, once per page. Nothing
// here keys off a plugin name: every selector is `[data-ac-rule*]`, emitted only by that partial,
// so this cannot double-fire through components/settings-widgets.js or reach another page.
//
// LOADED FROM THE CONTENT BLOCK, WITH `defer`. That puts it BEFORE settings-widgets.js in
// execution order (deferred scripts run in document order), so:
//   * nothing here may read anything that file defines;
//   * the delegated `.add-multiple` / `.remove-multiple` handler below runs BEFORE the cloner's,
//     hence the `setTimeout(..., 0)` -- it re-reads the DOM once the click has finished bubbling
//     and the clone is in place.
// `defer` is also what makes jQuery and the message catalog available: both are plain <script>
// tags further down base.html, and a non-deferred script here would run before either.
//
// ================== THE VALUE IS THE INPUT, THE CHIPS ARE CHROME ==================
// One stored key is one form field. The named input carries the whole expression; every control
// in a term row is nameless and only ever rewrites that input, the same division
// components/settings-widgets.js' multivalue widget uses. So this file can be absent and the
// page still SAVES correctly -- each input posts its stored value and the save is a no-op. What
// is lost is only the ability to edit.
//
// NEVER clear or disable an input to hide something: `postable_scope` claims every rule key and
// an in-scope key the POST does not carry has its row DELETED
// (db_methods/config_save.py:579-585). Removing a RULE is the one deliberate deletion, and it
// goes through the shared `.remove-multiple` handler, which takes the whole group out of the DOM
// so the family posts without that suffix.
(() => {
  const form = document.querySelector("form[data-plugin-settings-form]");
  if (!form) return;
  const section = form.querySelector("[data-ac-rules]");
  if (!section) return;
  const rowTemplate = section.querySelector("[data-ac-rule-term-template]");
  if (!rowTemplate) return;

  // THE GRAMMAR IS READ, NOT RESTATED. The separator, the negation prefix, the alias table and the
  // kind list all come off the markup the partial rendered -- the kinds straight out of the term
  // template's own <select>, option for option. A second copy here would be a second thing to keep
  // in step with the engine, and the day they disagreed this file would quietly stop drawing terms
  // the server happily stores.
  const SEPARATOR = section.dataset.acRuleSeparator;
  const NEGATION = section.dataset.acRuleNegation;
  const ALIASES = JSON.parse(section.dataset.acRuleAliases || "{}");
  const KINDS = Array.from(
    rowTemplate.content.querySelector("[data-ac-rule-kind]").options,
  ).map((option) => option.value);

  const rules = () => Array.from(section.querySelectorAll("[data-ac-rule]"));
  const rows = (rule) =>
    Array.from(rule.querySelectorAll("[data-ac-rule-term]"));
  const valueInput = (rule) => rule.querySelector(".ac-rule-value");

  // The ONE thing a value may not contain is the separator itself: the manifest regex forbids
  // " AND" followed by a space or the end of the value, case-insensitively. Everything else is
  // legal, spaces included -- a `ua:` value is a pattern, not a token. So nothing is stripped or
  // rewritten here; the field is MARKED, the term still goes into the expression, and the
  // server's own regex refuses the save. Rewriting the value would be a client-side rule the
  // server does not have, which is exactly how the two drift apart.
  const SEPARATOR_IN_VALUE = / and( |$)/i;

  // Trimmed, because the round trip cannot preserve edge whitespace anyway: the expression is
  // split on " AND " and each piece re-trimmed, so a stored " x " comes back as "x".
  const clean = (value) => value.trim();

  const markValue = (row, value) =>
    row
      .querySelector("[data-ac-rule-term-value]")
      .classList.toggle("is-invalid", SEPARATOR_IN_VALUE.test(value));

  const parse = (expression) =>
    (expression || "")
      .split(SEPARATOR)
      .map((piece) => piece.trim())
      .filter(Boolean)
      .map((piece) => {
        const negated = piece.startsWith(NEGATION);
        const rest = negated ? piece.slice(NEGATION.length).trim() : piece;
        const colon = rest.indexOf(":");
        if (colon < 0) return null;
        // FIRST colon only: an IPv6 term is `ip:2001:db8::/32`.
        const raw = rest.slice(0, colon).toLowerCase();
        const kind = ALIASES[raw] || raw;
        if (!KINDS.includes(kind)) return null;
        return { not: negated, kind, value: rest.slice(colon + 1) };
      })
      .filter(Boolean);

  // The pure half of serialisation: terms in, expression out. Split from the DOM walk below so the
  // grammar can be exercised without a browser -- `format(parse(x))` is the round trip, and
  // `.cache/results-2026-08-31-wave9/L2-rules-render-check.py` runs it in node over the same table
  // the server-rendered chips are checked against.
  const format = (terms) =>
    terms
      // An empty term is not an error, it is a term the operator has not filled in yet: it drops
      // out of the expression and the preview shows exactly what a save would store. A value the
      // grammar refuses is NOT dropped -- marked and kept, so the server answers for it.
      .filter((term) => term.value && KINDS.includes(term.kind))
      .map((term) => `${term.not ? NEGATION : ""}${term.kind}:${term.value}`)
      .join(SEPARATOR);

  const serialize = (rule) =>
    format(
      rows(rule).map((row) => {
        const value = clean(
          row.querySelector("[data-ac-rule-term-value]").value,
        );
        markValue(row, value);
        return {
          not:
            row
              .querySelector("[data-ac-rule-not]")
              .getAttribute("aria-pressed") === "true",
          kind: row.querySelector("[data-ac-rule-kind]").value,
          value,
        };
      }),
    );

  // Only the options matching this term's kind may be picked -- `@office` holds IPs, so offering
  // it on a `country:` term would insert a token the resolver drops. `hidden` alone is advisory on
  // a <select> in some engines; `disabled` is what actually makes it unpickable.
  const filterGroups = (row) => {
    const picker = row.querySelector("[data-ac-rule-group]");
    if (!picker) return;
    const kind = row.querySelector("[data-ac-rule-kind]").value;
    let available = 0;
    Array.from(picker.options).forEach((option) => {
      const optionKind = option.getAttribute("data-ac-rule-group-kind");
      if (!optionKind) return;
      const matches = optionKind === kind;
      option.hidden = !matches;
      option.disabled = !matches;
      if (matches) available += 1;
    });
    picker.hidden = available === 0;
  };

  const sync = (rule) => {
    const input = valueInput(rule);
    if (!input) return;
    const expression = serialize(rule);
    if (input.value !== expression) {
      input.value = expression;
      // `change`, not `input`: the shared widgets listen for `change` on `.plugin-setting`, and a
      // hidden input never fires `input` on a programmatic write anyway.
      input.dispatchEvent(new Event("change", { bubbles: true }));
    }
    const preview = rule.querySelector("[data-ac-rule-preview]");
    if (preview) preview.textContent = expression;
  };

  const addRow = (rule, term) => {
    const row = rowTemplate.content.firstElementChild.cloneNode(true);
    if (term) {
      row.querySelector("[data-ac-rule-kind]").value = term.kind;
      row.querySelector("[data-ac-rule-term-value]").value = term.value;
      const not = row.querySelector("[data-ac-rule-not]");
      not.setAttribute("aria-pressed", term.not ? "true" : "false");
      not.classList.toggle("active", term.not);
    }
    rule.querySelector("[data-ac-rule-terms]").appendChild(row);
    filterGroups(row);
    return row;
  };

  // Rebuild a rule's chips from its own input. Two callers: page load, so the DOM and the parser
  // can never disagree about what the stored expression means; and straight after a clone, where
  // the cloner has copied the SOURCE rule's rows and blanked their values -- the same problem
  // `rebuildMultivalueRows` solves for the multivalue widget.
  //
  // A disabled rule is skipped on purpose: the <template> row is rendered enabled (it is one
  // blank row, not one per rule), so rebuilding a rule whose method is not UI-editable would hand
  // the operator controls the server will not honour.
  const rebuild = (rule) => {
    const input = valueInput(rule);
    if (!input || input.disabled) return;
    const terms = parse(input.value);
    rule.querySelector("[data-ac-rule-terms]").replaceChildren();
    terms.forEach((term) => addRow(rule, term));
    // Always somewhere to type the next term, the trailing-slot rule the multivalue widget uses.
    if (!terms.length) addRow(rule, null);
    // PREVIEW-ONLY: do not call sync() here. sync() writes format(parse(input.value)) back into
    // the input, which normalises aliases and trims edge whitespace -- rebuild() runs at page
    // load and after a clone, so that write would rewrite a stored rule the operator never
    // touched. Show the raw stored string; sync() still fires on every real user gesture below.
    const preview = rule.querySelector("[data-ac-rule-preview]");
    if (preview) preview.textContent = input.value;
  };

  const ruleOf = (element) => element.closest("[data-ac-rule]");

  section.addEventListener("click", (event) => {
    const negate = event.target.closest("[data-ac-rule-not]");
    if (negate && !negate.disabled) {
      const pressed = negate.getAttribute("aria-pressed") === "true";
      negate.setAttribute("aria-pressed", pressed ? "false" : "true");
      negate.classList.toggle("active", !pressed);
      sync(ruleOf(negate));
      return;
    }

    const remove = event.target.closest("[data-ac-rule-term-remove]");
    if (remove && !remove.disabled) {
      const rule = ruleOf(remove);
      remove.closest("[data-ac-rule-term]").remove();
      if (!rows(rule).length) addRow(rule, null);
      sync(rule);
      return;
    }

    const add = event.target.closest("[data-ac-rule-add-term]");
    if (add) {
      const rule = ruleOf(add);
      addRow(rule, null).querySelector("[data-ac-rule-term-value]").focus();
      sync(rule);
    }
  });

  section.addEventListener("input", (event) => {
    const field = event.target.closest("[data-ac-rule-term-value]");
    if (field) sync(ruleOf(field));
  });

  section.addEventListener("change", (event) => {
    const kind = event.target.closest("[data-ac-rule-kind]");
    if (kind) {
      const row = kind.closest("[data-ac-rule-term]");
      // A group token carries no kind of its own, so one that no longer matches is now wrong.
      const field = row.querySelector("[data-ac-rule-term-value]");
      if (field.value.startsWith("@")) field.value = "";
      filterGroups(row);
      sync(ruleOf(kind));
      return;
    }

    const picker = event.target.closest("[data-ac-rule-group]");
    if (picker && picker.value) {
      const row = picker.closest("[data-ac-rule-term]");
      row.querySelector("[data-ac-rule-term-value]").value = picker.value;
      picker.value = "";
      sync(ruleOf(picker));
    }
  });

  // The cloner in components/settings-widgets.js owns add/remove RULE. Its handler is bound after
  // this one (see the header), so the work is deferred by a turn: by then the clone -- or the
  // removal -- has landed and every rule can be re-read from its own input.
  document.addEventListener("click", (event) => {
    if (!event.target.closest(".add-multiple, .remove-multiple")) return;
    setTimeout(() => rules().forEach(rebuild), 0);
  });

  const start = () => rules().forEach(rebuild);
  start();
  // A bfcache restore hands back the inputs' current values without firing anything.
  window.addEventListener("pageshow", start);
})();
