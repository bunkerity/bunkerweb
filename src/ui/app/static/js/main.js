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

  $("#select-plugin").on("click", function () {
    $("#plugin-search").focus();
  });

  $("#plugin-search").on("input", function () {
    const inputValue = $(this).val().toLowerCase();
    const dropdownItems = $("#plugins-dropdown-menu li.nav-item");

    dropdownItems.each(function () {
      const item = $(this);
      const text = item.text().toLowerCase();
      console.log(item);
      const pluginId = item
        .find("button")
        .data("bs-target")
        .replace("#navs-plugins-", "");

      if (text.includes(inputValue) || pluginId.includes(inputValue)) {
        item.show();
      } else {
        item.hide();
      }
    });

    // Show "No Item" message if no items match
    if (dropdownItems.filter(":visible").length === 0) {
      if ($(".no-items").length === 0) {
        $("#plugins-dropdown-menu").append(
          '<li class="no-items dropdown-item text-muted">No Item</li>',
        );
      }
    } else {
      $(".no-items").remove();
    }
  });

  $(document).on("click", function (event) {
    if (!$(event.target).closest(".card").length) {
      $("#plugins-dropdown-menu").removeClass("show");
      $("#plugin-search").val("");
      $("#plugin-search").trigger("input");
    }
  });
});
