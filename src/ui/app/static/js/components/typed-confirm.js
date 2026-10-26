/* Text-only confirmation content: callers retain permission checks and perform the
   action only when the returned Promise resolves true. Include before leave-guard.js. */
(function () {
  "use strict";
  if (window.BWConfirm) return;
  let active = false;
  function open(options = {}) {
    if (active) return Promise.resolve(false);
    active = true;
    const t = window.i18next?.t || ((key, fallback) => fallback || key);
    const previousFocus = document.activeElement;
    const root = document.createElement("div");
    root.classList.add("modal", "fade");
    root.tabIndex = -1;
    root.setAttribute("aria-labelledby", "bw-confirm-title");
    root.setAttribute("aria-hidden", "true");
    root.innerHTML = `<div class="modal-dialog modal-dialog-centered"><div class="modal-content">
      <div class="modal-header"><h5 class="modal-title" id="bw-confirm-title"></h5></div>
      <div class="modal-body"><p class="bw-confirm-message"></p>
        <div class="bw-confirm-phrase"><label for="bw-confirm-input" class="form-label"></label>
        <input id="bw-confirm-input" class="form-control" type="text" autocomplete="off" spellcheck="false"></div>
      </div><div class="modal-footer">
        <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal"></button>
        <button type="button" class="btn bw-confirm-submit"></button>
      </div></div></div>`;
    root.querySelector(".modal-title").textContent =
      options.title || t("table_system.confirm_title", "Confirm action");
    root.querySelector(".bw-confirm-message").textContent =
      options.message || "";
    const cancel = root.querySelector("[data-bs-dismiss]");
    cancel.textContent = options.cancelLabel || t("button.cancel", "Cancel");
    const confirm = root.querySelector(".bw-confirm-submit");
    confirm.classList.add(
      options.destructive === false ? "btn-primary" : "btn-danger",
    );
    confirm.textContent =
      options.confirmLabel || t("table_system.confirm", "Confirm");
    const input = root.querySelector("input");
    const phrase = options.phrase;
    root.querySelector(".bw-confirm-phrase").hidden = !phrase;
    root.querySelector("label").textContent = phrase
      ? t("table_system.type_phrase", "Type {{phrase}} to confirm", { phrase })
      : "";
    const valid = () => !phrase || input.value === phrase;
    confirm.disabled = !valid();
    input.addEventListener("input", () => {
      confirm.disabled = !valid();
    });
    document.body.append(root);
    const modal = new bootstrap.Modal(root);
    return new Promise((resolve) => {
      let confirmed = false;
      confirm.addEventListener("click", () => {
        if (!valid()) return;
        confirmed = true;
        modal.hide();
      });
      root.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && event.target === input && valid()) {
          event.preventDefault();
          confirm.click();
        }
      });
      $(root).one("shown.bs.modal", () => (phrase ? input : cancel).focus());
      $(root).one("hidden.bs.modal", () => {
        modal.dispose();
        root.remove();
        active = false;
        if (previousFocus?.isConnected) previousFocus.focus();
        resolve(confirmed);
      });
      modal.show();
    });
  }
  window.BWConfirm = { open };
  window.BWTypedConfirm = {
    open(options) {
      if (
        !options ||
        typeof options.phrase !== "string" ||
        !options.phrase.trim()
      ) {
        throw new TypeError(`BWTypedConfirm requires a non-empty phrase`);
      }
      return open(options);
    },
  };
})();
