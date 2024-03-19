import { Checkbox, Select, Password, DisabledPop } from "./utils/form.js";

class Menu {
  constructor() {
    this.sidebarEl = document.querySelector("[data-sidebar-menu]");
    this.toggleBtn = document.querySelector("[data-sidebar-menu-toggle]");
    this.closeBtn = document.querySelector("[data-sidebar-menu-close]");

    this.toggleBtn.addEventListener("click", this.toggle.bind(this));
    this.closeBtn.addEventListener("click", this.close.bind(this));
    this.init();
  }

  init() {
    window.addEventListener("click", (e) => {
      try {
        if (
          e.target.closest("aside").hasAttribute("data-sidebar-menu") &&
          e.target.closest("button").getAttribute("role") === "tab"
        ) {
          this.close();
        }
      } catch (err) {}
    });
  }

  toggle() {
    this.sidebarEl.classList.toggle("-translate-x-full");
    if (this.sidebarEl.classList.contains("-translate-x-full")) {
      this.sidebarEl.setAttribute("aria-hidden", "true");
      this.toggleBtn.setAttribute("aria-expanded", "false");
      this.closeBtn.setAttribute("aria-expanded", "false");
    } else {
      this.sidebarEl.setAttribute("aria-hidden", "false");
      this.toggleBtn.setAttribute("aria-expanded", "true");
      this.closeBtn.setAttribute("aria-expanded", "true");
    }
  }

  close() {
    this.toggleBtn.setAttribute("aria-expanded", "false");
    this.closeBtn.setAttribute("aria-expanded", "false");
    this.sidebarEl.classList.add("-translate-x-full");
    this.sidebarEl.setAttribute("aria-hidden", "true");
  }
}

class News {
  constructor() {
    this.BASE_URL = "https://www.bunkerweb.io/";
    this.init();
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
    }

    const newsContainer = document.querySelector("[data-news-container]");
    //remove default message
    newsContainer.textContent = "";
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
      );
      const BASE_URL = this.BASE_URL;
      let cleanHTML = DOMPurify.sanitize(cardHTML);
      //add to DOM
      document
        .querySelector("[data-news-container]")
        .insertAdjacentHTML("afterbegin", cleanHTML);
      document.querySelectorAll(`.blog-click-${news.slug}`).forEach((slug) => {
        slug.addEventListener("click", function () {
          window.open(`${BASE_URL}/blog/post/${news.slug}`, "_blank");
        });
      });
      document.querySelectorAll(".blog-click-tag").forEach((tag) => {
        tag.target = "_blank";
      });
    });
  }

  template(title, slug, img, excerpt, tags, date) {
    //loop on tags to get list
    let tagList = "";
    tags.forEach((tag) => {
      tagList += ` <a
      href="${this.BASE_URL}/blog/tag/${tag.slug}"
      class="blog-click-tag my-0 mr-1 rounded bg-secondary hover:brightness-90 hover:-translate-y-0.4 text-white py-1 px-2 text-sm"
      >
      ${tag.name}
      </a>`;
    });
    //create card
    const card = `
      <div
        class="min-h-[350px] w-full col-span-12 transition dark:bg-slate-700 dark:brightness-[0.885] bg-gray-100 rounded px-6 py-4 my-4 mx-0 flex flex-col justify-between"
      >
        <div>
            <img  role="link"
                class="blog-click-${slug} cursor-pointer rounded w-full  h-40 m-0 object-cover"
                src="${img}"
                alt="image"
            />
            <span role="link"
            class="blog-click-${slug} block cursor-pointer mt-3 mb-1 text-xl font-semibold text-primary dark:text-white tracking-wide">${title}</span>
        </div>
        <div>
            <div  role="link"
            class="blog-click-${slug} cursor-pointer min-h-[100px] mb-3 dark:text-gray-300 text-gray-600 pt-3">
                ${excerpt}
            </div>
            <div class="min-h-[75px] mt-2 flex flex-wrap justify-start items-end align-bottom">
                ${tagList}
            </div>

            <div class="mt-2 flex flex-col justify-start items-start">
                <span class="text-xs  dark:text-gray-300 text-gray-600"
                >Posted on : ${date}
                </span>
            </div>
        </div>
      </div>  `;
    return card;
  }
}

