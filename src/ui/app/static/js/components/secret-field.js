/**
 * Wires components/secret-field.html's masked-value reveal toggle + copy button.
 * Delegated on document + idempotent -- include once; works for markup rendered later too
 * (modals, AJAX-loaded panels). Deliberately shares the `.secret-field` / `.secret-toggle` /
 * `data-secret` contract with the older, page-specific handler in
 * static/js/pages/plugin_page.js so the two never fight over the same element -- this one
 * additionally wires the copy button and a translated aria-label swap on toggle, which that
 * older handler does neither.
 *
 * Copy always reads the verbatim value from `data-secret` -- never the visible (possibly
 * masked) text, and never jQuery `.data()`, which caches the first read and coerces
 * numeric-looking values, silently corrupting tokens that happen to look like numbers.
 */
(function () {
  "use strict";
  if (window.__bwSecretFieldInit) return;
  window.__bwSecretFieldInit = true;

  function t(key, fallback) {
    return typeof i18next !== "undefined" ? i18next.t(key, fallback) : fallback;
  }

  // Both buttons point at the field via data-secret-toggle/data-secret-copy="{id}" --
  // id is a required macro param, so a plain getElementById lookup is enough.
  function fieldFor(btn) {
    const id =
      btn.getAttribute("data-secret-toggle") ||
      btn.getAttribute("data-secret-copy");
    return id ? document.getElementById(id) : null;
  }

  function maskFor(field) {
    const n = parseInt(field.getAttribute("data-mask-count"), 10);
    return "•".repeat(n > 0 ? n : 16);
  }

  function setShown(field, toggle, shown) {
    field.textContent = shown
      ? field.getAttribute("data-secret")
      : maskFor(field);
    field.setAttribute("data-secret-shown", shown ? "1" : "0");
    if (shown) {
      field.removeAttribute("aria-label");
    } else {
      const name = field.getAttribute("data-secret-label") || "Secret value";
      field.setAttribute("aria-label", name + " (hidden)");
    }

    const key = shown ? "aria.label.hide_value" : "aria.label.reveal_value";
    const fallback = shown ? "Hide value" : "Reveal value";
    toggle.setAttribute("aria-pressed", String(shown));
    toggle.setAttribute("aria-label", t(key, fallback));
    toggle.setAttribute("data-i18n", key); // keeps i18next's own re-scan (language switch) correct
    const icon = toggle.querySelector("i");
    if (icon)
      icon.className = "bx " + (shown ? "bx-hide" : "bx-show") + " bx-xs";
  }

  function flashCopied(btn) {
    const icon = btn.querySelector("i");
    const prevClass = icon ? icon.className : null;
    if (icon) icon.className = "bx bx-check bx-xs";
    setTimeout(function () {
      if (icon && prevClass) icon.className = prevClass;
    }, 1400);
  }

  function copySecret(secret, btn) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard
        .writeText(secret)
        .then(function () {
          flashCopied(btn);
        })
        .catch(function () {});
      return;
    }
    // Legacy fallback for non-secure contexts / older browsers without Clipboard API.
    const ta = document.createElement("textarea");
    ta.value = secret;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    try {
      document.execCommand("copy");
      flashCopied(btn);
    } catch (err) {
      /* clipboard truly unavailable -- nothing else to do */
    }
    document.body.removeChild(ta);
  }

  document.addEventListener("click", function (e) {
    const toggle = e.target.closest && e.target.closest(".secret-toggle");
    if (toggle) {
      const field = fieldFor(toggle);
      if (field)
        setShown(
          field,
          toggle,
          field.getAttribute("data-secret-shown") !== "1",
        );
      return;
    }

    const copy = e.target.closest && e.target.closest(".secret-copy");
    if (copy) {
      const field = fieldFor(copy);
      const secret = field ? field.getAttribute("data-secret") : null;
      if (secret != null) copySecret(secret, copy);
    }
  });
})();
