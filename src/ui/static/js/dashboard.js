import { Checkbox, Loader } from "./utils.js";

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
      },
      body: JSON.stringify({ darkmode: isDark, csrf_token: this.csrf.value }),
    };
    const send = await fetch(`${location.href}/darkmode}`, data);
  }
}

class FlashMsg {
  constructor() {
    this.delayBeforeRemove = 5000;
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
  }
}

const setLoader = new Loader();
const setMenu = new Menu();
const setNews = new News();
const setDarkM = new darkMode();
const setCheckbox = new Checkbox("[sidebar-info]");
const setFlash = new FlashMsg();
