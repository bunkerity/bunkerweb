// Passwordless login. The button asks the authenticator for a discoverable
// credential — no username is sent, so nothing here can be used to probe which
// accounts exist — and posts the assertion back for verification.
(function () {
  "use strict";

  function init() {
    const button = document.getElementById("passkey-login");
    if (!button) return;

    const wrapper = document.getElementById("passkey-block");
    const status = document.getElementById("passkey-status");

    // The server only renders the block when a Relying Party is configured; the
    // browser still has to actually support the API.
    if (!window.BWWebAuthn || !window.BWWebAuthn.supported()) {
      if (wrapper) wrapper.remove();
      return;
    }
    if (wrapper) wrapper.classList.remove("d-none");

    function setStatus(message, isError) {
      if (!status) return;
      status.textContent = message || "";
      status.classList.toggle("err", !!isError); // .sw-key-status.err, see css/pages/login.css
    }

    button.addEventListener("click", async function () {
      button.disabled = true;
      setStatus("");

      try {
        // Relative to the current path so a reverse-proxy prefix is preserved.
        const base = window.location.pathname.replace(/\/$/, "");
        const options = await window.BWWebAuthn.postJSONOrThrow(
          `${base}/webauthn/options`,
          {},
        );
        const assertion = await window.BWWebAuthn.get(options);

        const nextField = document.querySelector("input[name='next']");
        const rememberField = document.getElementById("remember-me");
        assertion.next = nextField ? nextField.value : "";
        assertion.remember_me = !!(rememberField && rememberField.checked);

        const result = await window.BWWebAuthn.postJSONOrThrow(
          `${base}/webauthn/verify`,
          assertion,
        );
        window.location.href = result.redirect;
      } catch (error) {
        button.disabled = false;
        if (window.BWWebAuthn.isCancellation(error)) return;
        setStatus(
          error.message ||
            t(
              "error.passkey_sign_in_failed",
              "Couldn't sign you in with a passkey. Please try again.",
            ),
          true,
        );
      }
    });
  }

  if (document.readyState !== "loading") init();
  else document.addEventListener("DOMContentLoaded", init);
})();
