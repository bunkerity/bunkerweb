/**
 * Copy-to-clipboard wiring for components/copy-button.html.
 *
 * Delegated on document -- same idiom as components/recovery-code.js -- so
 * every `.js-copy-button` on the page works, including markup injected later
 * (modals, AJAX rows). Deliberately a distinct trigger class from the legacy
 * `.copy-to-clipboard` handler in main.js (static/non-delegated, assumes the
 * value always lives in a sibling `.input-group input`) so the two never
 * double-fire on the same element.
 *
 * What gets copied, resolved in this order:
 *   1. data-copy-text="…"   -- a literal string (wins if present, even "");
 *   2. data-copy-target="…" -- a CSS selector or a bare element id; reads
 *      that element's .value (inputs/textareas) or .textContent otherwise.
 *
 * Feedback matches the existing convention already used by main.js /
 * plugins-settings.js / components/recovery-code.js: swap
 * data-bs-original-title and call .tooltip("show"), restore after 2s.
 * data-copied-i18n (an i18next key) is preferred when i18next is loaded;
 * otherwise falls back to the trigger's own data-copied-label.
 */
(function () {
  function resolveText(trigger) {
    const literal = trigger.getAttribute("data-copy-text");
    if (literal !== null) {
      return literal;
    }

    const targetSel = trigger.getAttribute("data-copy-target");
    if (!targetSel) {
      return null;
    }

    let el = null;
    try {
      el = document.querySelector(targetSel);
    } catch (e) {
      // not a valid CSS selector -- fall through to a bare-id lookup
    }
    if (!el) {
      el = document.getElementById(targetSel);
    }
    if (!el) {
      return null;
    }

    return el.value !== undefined && el.value !== ""
      ? el.value
      : el.textContent;
  }

  function copiedLabel(trigger) {
    const key = trigger.getAttribute("data-copied-i18n");
    if (key && typeof i18next !== "undefined") {
      return i18next.t(key);
    }
    return trigger.getAttribute("data-copied-label") || "Copied!";
  }

  function run(trigger) {
    if (
      !trigger ||
      trigger.disabled ||
      trigger.getAttribute("aria-disabled") === "true"
    ) {
      return;
    }

    const text = resolveText(trigger);
    if (text === null) {
      return;
    }

    const $trigger = $(trigger);
    navigator.clipboard
      .writeText(text)
      .then(() => {
        $trigger
          .attr("data-bs-original-title", copiedLabel(trigger))
          .tooltip("show");
        setTimeout(() => {
          $trigger.tooltip("hide").attr("data-bs-original-title", "");
        }, 2000);
      })
      .catch((err) => {
        console.error("Failed to copy text: ", err);
      });
  }

  $(document).on("click", ".js-copy-button", function () {
    run(this);
  });

  // variant="addon" renders a <span role="button">, not a real <button> --
  // give it the same keyboard activation a native button gets for free.
  $(document).on("keydown", ".js-copy-button[role='button']", function (e) {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      run(this);
    }
  });
})();
