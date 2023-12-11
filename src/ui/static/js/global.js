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
  }

  close() {
    this.sidebarEl.classList.add("-translate-x-full");
  }
}

class News {
  constructor() {
    this.BASE_URL = "https://www.bunkerweb.io/";
    this.init();
  }

  init() {
    window.addEventListener("load", async () => {
      try {
        const res = await fetch("https://www.bunkerweb.io/api/posts/0/2", {
          headers: {
            method: "GET",
          },
        });
        return await this.render(res);
      } catch (err) {}
    });
  }

  render(lastNews) {
    const newsContainer = document.querySelector("[data-news-container]");
    //remove default message
    newsContainer.textContent = "";
    //render last news
    lastNews.forEach((news) => {
      //get info
      const slug = news.slug;
      const img = news.photo.url;
      const excerpt = news.excerpt;
      const tags = news.tags;
      const date = news.date;
      const lastUpdate = news.lastUpdate;
      //create html card from  infos
      const cardHTML = this.template(
        slug,
        img,
        excerpt,
        tags,
        date,
        lastUpdate
      );
      let cleanHTML = DOMPurify.sanitize(cardHTML);
      //add to DOM
      document
        .querySelector("[data-news-container]")
        .insertAdjacentHTML("afterbegin", cleanHTML);
    });
  }

  template(slug, img, excerpt, tags, date, lastUpdate) {
    //loop on tags to get list
    let tagList = "";
    tags.forEach((tag) => {
      tagList += ` <a
      href="${this.BASE_URL}/blog/tag/${tag.slug}"
      class="my-0 mr-1 rounded bg-secondary hover:brightness-90 hover:-translate-y-0.4 text-white py-1 px-2 text-sm"
      >
      ${tag.name}
      </a>`;
    });
    //create card
    const card = `
      <div
        class="min-h-[400px] w-full col-span-12 transition hover:-translate-y-2  bg-gray-100 dark:bg-slate-900 rounded px-6 py-4 m-2  flex flex-col justify-between"
      >
        <div>
            <img  role="link"
                onclick="window.location.href='${this.BASE_URL}/blog/post/${slug}'"
                class="cursor-pointer rounded w-full  h-40 m-0 object-cover"
                src="${img}"
                alt="image"
            />
            <h3 role="link"
            onclick="window.location.href='${this.BASE_URL}/blog/post/${slug}'"
            class="cursor-pointer mt-3 mb-1  text-3xl dark:text-white tracking-wide">{{ post['title'] }}</h3>
        </div>
        <div>
            <div  role="link"
            onclick="window.location.href='${this.BASE_URL}/blog/post/${slug}'"
            class="cursor-pointer min-h-[130px] mb-3 text-lg dark:text-gray-300 text-gray-600 pt-3">
                ${excerpt}
            </div>
            <div class="min-h-[75px] mt-2 flex flex-wrap justify-start items-end align-bottom">
                ${tagList}
            </div>

            <div class="mt-2 flex flex-col justify-start items-start">
                <span class="text-xs  dark:text-gray-300 text-gray-600"
                >Posted on : ${date}</span
                >
                {% if post["updatedAt"] %}
                <span class="text-xs  dark:text-gray-300 text-gray-600"
                >Last update : ${lastUpdate}</span
                >
                {%endif%}
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
  }

  open() {
    this.sidebarEl.classList.add("translate-x-0");
    this.sidebarEl.classList.remove("translate-x-90");
  }

  close() {
    this.sidebarEl.classList.add("translate-x-90");
    this.sidebarEl.classList.remove("translate-x-0");
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
      data
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
            "[data-flash-message]"
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
    this.init();
  }

  init() {
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
          }"]`
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
}

const setLoader = new Loader();
const setMenu = new Menu();
const setNewsSidebar = new Sidebar(
  "[data-sidebar-info]",
  "[data-sidebar-info-open]",
  "[data-sidebar-info-close]"
);

const setCheckbox = new Checkbox();
const setSelect = new Select();
const setPassword = new Password();
const setDisabledPop = new DisabledPop();

const setFlashSidebar = new Sidebar(
  "[data-flash-sidebar]",
  "[data-flash-sidebar-open]",
  "[data-flash-sidebar-close]"
);
const setNews = new News();
const setDarkM = new darkMode();
const setFlash = new FlashMsg();

const setBanner = new Banner();