class Sidebar {
  constructor(elAtt, btnOpenAtt, btnCloseAtt) {
    this.sidebarEl = document.querySelector(elAtt);
    this.openBtn = document.querySelector(btnOpenAtt);
    this.closeBtn = document.querySelector(btnCloseAtt);
    this.openBtn.addEventListener("click", this.open.bind(this));
    this.closeBtn.addEventListener("click", this.close.bind(this));
    this.init();
  }

  init() {
    this.openBtn.setAttribute("aria-expanded", "false");
    this.closeBtn.setAttribute("aria-expanded", "false");
    this.sidebarEl.setAttribute("aria-hidden", "false");
  }

  open() {
    this.openBtn.setAttribute("aria-expanded", "true");
    this.closeBtn.setAttribute("aria-expanded", "true");
    this.sidebarEl.classList.add("translate-x-0");
    this.sidebarEl.classList.remove("translate-x-90");
    this.sidebarEl.setAttribute("aria-hidden", "false");
  }

  close() {
    this.openBtn.setAttribute("aria-expanded", "false");
    this.closeBtn.setAttribute("aria-expanded", "false");
    this.sidebarEl.classList.add("translate-x-90");
    this.sidebarEl.classList.remove("translate-x-0");
    this.sidebarEl.setAttribute("aria-hidden", "true");
  }
}

class darkMode {
  constructor() {
    this.htmlEl = document.querySelector("html");
    this.darkToggleEl = document.querySelector("[data-dark-toggle]");
    this.darkToggleLabel = document.querySelector("[data-dark-toggle-label]");
    this.csrf = document.querySelector("input#csrf_token");
    this.init();
  }

  init() {
    this.darkToggleEl.addEventListener("change", (e) => {
      this.toggle();
      this.saveMode();
    });
  }

  toggle() {
    document.querySelector("html").classList.toggle("dark");
    this.darkToggleLabel.textContent = this.darkToggleEl.checked
      ? "dark mode"
      : "light mode";
  }

  async saveMode() {
    const isDark = this.darkToggleEl.checked ? "true" : "false";
    const data = {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-CSRF-Token": this.csrf.value,
      },
      body: JSON.stringify({ darkmode: isDark }),
    };
    const send = await fetch(
      `${location.href.split("/").slice(0, -1).join("/")}/darkmode`,
      data,
    );
  }
}

class FlashMsg {
  constructor() {
    this.openBtn = document.querySelector("[data-flash-sidebar-open]");
    this.flashCount = document.querySelector("[data-flash-count]");
    this.isMsgCheck = false;
    this.init();
  }

  init() {
    //animate message button if message + never opened
    window.addEventListener("load", (e) => {
      if (Number(this.flashCount.textContent) > 0) this.animeBtn();
      // display only one fixed flash message
      const flashFixedEls = document.querySelectorAll(
        "[data-flash-message-fixed]",
      );
      if (flashFixedEls.length > 1) {
        flashFixedEls.forEach((el, i) => {
          if (i > 0) el.remove();
        });
      }
    });
    //stop animate if clicked once
    this.openBtn.addEventListener("click", (e) => {
      try {
        if (
          e.target.closest("button").hasAttribute("data-flash-sidebar-open")
        ) {
          this.isMsgCheck = true;
        }
      } catch (err) {}
    });
    //remove flash message and change count
    window.addEventListener("click", (e) => {
      try {
        if (
          e.target.closest("button").hasAttribute("data-close-flash-message")
        ) {
          //remove logic
          const closeBtn = e.target.closest("button");
          const flashEl = closeBtn.closest("[data-flash-message]");
          flashEl.remove();
          //update count
          this.flashCount.textContent = document.querySelectorAll(
            "[data-flash-message]",
          ).length;
        }
      } catch (err) {}
    });
  }

