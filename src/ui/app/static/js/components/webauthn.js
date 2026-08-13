// Shared WebAuthn browser glue: base64url <-> ArrayBuffer conversion, the two
// navigator.credentials ceremonies, and the fetch wrapper the three auth pages
// (login, totp, profile) use. Exposed as window.BWWebAuthn.
//
// The browser API speaks ArrayBuffers while the server speaks base64url JSON, so
// every ceremony is a decode -> call -> encode round trip. Nothing secret passes
// through here: the private key stays inside the authenticator.
(function () {
  "use strict";

  function b64urlToBuf(value) {
    const padded = value.replace(/-/g, "+").replace(/_/g, "/");
    const raw = atob(padded + "=".repeat((4 - (padded.length % 4)) % 4));
    const buf = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) buf[i] = raw.charCodeAt(i);
    return buf.buffer;
  }

  function bufToB64url(buf) {
    const bytes = new Uint8Array(buf);
    let raw = "";
    for (let i = 0; i < bytes.length; i++) raw += String.fromCharCode(bytes[i]);
    return btoa(raw).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  }

  // Available at all only over HTTPS (or localhost) with the Permissions-Policy
  // publickey-credentials-* directives allowed.
  function supported() {
    return (
      typeof window.PublicKeyCredential !== "undefined" &&
      !!(navigator.credentials && navigator.credentials.create)
    );
  }

  function csrfToken() {
    const input = document.querySelector("input[name='csrf_token']");
    return input ? input.value : "";
  }

  // X-Requested-With is what satisfies the server's @cors_required decorator.
  function postJSON(url, body) {
    return fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRFToken": csrfToken(),
      },
      body: JSON.stringify(body || {}),
    });
  }

  async function postJSONOrThrow(url, body) {
    const response = await postJSON(url, body);
    let data = null;
    try {
      data = await response.json();
    } catch (e) {
      data = null;
    }
    if (!response.ok) {
      throw new Error((data && data.message) || "Request failed");
    }
    return data;
  }

  // ── Ceremonies ────────────────────────────────────────────────────

  async function create(options) {
    const publicKey = Object.assign({}, options, {
      challenge: b64urlToBuf(options.challenge),
      user: Object.assign({}, options.user, {
        id: b64urlToBuf(options.user.id),
      }),
      excludeCredentials: (options.excludeCredentials || []).map((c) =>
        Object.assign({}, c, { id: b64urlToBuf(c.id) }),
      ),
    });

    const credential = await navigator.credentials.create({ publicKey });
    return {
      id: credential.id,
      rawId: bufToB64url(credential.rawId),
      type: credential.type,
      authenticatorAttachment: credential.authenticatorAttachment || null,
      clientExtensionResults: credential.getClientExtensionResults(),
      response: {
        clientDataJSON: bufToB64url(credential.response.clientDataJSON),
        attestationObject: bufToB64url(credential.response.attestationObject),
        transports: credential.response.getTransports
          ? credential.response.getTransports()
          : [],
      },
    };
  }

  async function get(options) {
    const publicKey = Object.assign({}, options, {
      challenge: b64urlToBuf(options.challenge),
      allowCredentials: (options.allowCredentials || []).map((c) =>
        Object.assign({}, c, { id: b64urlToBuf(c.id) }),
      ),
    });

    const assertion = await navigator.credentials.get({ publicKey });
    return {
      id: assertion.id,
      rawId: bufToB64url(assertion.rawId),
      type: assertion.type,
      authenticatorAttachment: assertion.authenticatorAttachment || null,
      clientExtensionResults: assertion.getClientExtensionResults(),
      response: {
        clientDataJSON: bufToB64url(assertion.response.clientDataJSON),
        authenticatorData: bufToB64url(assertion.response.authenticatorData),
        signature: bufToB64url(assertion.response.signature),
        // Present for discoverable credentials; that is what lets the server find
        // the account without a username.
        userHandle: assertion.response.userHandle
          ? bufToB64url(assertion.response.userHandle)
          : null,
      },
    };
  }

  // A user who dismisses the browser prompt gets NotAllowedError / AbortError.
  // That is a cancellation, not a failure, and must not be reported as an error.
  function isCancellation(error) {
    return (
      error && (error.name === "NotAllowedError" || error.name === "AbortError")
    );
  }

  window.BWWebAuthn = {
    supported: supported,
    create: create,
    get: get,
    postJSON: postJSON,
    postJSONOrThrow: postJSONOrThrow,
    isCancellation: isCancellation,
    b64urlToBuf: b64urlToBuf,
    bufToB64url: bufToB64url,
  };
})();
