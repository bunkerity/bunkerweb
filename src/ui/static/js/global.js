import { Checkbox } from "./utils/form.js";

class Menu {
  constructor() {
    this.sidebarEl = document.querySelector("[sidebar-menu]");
    this.toggleBtn = document.querySelector("[sidebar-menu-toggle]");
    this.closeBtn = document.querySelector("[sidebar-menu-close]");

    this.toggleBtn.addEventListener("click", this.toggle.bind(this));
    this.closeBtn.addEventListener("click", this.close.bind(this));
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
    this.sidebarEl = document.querySelector("[sidebar-info]");
    this.openBtn = document.querySelector("[sidebar-info-open]");
    this.closeBtn = document.querySelector("[sidebar-info-close]");
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
    this.darkToggleEl = document.querySelector("[dark-toggle]");
    this.darkToggleLabel = document.querySelector("[dark-toggle-label]");
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
      ? "dark"
      : "light";
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
    this.delayBeforeRemove = 8000;
    this.init();
  }

  //remove flash message after this.delay if exist
  init() {
    window.addEventListener("DOMContentLoaded", () => {
      try {
        const flashEl = document.querySelector("[flash-message]");
        setTimeout(() => {
          try {
            flashEl.remove();
          } catch (err) {}
        }, this.delayBeforeRemove);
      } catch (err) {}
    });

    window.addEventListener("click", (e) => {
      try {
        if (e.target.closest("button").hasAttribute("close-flash-message")) {
          const closeBtn = e.target.closest("button");
          const flashEl = closeBtn.closest("[flash-message]");
          flashEl.remove();
        }
      } catch (err) {}
    });
  }
}

class Loader {
  constructor() {
    this.menuContainer = document.querySelector("[menu-container]");
    this.logoContainer = document.querySelector("[loader]");
    this.logoEl = document.querySelector("[loader-img]");
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

const setLoader = new Loader();
const setMenu = new Menu();
const setNews = new News();
const setDarkM = new darkMode();
const setCheckbox = new Checkbox("[sidebar-info]");
const setFlash = new FlashMsg();
