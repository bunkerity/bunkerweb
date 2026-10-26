/**
 * Main
 */

"use strict";

let menu, animate;

window.bwPrefersReducedMotion = () =>
  window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;

if (window.bwPrefersReducedMotion()) {
  document.querySelectorAll("lottie-player[autoplay]").forEach((player) => {
    player.removeAttribute("autoplay");
  });
}

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

  const syncMenuToggles = () => {
    const expanded = !window.Helpers.isCollapsed();
    document.querySelectorAll("button.layout-menu-toggle").forEach((toggle) => {
      toggle.setAttribute("aria-expanded", String(expanded));
      const desktopIcon = toggle.querySelector(
        ".bx-chevrons-left, .bx-chevrons-right",
      );
      if (desktopIcon) {
        desktopIcon.classList.toggle("bx-chevrons-left", expanded);
        desktopIcon.classList.toggle("bx-chevrons-right", !expanded);
      }
    });
  };
  window.Helpers.on("toggle.adminShell", syncMenuToggles);
  syncMenuToggles();

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

  // Keep the design-system default: expanded on desktop.
  window.Helpers.setCollapsed(false, false);
  syncMenuToggles();
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
      $(this).text(t("validation.invalid_date", "Invalid date"));
    }
  });
});

/**
 * Global search (Ctrl K): pages, plugins and services.
 *
 * Pages come from the sidebar links, plugins from the list navbar.html embeds (the shell already
 * has it), services from one request to /search/services, made the first time the field is
 * focused and cached for the life of the page. A page that never opens the search makes no call.
 * Listbox pattern: DOM focus stays in the input, aria-activedescendant names the active option.
 */
