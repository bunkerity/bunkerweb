/**
 * Post-upgrade recap: open once, stamp on close.
 *
 * Loaded only when the modal is rendered, which happens only when this user has releases it
 * has not seen — so a caught-up operator downloads nothing and issues no request.
 *
 * The stamp goes out on `hidden.bs.modal`, whatever closed it: the button, the header cross,
 * Escape or a backdrop click all mean "seen". A failed stamp is deliberately left alone rather
 * than retried — the recap simply comes back, which is the truthful outcome.
 */
(function () {
  "use strict";

  const root = document.getElementById("whats-new-root");
  const modalEl = document.getElementById("whats-new-modal");
  if (!root || !modalEl || !window.bootstrap) return;

  let stamped = false;

  modalEl.addEventListener("hidden.bs.modal", () => {
    if (stamped) return;
    stamped = true;
    fetch(root.dataset.stateUrl, {
      method: "PATCH",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
      },
      body: JSON.stringify({ version: root.dataset.version }),
    }).catch(() => {
      // Nothing to tell the user here: the modal is already gone and it will be back.
      stamped = false;
    });
  });

  window.bootstrap.Modal.getOrCreateInstance(modalEl).show();
})();
