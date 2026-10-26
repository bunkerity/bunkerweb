// Web cache: typed confirmation before "Purge all" (OPS-40) and the compact instances table.
(function () {
  const form = document.getElementById("web-cache-purge-all-form");
  if (form) {
    let confirmed = false;
    form.addEventListener("submit", async (event) => {
      if (confirmed) return;
      event.preventDefault();
      if (!window.BWTypedConfirm) return;
      const ok = await window.BWTypedConfirm.open({
        title: form.dataset.title,
        message: form.dataset.message,
        phrase: form.dataset.phrase,
        confirmLabel: form.dataset.confirm,
      });
      if (!ok) return;
      confirmed = true;
      form.requestSubmit();
    });
  }

  // Compact mode hides the two widest columns (disk usage, path). Instance, state, files, hit
  // rate and every error badge stay, so a compact table never conceals a failure or its scope.
  const toggle = document.getElementById("web-cache-compact");
  const card = document.getElementById("web-cache-instances");
  if (toggle && card) {
    toggle.addEventListener("click", () => {
      const on = toggle.getAttribute("aria-pressed") !== "true";
      toggle.setAttribute("aria-pressed", String(on));
      toggle.classList.toggle("active", on);
      card.classList.toggle("is-compact", on);
    });
  }
})();
