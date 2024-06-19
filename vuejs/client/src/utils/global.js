import { v4 as uuidv4 } from "uuid";

/**
  @name utils/global.js
  @description This file contains global utils that will be used in the application by default.
  This file contains functions related to accessibilities, cookies, and other global utils.
*/

/**
  @name useGlobal
  @description   This function is a wrapper that contains all the global utils functions.
  This function will for example update the aria-expanded attribute of an element in case we have an aria-controls attribute.
*/
function useGlobal() {
  window.addEventListener("click", (e) => {
    updateExpanded();
  });
}

/**
  @name useGlobal
  @description   This function updates the aria-expanded attribute of an element in case we have an aria-controls attribute.
*/
function updateExpanded() {
  // Wait for previous event and element visibility update
  setTimeout(() => {
    // Check state for all elements that have aria-controls and aria-expanded attributes
    const controlEls = document.querySelectorAll(
      "[aria-controls][aria-expanded]"
    );
    if (!controlEls) return;
    controlEls.forEach((el) => {
      try {
        const targetEl = document.getElementById(
          el.getAttribute("aria-controls")
        );
        if (!targetEl) return el.setAttribute("aria-expanded", "false");
        el.setAttribute(
          "aria-expanded",
          isElHidden(targetEl) ? "false" : "true"
        );
      } catch (err) {}
    });
  }, 50);
}

/**
  @name isElHidden
  @description   This function is a util that checks if an element is hidden.
  This will check for multiple ways to hide an element like aria-hidden, hidden class, display none, visibility hidden, and !hidden class.
*/
function isElHidden(el) {
  return el.hasAttribute("aria-hidden")
    ? el.getAttribute("aria-hidden") === "true"
      ? true
      : false
    : el.classList.contains("hidden")
    ? true
    : el.style.display === "none"
    ? true
    : el.style.visibility === "hidden"
    ? true
    : el.classList.contains("!hidden")
    ? true
    : false;
}

/**
  @name useUUID
  @description This function return a unique identifier using uuidv4 and a random number.
  Adding random number to avoid duplicate uuids when some components are rendered at the same time.
  We can pass a possible existing id, the function will only generate one if the id is empty.
  @param {String} [id=""] - Possible existing id, check if it's empty to generate a new one.
*/
function useUUID(id = "") {
  if (id) return id;
  // Generate a random number between 0 and 10000 to avoid duplicate uuids when some components are rendered at the same time
  const random = Math.floor(Math.random() * 10000);

  return uuidv4() + random;
}

export { useGlobal, useUUID };
