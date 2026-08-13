// TOTP verification page — single one-time-code input (styled as 6 boxes via
// CSS) + recovery-code toggle. One real field named totp_token, so 1Password /
// Bitwarden / SMS one-time-code autofill and clipboard paste all work natively.
// Auto-submits once 6 digits are present; recovery mode swaps the field for a
// free-text recovery-code input (also named totp_token — the server tries TOTP
// then recovery on the same token).
(function () {
  // Security key as an alternative to the code. Wired independently of the TOTP
  // inputs below, which are absent entirely for a user whose only second factor
  // is a security key.
  function initSecurityKey() {
    const button = document.getElementById("security-key-verify");
    if (!button) return;

    const wrapper = document.getElementById("security-key-block");
    const status = document.getElementById("security-key-status");

    if (!window.BWWebAuthn || !window.BWWebAuthn.supported()) {
      if (wrapper) wrapper.remove();
      return;
    }
    if (wrapper) wrapper.classList.remove("d-none");

    button.addEventListener("click", async function () {
      button.disabled = true;
      if (status) {
        status.textContent = "";
        status.classList.remove("err");
      }

      const base = window.location.pathname.replace(/\/$/, "");
      try {
        const options = await window.BWWebAuthn.postJSONOrThrow(
          `${base}/webauthn/options`,
          {},
        );
        const assertion = await window.BWWebAuthn.get(options);
        const result = await window.BWWebAuthn.postJSONOrThrow(
          `${base}/webauthn/verify`,
          assertion,
        );
        window.location.href = result.redirect;
      } catch (error) {
        button.disabled = false;
        if (window.BWWebAuthn.isCancellation(error)) return;
        if (status) {
          status.textContent =
            error.message ||
            "Couldn't verify your security key, please try again";
          status.classList.add("err"); // .sw-key-status.err, see css/pages/login.css
        }
      }
    });
  }

  function init() {
    initSecurityKey();

    const form = document.getElementById("totp-form");
    const wrap = document.getElementById("totpInputs");
    const verify = document.getElementById("totpVerify");
    const status = document.getElementById("totpStatus");
    const recovery = document.getElementById("totpRecovery");
    if (!form || !wrap || !verify || !recovery) return;

    const codeHTML = wrap.innerHTML; // cache the boxed-input markup for restore
    let recoveryMode = false;

    const field = () => wrap.querySelector(".totp-code, .totp-recovery-input");

    function refresh() {
      status.className = "sw-key-status";
      status.textContent = "";
      wrap.classList.remove("err");
      const f = field();
      if (!f) return;
      const v = f.value.trim();
      verify.disabled = recoveryMode ? v.length < 10 : !/^\d{6}$/.test(v);
    }

    function submitIfValid() {
      if (verify.disabled) return;
      form.submit(); // native submit — bypasses the submit handler below
    }

    function bind() {
      const f = field();
      if (!f) return;
      if (recoveryMode) {
        f.addEventListener("input", refresh);
      } else {
        f.addEventListener("input", () => {
          // Keep digits only; covers manual typing, paste, and manager autofill.
          const cleaned = f.value.replace(/\D/g, "").slice(0, 6);
          if (cleaned !== f.value) f.value = cleaned;
          refresh();
          if (/^\d{6}$/.test(f.value)) submitIfValid(); // auto-submit when full
        });
      }
      f.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          submitIfValid();
        }
      });
      f.focus();
    }

    function toggleRecovery() {
      recoveryMode = !recoveryMode;
      if (recoveryMode) {
        wrap.innerHTML =
          '<input class="sw-input totp-recovery-input" type="text" name="totp_token" id="totp_token" placeholder="XXXXX-XXXXX-XXXXX" autocomplete="off" spellcheck="false" aria-label="Recovery code" required />';
        recovery.textContent = "Use an authenticator code";
        recovery.setAttribute("data-i18n", "link.use_authenticator_code");
      } else {
        wrap.innerHTML = codeHTML;
        recovery.textContent = "Use a recovery code";
        recovery.setAttribute("data-i18n", "link.use_recovery_code");
      }
      bind();
      refresh();
    }

    verify.addEventListener("click", submitIfValid);
    recovery.addEventListener("click", toggleRecovery);
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      submitIfValid();
    });

    bind();
    refresh();
  }

  if (document.readyState !== "loading") init();
  else document.addEventListener("DOMContentLoaded", init);
})();
