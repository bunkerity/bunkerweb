/**
 * setButtonLoading(button, isLoading) -- toggle a <button> into/out of a
 * disabled + spinner "in flight" state at runtime.
 *
 * Generalizes the hand-rolled pattern already duplicated per-page for async
 * submit/save buttons (see static/js/pages/template_edit.js's setSaving(),
 * which stashes .innerHTML on a dataset field, swaps in a
 * ".spinner-border.spinner-border-sm", and restores it after) into one
 * reusable helper. Works on ANY <button> -- one rendered by
 * components/button.html, or a plain hand-rolled one -- not tied to any
 * particular macro's markup.
 *
 * Idempotent: calling setButtonLoading(btn, true) while already loading, or
 * setButtonLoading(btn, false) while not loading, is a no-op -- the original
 * content is stashed exactly once via `data-loading`/`data-orig-html`, never
 * clobbered by a second call, and never reads back a spinner-swapped
 * .innerHTML as if it were the "original" content.
 *
 * Existing per-page hand-rolled equivalents (template_edit.js's setSaving(),
 * reports.js's inline "Loading report details..." markup) are left as-is --
 * consolidating them onto this helper is separate follow-up work, not done
 * here. This file only makes the helper available.
 */
(function () {
  "use strict";
  if (window.setButtonLoading) return;

  function setButtonLoading(button, isLoading) {
    if (!button) return button;

    const loading = button.getAttribute("data-loading") === "1";
    if (isLoading === loading) return button; // already in that state -- no-op

    if (isLoading) {
      button.setAttribute("data-loading", "1");
      button.setAttribute("data-orig-html", button.innerHTML);
      // Lock the current width so swapping in the spinner doesn't reflow
      // the button (and, in turn, anything laid out next to it).
      const width = button.offsetWidth;
      if (width) button.style.minWidth = width + "px";
      button.disabled = true;
      button.setAttribute("aria-busy", "true");
      button.innerHTML =
        '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>' +
        button.getAttribute("data-orig-html");
    } else {
      const original = button.getAttribute("data-orig-html");
      if (original !== null) button.innerHTML = original;
      button.removeAttribute("data-loading");
      button.removeAttribute("data-orig-html");
      button.style.minWidth = "";
      button.disabled = false;
      button.removeAttribute("aria-busy");
    }
    return button;
  }

  window.setButtonLoading = setButtonLoading;
})();
