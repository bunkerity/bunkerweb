import { Tabs } from "./utils/settings.js";

class TabPopover {
  constructor() {
    this.init();
  }

  init() {
    window.addEventListener("pointerover", (e) => {
      //POPOVER LOGIC
      try {
        if (
          e.target.closest("button").hasAttribute(`data-popover-btn`) ||
          e.target.closest("svg").hasAttribute(`data-popover-btn`)
        ) {
          this.showPopover(e.target);
        }
      } catch (err) {}
    });

    window.addEventListener("pointerout", (e) => {
      //POPOVER LOGIC
      try {
        if (
          e.target.closest("button").hasAttribute(`data-popover-btn`) ||
          e.target.closest("svg").hasAttribute(`data-popover-btn`)
        ) {
          this.hidePopover(e.target);
        }
      } catch (err) {}
    });
  }

  showPopover(el) {
    const btn = el.closest("button").hasAttribute("data-popover-btn")
      ? el.closest("button")
      : el.closest("svg");
    const popoverName = btn.getAttribute("data-popover-btn");
    //toggle curr popover
    const popover = btn.parentElement.querySelector(
      `[data-popover-content=${popoverName}]`,
    );
    popover.classList.add("transition-all", "delay-200", "opacity-0");
    popover.classList.remove("hidden");
    setTimeout(() => {
      popover.classList.remove("opacity-0");
    }, 10);
  }

  hidePopover(el) {
    const btn = el.closest("button").hasAttribute("data-popover-btn")
      ? el.closest("button")
      : el.closest("svg");
    const popoverName = btn.getAttribute("data-popover-btn");
    //toggle curr popover
    const popover = btn.parentElement.querySelector(
      `[data-popover-content=${popoverName}]`,
    );
    popover.classList.add("hidden");
    popover.classList.remove("transition-all", "delay-200");
  }
}


class SubmitAccount {
  constructor() {
    this.pwEl = document.querySelector("#admin_password");
    this.pwCheckEl = document.querySelector("#admin_password_check");
    this.pwAlertEl = document.querySelector("[data-pw-alert]");
    this.formEl = document.querySelector("#password-form");
    this.init();
  }

  init() {
    // Check password to send
    this.checkSamePW();
    this.pwCheckEl.addEventListener("input", (e) => {
      this.checkSamePW();
    });

    this.pwEl.addEventListener("input", (e) => {
      this.checkSamePW();
    });

    // Submit
    this.formEl.addEventListener("submit", (e) => {
      // Case not same PW
      if (this.pwEl.value !== this.pwCheckEl.value) return e.preventDefault();

      this.formEl.submit();
    });
  }

  checkSamePW() {
    if (!this.pwEl.value || !this.pwCheckEl.value) return this.hidePWAlert();

    if (this.pwEl.value !== this.pwCheckEl.value) return this.showPWAlert();

    return this.hidePWAlert();
  }

  hidePWAlert() {
    this.pwCheckEl.classList.remove(
      "focus:!border-red-500",
      "focus:valid:!border-red-500",
      "focus:!ring-red-500",
      "focus:valid:!ring-red-500",
      "active:!border-red-500",
      "active:valid:!border-red-500",
      "valid:!border-red-500"
    );
    this.pwAlertEl.classList.add("opacity-0");
    this.pwAlertEl.setAttribute("aria-hidden", "true");
  }

  showPWAlert() {
    this.pwCheckEl.classList.add(
      "focus:!border-red-500",
      "focus:valid:!border-red-500",
      "focus:!ring-red-500",
      "focus:valid:!ring-red-500",
      "active:!border-red-500",
      "active:valid:!border-red-500",
      "valid:!border-red-500"
    );
    this.pwAlertEl.classList.remove("opacity-0");
    this.pwAlertEl.setAttribute("aria-hidden", "false");
  }
}

class PwBtn {
  constructor() {
    this.init();
  }

  init() {
    window.addEventListener("click", (e) => {
      if (!e.target.getAttribute("data-setting-password")) return;
      const passwordContainer = e.target.closest("[data-input-group]");
      const inpEl = passwordContainer.querySelector("input");
      const invBtn = passwordContainer.querySelector(
        '[data-setting-password="invisible"]'
      );
      const visBtn = passwordContainer.querySelector(
        '[data-setting-password="visible"]'
      );
      inpEl.setAttribute(
        "type",
        inpEl.getAttribute("type") === "password" ? "text" : "password"
      );

      if (inpEl.getAttribute("type") === "password") {
        invBtn.classList.add("hidden");
        visBtn.classList.add("flex");
        visBtn.classList.remove("hidden");
      } else {
        visBtn.classList.add("hidden");
        invBtn.classList.add("flex");
        invBtn.classList.remove("hidden");
      }
    });
  }
}

// Check flash message
// Show previous failed form tab
class SwitchTabForm {
  constructor() {
    this.init();
  }

  init() {
    window.addEventListener("load", () => {
      // Check flash
      const flashMsg = document.querySelector("[data-flash-message]");
      if (!flashMsg) return;
      const content = flashMsg.querySelector("p").textContent.toLowerCase();

      const names = ["global", "password", "username", "totp"];

      names.forEach((name) => {
        this.showRelateTab(name, content);
      });
    });
  }

  showRelateTab(name, content) {
    if (!content.includes(`(${name})`)) return;
    document.querySelector(`button[data-tab-handler="${name}"]`).click();
  }
}

const setPWBtn = new PwBtn();
const setSubmit = new SubmitAccount();
const setTabs = new Tabs();
const setTabPopover = new TabPopover();
const setSwitchTabForm = new SwitchTabForm();