(function () {
  const input = document.getElementById("admin-nav-search");
  const list = document.getElementById("admin-nav-search-results");
  if (!input || !list) return;

  const status = document.getElementById("admin-nav-search-status");
  const wrap = document.getElementById("admin-nav-search-wrap");
  const kbd = document.getElementById("admin-nav-search-kbd");
  const appRoot = document.body.getAttribute("data-app-root") || "";
  const KIND_ICON = {
    page: "bx-file",
    plugin: "bx-plug",
    service: "bx-server",
  };
  const KIND_ORDER = { page: 0, plugin: 1, service: 2 };
  const MAX_RESULTS = 10;

  if (kbd && /Mac|iPhone|iPad/.test(navigator.platform || "")) {
    kbd.textContent = `${String.fromCharCode(0x2318)} K`;
  }

  let services = null;
  let servicesRequested = false;
  let results = [];
  let active = -1;

  const pageEntries = () => {
    const seen = new Set();
    return Array.from(
      document.querySelectorAll(
        "#layout-menu a.menu-link[href]:not(#menu-insights-list a)",
      ),
    )
      .map((link) => ({
        kind: "page",
        label: link.textContent.trim().replace(/\s+/g, " "),
        url: link.getAttribute("href"),
      }))
      .filter(
        (entry) =>
          entry.label &&
          entry.url &&
          !entry.url.startsWith("#") &&
          !/^https?:/.test(entry.url) &&
          !seen.has(entry.url) &&
          seen.add(entry.url),
      );
  };

  const pluginEntries = () => {
    try {
      return JSON.parse(
        document.getElementById("admin-nav-search-plugins")?.value || "[]",
      ).map((plugin) => ({
        kind: "plugin",
        label: plugin.name || plugin.id,
        id: plugin.id,
        url: plugin.url,
      }));
    } catch (e) {
      return [];
    }
  };

  const serviceEntries = () => {
    const base = (input.getAttribute("data-services-url") || "").replace(
      /\/+$/,
      "",
    );
    return (services || []).map((service) => ({
      kind: "service",
      label: service.id,
      url: `${base}/${encodeURIComponent(service.id)}`,
    }));
  };

  function loadServices() {
    if (servicesRequested) return;
    servicesRequested = true;
    fetch(`${appRoot}/search/services`, {
      credentials: "same-origin",
      headers: { "X-Requested-With": "XMLHttpRequest" },
    })
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then((data) => {
        services = data.services || [];
        if (input.value.trim() && !list.hidden) render();
      })
      .catch((error) => {
        servicesRequested = false;
        console.warn(error);
      });
  }

  const escapeHtml = (text) =>
    String(text).replace(
      /[&<>"']/g,
      (c) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[c],
    );

  const highlight = (label, query) => {
    const index = label.toLowerCase().indexOf(query);
    if (index < 0) return escapeHtml(label);
    return (
      escapeHtml(label.slice(0, index)) +
      "<mark>" +
      escapeHtml(label.slice(index, index + query.length)) +
      "</mark>" +
      escapeHtml(label.slice(index + query.length))
    );
  };

  function close() {
    list.hidden = true;
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
  }

  function setActive(index) {
    if (!results.length) return;
    active = (index + results.length) % results.length;
    list.querySelectorAll(".gs-opt").forEach((option, i) => {
      option.classList.toggle("is-active", i === active);
      option.setAttribute("aria-selected", String(i === active));
    });
    input.setAttribute(
      "aria-activedescendant",
      `admin-nav-search-opt-${active}`,
    );
    list
      .querySelector(`#admin-nav-search-opt-${active}`)
      ?.scrollIntoView({ block: "nearest" });
  }

  function render() {
    const raw = input.value.trim();
    const query = raw.toLowerCase();
    if (!query) {
      close();
      return;
    }
    results = [...pageEntries(), ...pluginEntries(), ...serviceEntries()]
      .map((entry) => ({
        entry,
        at: Math.min(
          ...[entry.label, entry.id]
            .filter(Boolean)
            .map((text) => String(text).toLowerCase().indexOf(query))
            .map((i) => (i < 0 ? Infinity : i)),
        ),
      }))
      .filter(({ at }) => at !== Infinity)
      .sort(
        (a, b) =>
          a.at - b.at ||
          KIND_ORDER[a.entry.kind] - KIND_ORDER[b.entry.kind] ||
          a.entry.label.localeCompare(b.entry.label),
      )
      .slice(0, MAX_RESULTS)
      .map(({ entry }) => entry);
    active = results.length ? 0 : -1;

    list.replaceChildren();
    if (results.length) {
      results.forEach((entry, i) => {
        const option = document.createElement("li");
        option.id = `admin-nav-search-opt-${i}`;
        option.className = `gs-opt${i === active ? " is-active" : ""}`;
        option.setAttribute("role", "option");
        option.setAttribute("aria-selected", String(i === active));
        option.dataset.index = String(i);
        option.innerHTML =
          `<i class="bx ${KIND_ICON[entry.kind]}" aria-hidden="true"></i>` +
          `<span class="gs-l">${highlight(entry.label, query)}</span>` +
          `<span class="gs-k">${escapeHtml(t(`shell.search.kind_${entry.kind}`))}</span>`;
        list.append(option);
      });
    } else {
      const empty = document.createElement("li");
      empty.className = "gs-empty";
      empty.setAttribute("role", "presentation");
      empty.textContent =
        typeof i18next === "undefined"
          ? "No items found."
          : i18next.t("status.no_search_results", {
              defaultValue: "No items found.",
            });
      list.append(empty);
    }
    list.hidden = false;
    input.setAttribute("aria-expanded", "true");
    if (active >= 0) {
      input.setAttribute(
        "aria-activedescendant",
        `admin-nav-search-opt-${active}`,
      );
    } else {
      input.removeAttribute("aria-activedescendant");
    }
    if (status) {
      status.textContent = results.length
        ? t("shell.search.status_results", {
            count: results.length,
            interpolation: { escapeValue: false },
          })
        : servicesRequested && services === null
          ? t("shell.search.loading_services")
          : t("shell.search.no_match", {
              query: raw,
              interpolation: { escapeValue: false },
            });
    }
  }

  const go = (index) => {
    const entry = results[index];
    if (!entry) return;
    close();
    window.location.assign(entry.url);
  };

  input.addEventListener("input", render);
  input.addEventListener("focus", () => {
    loadServices();
    if (input.value.trim()) render();
  });
  input.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      if (list.hidden) render();
      else setActive(active + 1);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive(active - 1);
    } else if (event.key === "Enter" && !list.hidden && active >= 0) {
      event.preventDefault();
      go(active);
    } else if (event.key === "Escape") {
      if (!list.hidden) {
        event.preventDefault();
        close();
      } else {
        input.value = "";
      }
    }
  });
  // Keep focus in the input while an option is pressed.
  list.addEventListener("mousedown", (event) => event.preventDefault());
  list.addEventListener("click", (event) => {
    const option = event.target.closest(".gs-opt");
    if (option) go(Number(option.dataset.index));
  });
  document.addEventListener("click", (event) => {
    if (!wrap.contains(event.target)) close();
  });
  document.addEventListener("keydown", (event) => {
    if (
      (event.key === "k" || event.key === "K") &&
      (event.ctrlKey || event.metaKey) &&
      !event.target.closest?.(".ace_editor")
    ) {
      event.preventDefault();
      input.focus();
      input.select();
    }
  });
})();

