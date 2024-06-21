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
  window.addEventListener(
    "click",
    (e) => {
      console.log("click", e.target);
      // Update some states
      useShowEl(e);
      useHideEl(e);
    },
    true
  );
}

/**
  @name useShowEl
  @description   This function will check if an element controls an element visibility and show it if it's the case.
  The element handler need to have a data-show-el attribute with the id of the target element as value.
  This function needs to be link to an event listener to work.
  This function will check if aria-controls and aria-expanded attributes are present, else will create them.
  @example
  <button data-show-el="modal">Open modal</button>
  <div id="modal" class="hidden">Modal content</div>
  @param {Event} e - The event object.
*/
function useShowEl(e) {
  if (!e.target.hasAttribute("data-show-el")) return;
  // show
  const showElId = e.target.getAttribute("data-show-el");
  document.getElementById(showElId).classList.remove("hidden");
  // Update a11y attributes
  e.target.setAttribute("aria-controls", showElId);
  e.target.setAttribute("aria-expanded", "true");
}

/**
  @name useHideEl
  @description  This function will check if an element controls an element visibility and close it if it's the case.
  The element handler need to have a data-show-el attribute with the id of the target element as value.
  This function needs to be link to an event listener to work.
  This function will check if aria-controls and aria-expanded attributes are present, else will create them.
  @example
  <button data-close-el="modal">Close modal</button>
  <div id="modal" class="">Modal content</div>
  @param {Event} e - The event object.
*/
function useHideEl(e) {
  if (!e.target.hasAttribute("data-hide-el")) return;
  // hide
  const hideElId = e.target.getAttribute("data-hide-el");
  document.getElementById(hideElId).classList.add("hidden");
  // Update a11y attributes
  e.target.setAttribute("aria-controls", hideElId);
  e.target.setAttribute("aria-expanded", "false");
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
