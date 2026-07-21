/**
 * Copy-all wiring for components/recovery-code.html.
 *
 * Generalizes the inline <script> block that used to live in profile.html's
 * #modal-recovery-codes (hardcoded to #copy-codes-button / .recovery-code).
 * Delegated on document + idempotent, so it works no matter how many
 * recovery-code macro instances are on the page (or injected later, e.g. a
 * modal shown after DOMContentLoaded) -- same pattern as the generic
 * ".copy-to-clipboard" handler in main.js.
 *
 * Include once (nonce script tag) on any page that renders the macro with
 * copyable=true.
 */
$(document).on("click", "[data-recovery-copy-target]", function () {
  const button = $(this);
  const wrapper = document.getElementById(
    button.attr("data-recovery-copy-target"),
  );
  if (!wrapper) {
    return;
  }

  const codes = Array.from(wrapper.querySelectorAll(".recovery-code"))
    .map((el) => el.textContent.trim())
    .join("\n");

  navigator.clipboard
    .writeText(codes)
    .then(() => {
      const copiedLabel =
        typeof i18next !== "undefined"
          ? i18next.t("tooltip.copied")
          : "Copied!";
      button.attr("data-bs-original-title", copiedLabel).tooltip("show");
      setTimeout(() => {
        button.tooltip("hide").attr("data-bs-original-title", "");
      }, 2000);
    })
    .catch((err) => {
      console.error("Failed to copy recovery codes: ", err);
    });
});