/**
 * Sidebar parents (Plugins, Plugin insights): open state is remembered per browser, and the
 * insights list filters as you type. Bootstrap's collapse plugin does the toggling.
 */
(function () {
  const storageKey = (name) => `bw-menu-open-${name}`;

  document.querySelectorAll("[data-menu-parent]").forEach((parent) => {
    const name = parent.getAttribute("data-menu-parent");
    const panel = parent.querySelector(".menu-subitems");
    const toggle = parent.querySelector(".menu-parent-toggle");
    if (!panel || !toggle) return;

    let stored = null;
    try {
      stored = localStorage.getItem(storageKey(name));
    } catch (e) {
      // Storage unavailable (private mode): keep the rendered state.
    }
    // The page the user is on keeps its parent open whatever was stored.
    if (stored !== null && !parent.classList.contains("has-active-child")) {
      const open = stored === "1";
      panel.classList.toggle("show", open);
      parent.classList.toggle("is-open", open);
      toggle.classList.toggle("collapsed", !open);
      toggle.setAttribute("aria-expanded", String(open));
    }

    const remember = (open) => {
      parent.classList.toggle("is-open", open);
      try {
        localStorage.setItem(storageKey(name), open ? "1" : "0");
      } catch (e) {
        // Storage unavailable (private mode): non-fatal.
      }
    };
    // The sidebar scrolls inside a PerfectScrollbar: it must re-measure when a parent opens or closes.
    const remeasure = () => window.Helpers?.menuPsScroll?.update();
    panel.addEventListener("shown.bs.collapse", () => {
      remember(true);
      remeasure();
    });
    panel.addEventListener("hidden.bs.collapse", () => {
      remember(false);
      remeasure();
    });
  });

  const filter = document.getElementById("menu-insights-filter");
  const items = document.querySelectorAll(
    "#menu-insights-list > li[data-label]",
  );
  const empty = document.getElementById("menu-insights-empty");
  if (filter) {
    filter.addEventListener("input", () => {
      const query = filter.value.trim().toLowerCase();
      let shown = 0;
      items.forEach((item) => {
        const match = !query || item.dataset.label.includes(query);
        item.hidden = !match;
        if (match) shown += 1;
      });
      if (empty) empty.hidden = shown > 0;
    });
  }

  // The skip link lands on <main>, which is not focusable by default.
  document.querySelector(".skip-link")?.addEventListener("click", () => {
    document.getElementById("main")?.focus({ preventScroll: false });
  });
})();
