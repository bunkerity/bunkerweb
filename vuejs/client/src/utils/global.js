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

export { useGlobal };
