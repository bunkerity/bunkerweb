// Passkey enrollment on the profile Security tab. Kept out of pages/profile.js
// (jQuery, ~400 lines of account/password logic) since this is self-contained
// vanilla JS driving the WebAuthn registration ceremony.
(function () {
  "use strict";

  function init() {
    const button = document.getElementById("passkey-register");
    if (!button) return;

    const form = document.getElementById("passkey-register-form");
    const status = document.getElementById("passkey-register-status");
    const unsupported = document.getElementById("passkey-unsupported");
    const nameField = document.getElementById("passkey-name");
    const passwordField = document.getElementById("passkey-password");

    if (!window.BWWebAuthn || !window.BWWebAuthn.supported()) {
      if (form) form.remove();
      if (unsupported) unsupported.classList.remove("d-none");
      return;
    }
    if (form) form.classList.remove("d-none");

    function setStatus(message, isError) {
      if (!status) return;
      status.textContent = message || "";
      status.classList.toggle("text-danger", !!isError);
    }

    button.addEventListener("click", async function () {
      const password = passwordField ? passwordField.value : "";
      if (!password) {
        setStatus(
          t(
            "validation.current_password_required_for_passkey",
            "Enter your current password to add a passkey.",
          ),
          true,
        );
        return;
      }

      button.disabled = true;
      setStatus("");

      // Relative to the current path so a reverse-proxy prefix is preserved.
      const base = window.location.pathname.replace(/\/$/, "");
      try {
        const options = await window.BWWebAuthn.postJSONOrThrow(
          `${base}/webauthn/register/options`,
          { password: password },
        );
        const credential = await window.BWWebAuthn.create(options);

        const result = await window.BWWebAuthn.postJSONOrThrow(
          `${base}/webauthn/register/verify`,
          {
            credential: credential,
            name: nameField ? nameField.value : "",
          },
        );
        window.location.href = result.redirect;
      } catch (error) {
        button.disabled = false;
        if (window.BWWebAuthn.isCancellation(error)) return;
        setStatus(
          error.message ||
            t(
              "error.passkey_registration_failed",
              "Couldn't register this passkey. Please try again.",
            ),
          true,
        );
      } finally {
        if (passwordField) passwordField.value = "";
      }
    });
  }

  if (document.readyState !== "loading") init();
  else document.addEventListener("DOMContentLoaded", init);
})();
