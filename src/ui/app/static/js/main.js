/**
 * Main
 */

"use strict";

let menu, animate;

(function () {
  // Initialize menu
  //-----------------

  let layoutMenuEl = document.querySelectorAll("#layout-menu");
  layoutMenuEl.forEach(function (element) {
    menu = new Menu(element, {
      orientation: "vertical",
      closeChildren: false,
    });
    // Change parameter to true if you want scroll animation
    window.Helpers.scrollToActive((animate = false));
    window.Helpers.mainMenu = menu;
  });

  // Initialize menu togglers and bind click on each
  let menuToggler = document.querySelectorAll(".layout-menu-toggle");
  menuToggler.forEach((item) => {
    item.addEventListener("click", (event) => {
      event.preventDefault();
      window.Helpers.toggleCollapsed();
    });
  });

  // Display menu toggle (layout-menu-toggle) on hover with delay
  let delay = function (elem, callback) {
    let timeout = null;
    elem.onmouseenter = function () {
      // Set timeout to be a timer which will invoke callback after 300ms (not for small screen)
      if (!Helpers.isSmallScreen()) {
        timeout = setTimeout(callback, 300);
      } else {
        timeout = setTimeout(callback, 0);
      }
    };

    elem.onmouseleave = function () {
      // Clear any timers set to timeout
      document.querySelector(".layout-menu-toggle").classList.remove("d-block");
      clearTimeout(timeout);
    };
  };
  if (document.getElementById("layout-menu")) {
    delay(document.getElementById("layout-menu"), function () {
      // not for small screen
      if (!Helpers.isSmallScreen()) {
        document.querySelector(".layout-menu-toggle").classList.add("d-block");
      }
    });
  }

  // Display in main menu when menu scrolls
  let menuInnerContainer = document.getElementsByClassName("menu-inner"),
    menuInnerShadow = document.getElementsByClassName("menu-inner-shadow")[0];
  if (menuInnerContainer.length > 0 && menuInnerShadow) {
    menuInnerContainer[0].addEventListener("ps-scroll-y", function () {
      if (this.querySelector(".ps__thumb-y").offsetTop) {
        menuInnerShadow.style.display = "block";
      } else {
        menuInnerShadow.style.display = "none";
      }
    });
  }

  // Init helpers & misc
  // --------------------

  // Init BS Tooltip
  const tooltipTriggerList = [].slice.call(
    document.querySelectorAll('[data-bs-toggle="tooltip"]'),
  );
  tooltipTriggerList.map(function (tooltipTriggerEl) {
    return new bootstrap.Tooltip(tooltipTriggerEl);
  });

  // Accordion active class
  const accordionActiveFunction = function (e) {
    if (e.type == "show.bs.collapse" || e.type == "show.bs.collapse") {
      e.target.closest(".accordion-item").classList.add("active");
    } else {
      e.target.closest(".accordion-item").classList.remove("active");
    }
  };

  const accordionTriggerList = [].slice.call(
    document.querySelectorAll(".accordion"),
  );
  const accordionList = accordionTriggerList.map(function (accordionTriggerEl) {
    accordionTriggerEl.addEventListener(
      "show.bs.collapse",
      accordionActiveFunction,
    );
    accordionTriggerEl.addEventListener(
      "hide.bs.collapse",
      accordionActiveFunction,
    );
  });

  // Auto update layout based on screen size
  window.Helpers.setAutoUpdate(true);

  // Toggle Password Visibility
  window.Helpers.initPasswordToggle();

  // Speech To Text
  window.Helpers.initSpeechToText();

  // Manage menu expanded/collapsed with templateCustomizer & local storage
  //------------------------------------------------------------------

  // If current layout is horizontal OR current window screen is small (overlay menu) than return from here
  if (window.Helpers.isSmallScreen()) {
    return;
  }

  // If current layout is vertical and current window screen is > small

  // Auto update menu collapsed/expanded based on the themeConfig
  window.Helpers.setCollapsed(true, false);
})();

/**
 * Custom
 */

$(document).ready(function () {
  // Generic Copy to Clipboard with Tooltip
  $(".copy-to-clipboard").on("click", function () {
    const input = $(this).closest(".input-group").find("input")[0];

    // Use the Clipboard API
    navigator.clipboard
      .writeText(input.value)
      .then(() => {
        // Show tooltip
        const button = $(this);
        button.attr("data-bs-original-title", "Copied!").tooltip("show");

        // Hide tooltip after 2 seconds
        setTimeout(() => {
          button.tooltip("hide").attr("data-bs-original-title", "");
        }, 2000);
      })
      .catch((err) => {
        console.error("Failed to copy text: ", err);
      });
  });

  $("#pluginsCollapse").on("shown.bs.collapse", function () {
    $('[data-bs-target="#pluginsCollapse"] .chevron-icon')
      .addClass("chevron-rotate")
      .removeClass("chevron-rotate-back");
  });

  $("#pluginsCollapse").on("hidden.bs.collapse", function () {
    $('[data-bs-target="#pluginsCollapse"] .chevron-icon')
      .removeClass("chevron-rotate")
      .addClass("chevron-rotate-back");
  });

  $("#extraPagesCollapse").on("shown.bs.collapse", function () {
    $('[data-bs-target="#extraPagesCollapse"] .chevron-icon')
      .addClass("chevron-rotate")
      .removeClass("chevron-rotate-back");
  });

  $("#extraPagesCollapse").on("hidden.bs.collapse", function () {
    $('[data-bs-target="#extraPagesCollapse"] .chevron-icon')
      .removeClass("chevron-rotate")
      .addClass("chevron-rotate-back");
  });

  $(".toast-datetime").each(function () {
    const isoDateStr = $(this).text().trim();

    // Parse the ISO format date string
    const date = new Date(isoDateStr);

    // Check if the date is valid
    if (!isNaN(date)) {
      // Convert to local date and time string
      const localDateStr = date.toLocaleString();

      // Update the text content with the local date string
      $(this).text(localDateStr);
    } else {
      // Handle invalid date
      console.error(`Invalid date string: ${isoDateStr}`);
      $(this).text("Invalid date");
    }
  });
});
