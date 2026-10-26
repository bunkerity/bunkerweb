// About: copy the environment facts the page shows as plain text. Only what is already on screen
// is copied, so nothing the allowlist left out can leak through this button.
(function () {
  const button = document.getElementById("about-copy-diagnostics");
  const facts = document.getElementById("about-environment-facts");
  if (!button || !facts) return;

  button.addEventListener("click", async () => {
    const lines = [];
    facts.querySelectorAll("dt").forEach((term) => {
      const value = term.nextElementSibling;
      const text = value ? value.textContent.trim() : "";
      lines.push(
        text ? `${term.textContent.trim()}: ${text}` : term.textContent.trim(),
      );
    });
    try {
      await navigator.clipboard.writeText(lines.join("\n"));
    } catch (error) {
      return;
    }
    const label = button.querySelector("span");
    const previous = label.textContent;
    label.textContent = t("about.environment.copied", "Copied");
    setTimeout(() => (label.textContent = previous), 1500);
  });
})();