  animeBtn() {
    this.openBtn.classList.add("rotate-12");

    setTimeout(() => {
      this.openBtn.classList.remove("rotate-12");
      this.openBtn.classList.add("-rotate-12");
    }, 150);

    setTimeout(() => {
      this.openBtn.classList.remove("-rotate-12");
    }, 300);

    setTimeout(() => {
      if (!this.isMsgCheck) {
        this.animeBtn();
      }
    }, 1500);
  }
}

class Loader {
  constructor() {
    this.menuContainer = document.querySelector("[data-menu-container]");
    this.logoContainer = document.querySelector("[data-loader]");
    this.logoEl = document.querySelector("[data-loader-img]");
    this.isLoading = true;
    this.init();
  }

  init() {
    this.loading();
    window.addEventListener("load", (e) => {
      setTimeout(() => {
        this.logoContainer.classList.add("opacity-0");
      }, 350);

      setTimeout(() => {
        this.isLoading = false;
        this.logoContainer.classList.add("hidden");
      }, 650);

      setTimeout(() => {
        this.logoContainer.remove();
      }, 800);
    });
  }

  loading() {
    if ((this.isLoading = true)) {
      setTimeout(() => {
        this.logoEl.classList.toggle("scale-105");
        this.loading();
      }, 300);
    }
  }
}

class Banner {
  constructor() {
    this.bannerEl = document.getElementById("banner");
    this.bannerItems = this.bannerEl.querySelectorAll('[role="listitem"]');
    this.nextDelay = 9000;
    this.transDuration = 700;
    this.menuBtn = document.querySelector("[data-sidebar-menu-toggle]");
    this.menuEl = document.querySelector("[data-sidebar-menu]");
    this.newsBtn = document.querySelector("[data-sidebar-info-open]");
    this.flashBtn = document.querySelector("[data-flash-group]");
    this.init();
  }

  init() {
    window.addEventListener("load", () => {
      this.changeMenu();
      this.loadData();
      this.animateBanner();
    });
  }

  loadData() {
    if (sessionStorage.getItem("bannerRefetch") !== null) {
      const storeStamp = sessionStorage.getItem("bannerRefetch");
      const nowStamp = Math.round(new Date().getTime() / 1000);
      if (+nowStamp > storeStamp) {
        sessionStorage.removeItem("bannerRefetch");
        sessionStorage.removeItem("bannerNews");
      }
    }

    //[
    //   {
    //  "content": "<p  class='dark:brightness-125 mb-0 text-center text-xs xs:text-sm text-white' style='color:white'> Need premium support ? <a class='dark:brightness-125 font-medium underline text-gray-100 hover:no-underline ml-1' style='text-decoration:underline; color :  white;' href='https://panel.bunkerweb.io/?utm_campaign=self&utm_source=doc'>Check BunkerWeb Panel</a></p>"
    // }
    //]
    // Try to get data from api
    if (sessionStorage.getItem("bannerNews") !== null) {
      console.log(JSON.parse(sessionStorage.getItem("bannerNews")));
      return this.updateBanner(
        JSON.parse(sessionStorage.getItem("bannerNews")),
      );
    }
    fetch("https://www.bunkerweb.io/api/bw-ui-news")
      .then((res) => {
        return res.json();
      })
      .then((res) => {
        sessionStorage.setItem("bannerNews", JSON.stringify(res.data[0].data));
        // Refetch after one hour
        sessionStorage.setItem(
          "bannerRefetch",
          Math.round(new Date().getTime() / 1000) + 3600,
        );
        return this.updateBanner(res.data[0].data);
      })
      .catch((e) => {});
  }

  updateBanner(bannerNews) {
    // store for next time
    const bannerItems = this.bannerEl.querySelectorAll('[role="listitem"]');
    const maxItems = Math.min(bannerNews.length, bannerItems.length);

    for (let i = 0; i < maxItems; i++) {
      const bannerEl = bannerItems[i];
      bannerEl.innerHTML = bannerNews[i]["content"];
    }
  }

