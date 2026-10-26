// Plugin settings page chrome (templates/plugin_settings_page.html): the Plugin / Scope selectors
// that move between /global-settings/plugins/<plugin> and /services/<svc>/plugins/<plugin>, the
// in-card search and count, Revert, and the unsaved-edit guard (BWLeaveGuard, W1 module).
//
// Nothing here posts. The selectors live outside the form, the search input has no `name`, and
// the fields are only ever HIDDEN by search (display:none): a hidden field still serialises, and
// an in-scope key the POST omits is deleted by the save.
(() => {
  "use strict";
  const form = document.getElementById("plugin-settings-form");
  if (!form) return;

  const t = window.i18next?.t || ((key, fallback) => fallback || key);
  const GLOBAL = "__global__";
  const nav = document.querySelector("[data-plugin-scope-nav]");
  const revert = document.getElementById("plugin-settings-revert");
  let dirty = false;
  let reverting = false;

  const setDirty = (value) => {
    dirty = value;
    if (revert) revert.disabled = !value;
  };

  // ---------------------------------------------------------------- unsaved-edit guard
  // `input` alone misses checkbox/select/file, `change` alone misses typing: both, capture phase.
  // Armed after load so a widget normalising its own value while it initialises is not an edit.
  const arm = () => {
    const mark = (event) => {
      if (event.target.id === "plugin-settings-search") return;
      setDirty(true);
    };
    form.addEventListener("input", mark, true);
    form.addEventListener("change", mark, true);
    // The per-field reset moves values with jQuery's `.trigger("change")`, which runs jQuery handlers only.
    if (window.jQuery) window.jQuery(form).on("input change", mark);
    form.addEventListener("submit", () => setDirty(false));
  };
  if (document.readyState === "complete") setTimeout(arm, 0);
  else window.addEventListener("load", () => setTimeout(arm, 0));

  const guard = window.BWLeaveGuard?.create({
    isDirty: () => dirty && !reverting,
  });

  // ---------------------------------------------------------------- Plugin / Scope selectors
  if (nav) {
    const urlFor = (plugin, scope) => {
      const base =
        scope === GLOBAL ? nav.dataset.urlGlobal : nav.dataset.urlService;
      return base
        .replace("__SERVICE__", encodeURIComponent(scope))
        .replace("__PLUGIN__", encodeURIComponent(plugin));
    };
    const pluginInput = document.getElementById("plugin-nav-plugin");
    const scopeInput = document.getElementById("plugin-nav-scope");
    const current = {
      plugin: nav.dataset.plugin,
      scope: nav.dataset.scope,
    };
    let restoring = false;

    const restore = (input, value) => {
      const wrapper = input.closest(".bw-select");
      const option = wrapper?.querySelector(
        `[data-select-option][data-value="${CSS.escape(value)}"]`,
      );
      if (!option) return;
      restoring = true;
      option.click();
      restoring = false;
    };

    const onChange = (input, key) => {
      if (!input) return;
      input.addEventListener("change", () => {
        if (restoring || input.value === current[key]) return;
        const target = { ...current, [key]: input.value };
        const go = () =>
          window.location.assign(urlFor(target.plugin, target.scope));
        if (!guard) return go();
        guard.confirmLeave(go).then((left) => {
          if (!left) restore(input, current[key]);
        });
      });
    };
    onChange(pluginInput, "plugin");
    onChange(scopeInput, "scope");

    // Services are listed only when the scope select first opens (one request, cached for the page).
    const trigger = document.getElementById("plugin-nav-scope-trigger");
    const list = document.getElementById("plugin-nav-scope-list");
    let requested = false;
    const addOption = (service) => {
      if (
        list.querySelector(
          `[data-select-option][data-value="${CSS.escape(service)}"]`,
        )
      )
        return;
      const item = document.createElement("li");
      item.setAttribute("role", "presentation");
      const button = document.createElement("button");
      button.type = "button";
      button.className = "dropdown-item d-flex align-items-center gap-2";
      button.setAttribute("role", "option");
      button.setAttribute("data-select-option", "");
      button.setAttribute("data-value", service);
      button.setAttribute("data-label", service);
      button.setAttribute("data-icon", "bx-server");
      button.setAttribute("aria-selected", "false");
      const icon = document.createElement("i");
      icon.className = "bx bx-server";
      icon.setAttribute("aria-hidden", "true");
      const span = document.createElement("span");
      span.className = "flex-grow-1 text-truncate";
      const label = document.createElement("span");
      label.className = "select-option-label";
      label.textContent = service;
      span.appendChild(label);
      button.append(icon, span);
      item.appendChild(button);
      list.insertBefore(item, list.querySelector("[data-select-no-results]"));
    };
    if (trigger && list && nav.dataset.serviceScope === "yes") {
      trigger.addEventListener("click", () => {
        if (requested) return;
        requested = true;
        const root = document.body.getAttribute("data-app-root") || "";
        fetch(nav.dataset.servicesEndpoint || `${root}/search/services`, {
          credentials: "same-origin",
          headers: { "X-Requested-With": "XMLHttpRequest" },
        })
          .then((response) => {
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return response.json();
          })
          .then((data) =>
            (data.services || []).forEach((service) => addOption(service.id)),
          )
          .catch((error) => {
            requested = false;
            console.warn(error);
          });
      });
    }
  }

  // ---------------------------------------------------------------- in-card search and count
  // Counted: the fields the page shows. A plugin body hides the sections that do not apply to the chosen mode
  // (`hidden`); they stay in the form and post, but they are not "settings" on screen.
  const cells = () =>
    Array.from(form.querySelectorAll(".bw-setting-frame"))
      .filter((frame) => !frame.closest("[hidden]"))
      .map((frame) => ({
        frame,
        cell: frame.closest(".col-12") || frame,
      }));
  const countEl = document.getElementById("plugin-settings-count");
  const search = document.getElementById("plugin-settings-search");
  const noMatch = document.getElementById("plugin-settings-nomatch");
  const haystack = (frame) =>
    [
      frame.querySelector("label")?.textContent || "",
      Array.from(frame.querySelectorAll("[name]"))
        .map((field) => field.name)
        .join(" "),
      frame.querySelector(".bw-input-help")?.textContent || "",
    ]
      .join(" ")
      .toLowerCase();

  const render = () => {
    const query = (search?.value || "").trim().toLowerCase();
    const all = cells();
    let shown = 0;
    all.forEach(({ frame, cell }) => {
      const match = !query || haystack(frame).includes(query);
      cell.style.display = match ? "" : "none";
      if (match) shown += 1;
    });
    if (countEl) {
      const template = query
        ? countEl.dataset.countFilteredTemplate
        : countEl.dataset.countTemplate;
      countEl.textContent = (template || "")
        .replace("{{count}}", all.length)
        .replace("{{shown}}", shown)
        .replace("{{total}}", all.length);
    }
    if (noMatch)
      noMatch.classList.toggle(
        "d-none",
        !query || shown > 0 || all.length === 0,
      );
  };
  if (search) search.addEventListener("input", render);
  render();
  // A body hides and shows its sections on a mode change; recount once its own handler has run.
  const recount = () => setTimeout(render, 0);
  form.addEventListener("change", recount);
  if (window.jQuery) window.jQuery(form).on("change", recount);

  // ---------------------------------------------------------------- Revert
  // Reverting means "reload what is saved": the page is rendered from the stored configuration,
  // and per-field reset (the widgets' own button) stays for single fields.
  if (revert) {
    revert.addEventListener("click", async () => {
      if (!dirty || !window.BWConfirm) return;
      const confirmed = await window.BWConfirm.open({
        title:
          revert.dataset.title ||
          t("settings_page.revert_title", "Revert changes"),
        message: t(
          "settings_page.revert_message",
          "This reverts every unsaved edit on this page to its last saved value.",
        ),
        confirmLabel: t("settings_page.revert_confirm", "Revert all"),
        destructive: false,
      });
      if (!confirmed) return;
      reverting = true;
      window.location.assign(window.location.pathname + window.location.search);
    });
  }
})();
