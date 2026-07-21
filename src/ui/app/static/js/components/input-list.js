/**
 * Wires components/input-list.html's "view all N settings" trigger --
 * delegated on document + idempotent (window.__bwInputListInit guard), same
 * idiom as static/js/components/secret-field.js. Works for markup rendered
 * later too (modals, AJAX-loaded panels).
 *
 * On click of any [data-il-open] trigger:
 *   1. reads the settings payload back via `getAttribute('data-il-settings')`
 *      -- NEVER jQuery `.data()`, which caches the first read and coerces
 *      numeric-looking values, silently corrupting settings that happen to
 *      look like numbers (same reasoning secret-field.js documents for its
 *      own `data-secret` reads);
 *   2. builds the Name/Value rows into the modal body components/modal.html
 *      already rendered (pointed at via the trigger's `aria-controls`);
 *   3. opens it with Bootstrap's own `new bootstrap.Modal(...)` JS API --
 *      the same pattern already used in pages/instances.js and
 *      pages/jobs.js's show-history handler -- instead of a hand-rolled
 *      overlay.
 *
 * The trigger always carries the *real* values regardless of the macro's
 * show_values=false compact-table option (see input-list.html's doc
 * comment) -- opening "view all" is a deliberate reveal action.
 */
(function () {
  "use strict";
  if (window.__bwInputListInit) return;
  window.__bwInputListInit = true;

  function t(key, fallback, options) {
    if (typeof i18next === "undefined") return fallback;
    return i18next.t(key, Object.assign({ defaultValue: fallback }, options));
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, function (c) {
      return (
        { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[
          c
        ] || c
      );
    });
  }

  function parseSettings(raw) {
    if (!raw) return [];
    try {
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch (err) {
      return [];
    }
  }

  function rowsHtml(entries) {
    if (!entries.length) {
      return (
        '<tr><td colspan="2" class="text-center text-muted py-3">' +
        escapeHtml(t("status.no_data", "No data")) +
        "</td></tr>"
      );
    }
    return entries
      .map(function (entry) {
        const value =
          entry.value === null ||
          entry.value === undefined ||
          entry.value === ""
            ? '<span class="text-muted" aria-hidden="true">&mdash;</span>'
            : '<code class="courier-prime text-break">' +
              escapeHtml(entry.value) +
              "</code>";
        return (
          '<tr><td><code class="courier-prime">' +
          escapeHtml(entry.key) +
          "</code></td><td>" +
          value +
          "</td></tr>"
        );
      })
      .join("");
  }

  document.addEventListener("click", function (e) {
    const trigger = e.target.closest && e.target.closest("[data-il-open]");
    if (!trigger) return;

    const targetId = trigger.getAttribute("aria-controls");
    const modalEl = targetId ? document.getElementById(targetId) : null;
    if (!modalEl || typeof bootstrap === "undefined") return;

    const entries = parseSettings(trigger.getAttribute("data-il-settings"));

    const body = modalEl.querySelector("[data-il-modal-body]");
    if (body) body.innerHTML = rowsHtml(entries);

    const titleEl = modalEl.querySelector(".modal-title");
    if (titleEl) {
      titleEl.textContent = t(
        "input_list.view_all_settings",
        "View all {{count}} settings",
        { count: entries.length },
      );
    }

    const modal = new bootstrap.Modal(modalEl);
    modal.show();
  });
})();
