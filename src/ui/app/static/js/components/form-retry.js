// Reopens the modal form the server just refused, refilled with what was posted and with the
// refusal shown inside it (QA-UI M22, M28). The server half is app/form_retry.py: the route stores
// the posted fields, the page renders them into `#form-retry`, and the form to refill carries
// `data-form-retry="<form id>"`. A page script that builds part of its form itself (the resource
// group entries) listens for `bw:form-retry` on the form; load this file AFTER that script so its
// listener is registered first.
document.addEventListener("DOMContentLoaded", () => {
  const source = document.getElementById("form-retry");
  if (!source) return;
  let retry = null;
  try {
    retry = JSON.parse(source.value || "null");
  } catch (_error) {
    return;
  }
  if (!retry || !retry.form) return;
  const form = document.querySelector(
    `form[data-form-retry="${CSS.escape(retry.form)}"]`,
  );
  if (!form) return;

  const fields = retry.fields || {};
  const valuesOf = (name) => {
    const value = fields[name];
    if (value === undefined) return [];
    return (Array.isArray(value) ? value : [value]).map(String);
  };
  Array.from(form.elements).forEach((field) => {
    if (!field.name || field.name === "csrf_token" || field.type === "file")
      return;
    const values = valuesOf(field.name);
    if (field.type === "checkbox" || field.type === "radio") {
      // An unchecked box is absent from a POST, so "not posted" means "unchecked" here.
      field.checked = values.includes(field.value || "on");
    } else if (field.multiple) {
      Array.from(field.options).forEach((option) => {
        option.selected = values.includes(option.value);
      });
    } else if (values.length) {
      field.value = values[0];
    }
  });

  const alert = document.createElement("div");
  alert.className = "alert alert-danger";
  alert.setAttribute("role", "alert");
  alert.textContent = retry.error || "";
  (form.querySelector(".modal-body") || form).prepend(alert);

  form.dispatchEvent(new CustomEvent("bw:form-retry", { detail: retry }));

  const modalElement = form.closest(".modal");
  if (modalElement && typeof bootstrap !== "undefined") {
    modalElement.addEventListener("hidden.bs.modal", () => alert.remove(), {
      once: true,
    });
    bootstrap.Modal.getOrCreateInstance(modalElement).show();
  }
});
