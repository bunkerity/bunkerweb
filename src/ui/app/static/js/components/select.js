/**
 * Wires components/select.html's custom combobox: picking an option syncs the hidden
 * `[data-select-value]` input (firing a real `change` event so existing `$(...).on('change',
 * ...)` page code keeps working) and the trigger's visible label/icon, and the optional
 * in-menu search box filters the option list live.
 *
 * Open/close, outside-click dismissal, Popper positioning and ArrowUp/ArrowDown/Escape
 * keyboard nav across `.dropdown-item` options are all Bootstrap's own dropdown plugin
 * (data-bs-toggle="dropdown", already vendored and loaded on every page) -- see
 * components/select.html's doc comment for why. This file only adds the parts that plugin
 * doesn't do for a value-picking widget: syncing the hidden field, and the search filter.
 *
 * Delegated on document + idempotent -- include once; works for markup rendered later too
 * (modals, AJAX-loaded panels), same convention as components/secret-field.js.
 */
(function () {
  "use strict";
  if (window.__bwSelectInit) return;
  window.__bwSelectInit = true;

  function visibleOptions(wrapper) {
    return wrapper.querySelectorAll(
      ".bw-select-list li:not(.d-none) > [data-select-option]",
    );
  }

  function selectOption(opt) {
    if (!opt || opt.disabled) return;
    const wrapper = opt.closest(".bw-select");
    if (!wrapper) return;
    const hiddenInput = wrapper.querySelector("[data-select-value]");
    const trigger = wrapper.querySelector('[data-bs-toggle="dropdown"]');
    if (!hiddenInput || !trigger) return;

    const value = opt.getAttribute("data-value") || "";
    const label = opt.getAttribute("data-label") || "";
    const icon = opt.getAttribute("data-icon");

    if (hiddenInput.value !== value) {
      hiddenInput.value = value;
      hiddenInput.dispatchEvent(new Event("change", { bubbles: true }));
    }

    wrapper.querySelectorAll("[data-select-option]").forEach(function (o) {
      o.classList.remove("active");
      o.setAttribute("aria-selected", "false");
    });
    opt.classList.add("active");
    opt.setAttribute("aria-selected", "true");

    const labelEl = trigger.querySelector("[data-select-trigger-label]");
    if (labelEl) {
      // `data-label` is the option's label already translated by the server, so the trigger has
      // nothing left to resolve. It used to copy the option's `data-i18n` key across and call
      // t() on it -- with the macro translated server-side that key is gone, and the fallback
      // silently showed the English text in every language.
      labelEl.textContent = label;
    }

    const iconEl = trigger.querySelector("[data-select-trigger-icon]");
    if (iconEl) {
      iconEl.className = icon
        ? "bx " + icon + " bw-select-trigger-icon"
        : "bx bw-select-trigger-icon d-none";
    }
  }

  function filterOptions(wrapper, query) {
    const list = wrapper.querySelector(".bw-select-list");
    if (!list) return;
    const q = (query || "").trim().toLowerCase();
    let anyVisible = false;

    list.querySelectorAll("[data-select-option]").forEach(function (opt) {
      const li = opt.closest("li");
      if (!li) return;
      const label = (opt.getAttribute("data-label") || "").toLowerCase();
      const visible = !q || label.indexOf(q) !== -1;
      // d-none (not inline style) to match the existing house convention for filtered
      // rows -- see filterMultiselectOptions() in static/js/components/settings-widgets.js.
      li.classList.toggle("d-none", !visible);
      if (visible) anyVisible = true;
    });

    const noResults = list.querySelector("[data-select-no-results]");
    if (noResults) noResults.classList.toggle("d-none", !(q && !anyVisible));
  }

  document.addEventListener("click", function (e) {
    const opt = e.target.closest && e.target.closest("[data-select-option]");
    if (opt) selectOption(opt);
  });

  document.addEventListener("input", function (e) {
    const input = e.target.closest && e.target.closest(".bw-select-search");
    if (!input) return;
    const wrapper = input.closest(".bw-select");
    if (wrapper) filterOptions(wrapper, input.value);
  });

  // From the search box, ArrowDown hands keyboard focus off to the first visible option --
  // Bootstrap's own dropdown keydown handler deliberately ignores Up/Down while focus sits
  // in an <input>/<textarea> (so normal text-field key handling still works), so without
  // this the list is only reachable by Tab or a mouse click.
  document.addEventListener("keydown", function (e) {
    if (e.key !== "ArrowDown") return;
    const input = e.target.closest && e.target.closest(".bw-select-search");
    if (!input) return;
    const wrapper = input.closest(".bw-select");
    if (!wrapper) return;
    const first = visibleOptions(wrapper)[0];
    if (first) {
      e.preventDefault();
      first.focus();
    }
  });

  // shown.bs.dropdown / hidden.bs.dropdown are Bootstrap custom events -- Bootstrap
  // dispatches them through jQuery when it's present (it is, everywhere in this app), so
  // they're listened for the same way the rest of the codebase already does (see
  // static/js/pages/config_edit.js's "hidden.bs.dropdown" handler).
  $(document).on("shown.bs.dropdown", ".bw-select", function () {
    const search = this.querySelector(".bw-select-search");
    if (!search) return;
    search.value = "";
    filterOptions(this, "");
    search.focus();
  });
})();
