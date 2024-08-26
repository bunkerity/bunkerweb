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

class News {
  constructor() {
    this.BASE_URL = "https://www.bunkerweb.io/";
  }

  init() {
    window.addEventListener("load", () => {
      if (sessionStorage.getItem("lastRefetch") !== null) {
        const storeStamp = sessionStorage.getItem("lastRefetch");
        const nowStamp = Math.round(new Date().getTime() / 1000);
        if (+nowStamp > storeStamp) {
          sessionStorage.removeItem("lastRefetch");
          sessionStorage.removeItem("lastNews");
        }
      }

      if (sessionStorage.getItem("lastNews") !== null)
        return this.render(JSON.parse(sessionStorage.getItem("lastNews")));

      fetch("https://www.bunkerweb.io/api/posts/0/2")
        .then((res) => {
          return res.json();
        })
        .then((res) => {
          const reverseData = res.data.reverse();
          return this.render(reverseData);
        })
        .catch((e) => {});
    });
  }

  render(lastNews) {
    // store for next time if not the case
    if (
      !sessionStorage.getItem("lastNews") &&
      !sessionStorage.getItem("lastRefetch")
    ) {
      sessionStorage.setItem(
        "lastRefetch",
        Math.round(new Date().getTime() / 1000) + 3600,
      );
      sessionStorage.setItem("lastNews", JSON.stringify(lastNews));
      const newsNumber = lastNews.length;
      document.querySelector("#news-pill").insertAdjacentHTML(
        "beforeend",
        DOMPurify.sanitize(`<span class="badge rounded-pill badge-center-sm bg-danger ms-1_5"
    >${newsNumber}</span
  >`),
      );
      document.querySelector("#news-button").insertAdjacentHTML(
        "beforeend",
        DOMPurify.sanitize(`<span
    class="badge-dot-text position-absolute top-0 start-100 translate-middle badge rounded-pill bg-danger"
  >
    ${newsNumber}
    <span class="visually-hidden">unread news</span>
  </span>`),
      );
    }

    const newsContainer = document.querySelector("[data-news-container]");
    const lastItem = lastNews[0];
    //remove default message
    newsContainer.textContent = "";
    document
      .querySelector("[data-news-container]")
      .insertAdjacentHTML(
        "afterbegin",
        `<div data-news-row class="row g-6 justify-content-center">`,
      );
    //render last news
    lastNews.forEach((news) => {
      //create html card from  infos
      const cardHTML = this.template(
        news.title,
        news.slug,
        news.photo.url,
        news.excerpt,
        news.tags,
        news.date,
        news === lastItem,
      );
      const BASE_URL = this.BASE_URL;
      let cleanHTML = DOMPurify.sanitize(cardHTML);
      //add to DOM inside the created div
      document
        .querySelector("[data-news-row]")
        .insertAdjacentHTML("afterbegin", cleanHTML);
      document.querySelectorAll(`.blog-click-${news.slug}`).forEach((slug) => {
        slug.addEventListener("click", function () {
          window.open(
            `${BASE_URL}blog/post/${news.slug}?utm_campaign=self&utm_source=ui`,
            "_blank",
          );
        });
      });
      document.querySelectorAll(".blog-click-tag").forEach((tag) => {
        tag.target = "_blank";
      });
    });
    document
      .querySelector("[data-news-container]")
      .insertAdjacentHTML("beforeend", "</div>");
  }

  template(title, slug, img, excerpt, tags, date, last) {
    //loop on tags to get list
    let tagList = "";
    tags.forEach((tag) => {
      tagList += `<a
  role="button"
  href="${this.BASE_URL}/blog/tag/${tag.slug}?utm_campaign=self&utm_source=ui"
  aria-pressed="true"
  class="btn btn-sm btn-outline-primary"
  target="_blank"
  rel="noopener"
>
  <span class="tf-icons bx bx-xs bx-purchase-tag bx-18px me-2"></span
  >${tag.name}
</a>
`;
    });
    const card = `<div class="col-md-11 col-xl-11 ${last ? "" : "mb-1"}">
  <div class="card">
    <a
      href="${this.BASE_URL}blog/post/${slug}?utm_campaign=self&utm_source=ui"
      target="_blank"
      rel="noopener"
      ><img class="card-img-top" src="${img}" alt="News image"
    /></a>
    <div class="card-body">
      <h5 class="card-title">
        <a
          href="${
            this.BASE_URL
          }blog/post/${slug}?utm_campaign=self&utm_source=ui"
          target="_blank"
          rel="noopener"
          >${title}</a
        >
      </h5>
      <p class="card-text">${excerpt}</p>
      <p class="d-flex flex-wrap">${tagList}</p>
      <p class="card-text">
        <small class="text-muted">Posted on : ${date}</small>
      </p>
    </div>
  </div>
</div>
`;
    return card;
  }
}

const setNews = new News();

DOMPurify.addHook("afterSanitizeAttributes", function (node) {
  // set all elements owning target to target=_blank
  if ("target" in node) {
    node.setAttribute("target", "_blank");
    node.setAttribute("rel", "noopener");
  }
});

document.addEventListener("DOMContentLoaded", function onContentLoaded() {
  setNews.init();

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
});
