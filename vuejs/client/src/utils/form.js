/**
  @name utils/form.js
  @description This file contains form utils that will be used in the application by default.
    This file contains functions related to form validation, form submission, and other form utils.
*/

/**
  @name useForm
  @description  This function is a composable wrapper that contains all the form utils functions.
 This function will for example look for elements with data-submit-form attribute and submit the form with the data attributes.
*/
function useForm() {
  window.addEventListener("click", (e) => {
    if (!e.target.hasAttribute("data-submit-form")) return;
    const data = useGetFormDataAttr(e.target);
    useSubmitForm(data);
  });
}

/**
  @name useSubmitForm
  @description   Create programmatically a form element and submit it with the given data object of type {key: value}.
  This will create a FormData and append data arguments to it, retrieve the csrf token and send it with a regular form.
      @example
  {
    instance: "1",
    operation: "delete",
  }
  @param {object} data - Object with the form data to submit.
*/
function useSubmitForm(data) {
  // Create a form element
  const form = document.createElement("form");
  form.style.display = "none";
  form.method = "POST";
  // Retrieve csrf token form data-crfs-token
  try {
    const csrfToken = document.querySelector("[data-csrf-token]");
    if (csrfToken) {
      data.csrf_token = csrfToken.getAttribute("data-csrf-token");
    }
  } catch (e) {}
  // Add input elements with the data object
  for (const key in data) {
    const input = document.createElement("input");
    input.type = "hidden";
    input.name = key;
    input.value = data[key];
    form.appendChild(input);
  }
  // Append the form to the body and submit it
  document.querySelector("body").appendChild(form);
  console.log(form);
  form.submit();
}

/**
  @name useGetFormDataAttr
  @description   /Get the form data store on attributes of the element.
  Format is data-form-<key>="<value>"
  @example document.querySelector("[data-submit-form]")
  @param {DOMElement} el - Element to get the data attributes.
*/
function useGetFormDataAttr(el) {
  const data = {};
  const attributes = el.attributes;
  for (let i = 0; i < attributes.length; i++) {
    if (attributes[i].name.includes("data-form-")) {
      const key = attributes[i].name.replace("data-form-", "");
      data[key] = attributes[i].value;
    }
  }
  return data;
}

export { useForm };