  animateBanner() {
    setInterval(() => {
      // Get current visible
      let visibleEl;
      this.bannerItems.forEach((item) => {
        if (item.getAttribute("aria-hidden") === "false") {
          visibleEl = item;
        }
      });

      // Get next one to show (next index or first one)
      let nextEl =
        this.bannerEl.querySelector(
          `[role="listitem"][data-id="${
            +visibleEl.getAttribute("data-id") + 1
          }"]`,
        ) || this.bannerEl.querySelector(`[role="listitem"][data-id="0"]`);

      // Hide current one
      visibleEl.classList.add("-left-full");
      visibleEl.classList.remove("left-0");
      visibleEl.setAttribute("aria-hidden", "true");
      setTimeout(() => {
        visibleEl.classList.remove("transition-all");
      }, this.transDuration + 10);
      setTimeout(() => {
        visibleEl.classList.add("opacity-0");
      }, this.transDuration + 20);
      setTimeout(() => {
        visibleEl.classList.remove("-left-full");
        visibleEl.classList.add("left-full");
      }, this.transDuration * 2);

      // Show next one
      nextEl.classList.remove("opacity-0");
      nextEl.classList.add("transition-all");
      nextEl.classList.add("left-0");
      nextEl.classList.remove("left-full");
      nextEl.setAttribute("aria-hidden", "false");
    }, this.nextDelay);
  }

  // update float button position looking at current banner visibility
  changeMenu() {
    let options = {
      root: null,
      rootMargin: "0px",
      threshold: 0.35,
    };

    let observer = new IntersectionObserver((entries, observer) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          this.menuEl.classList.add("mt-[4.5rem]");
          this.menuBtn.classList.add("top-[8.2rem]", "sm:top-[4.5rem]");
          this.newsBtn.classList.add("top-[4.5rem]");
          this.flashBtn.classList.add("top-[4.5rem]");
          this.menuBtn.classList.remove("top-16", "sm:top-2");
          this.newsBtn.classList.remove("top-2");
          this.flashBtn.classList.remove("top-2");
          this.menuEl.classList.remove("mt-2");
        }

        if (!entry.isIntersecting) {
          this.menuEl.classList.add("mt-2");
          this.menuBtn.classList.add("top-16", "sm:top-2");
          this.newsBtn.classList.add("top-2");
          this.flashBtn.classList.add("top-2");
          this.menuBtn.classList.remove("top-[8.2rem]", "sm:top-[4.5rem]");
          this.newsBtn.classList.remove("top-[4.5rem]");
          this.flashBtn.classList.remove("top-[4.5rem]");
          this.menuEl.classList.remove("mt-[4.5rem]");
        }
      });
    }, options);

    observer.observe(this.bannerEl);
  }
}

class Clipboard {
  constructor() {
    this.init();
  }

  init() {
    // Show clipboard copy if https
    window.addEventListener("load", () => {
      if (!window.location.href.startsWith("https://")) return;

      document.querySelectorAll("[data-clipboard-copy]").forEach((el) => {
        el.classList.remove("hidden");
      });
    });

    window.addEventListener("click", (e) => {
      if (!e.target.hasAttribute("data-clipboard-target")) return;

      navigator.permissions
        .query({ name: "clipboard-write" })
        .then((result) => {
          if (result.state === "granted" || result.state === "prompt") {
            /* write to the clipboard now */
            const copyEl = document.querySelector(
              e.target.getAttribute("data-clipboard-target"),
            );

            copyEl.select();
            copyEl.setSelectionRange(0, 99999); // For mobile devices

            // Copy the text inside the text field
            navigator.clipboard.writeText(copyEl.value);
          }
        });
    });
  }
}

const setCheckbox = new Checkbox();
const setSelect = new Select();
const setPassword = new Password();
const setDisabledPop = new DisabledPop();
const setNews = new News();
const setBanner = new Banner();
const setDarkM = new darkMode();
const setFlash = new FlashMsg();
const setLoader = new Loader();
const setMenu = new Menu();

const setNewsSidebar = new Sidebar(
  "[data-sidebar-info]",
  "[data-sidebar-info-open]",
  "[data-sidebar-info-close]",
);

const setFlashSidebar = new Sidebar(
  "[data-flash-sidebar]",
  "[data-flash-sidebar-open]",
  "[data-flash-sidebar-close]",
);

const setClipboard = new Clipboard();
