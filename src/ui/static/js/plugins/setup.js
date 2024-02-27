class SetupPlugin {
  constructor(data, url = location.href) {
    this.url = url;
    // Set data defaults elements and variables
    // Key of this.data need to match key of fetch data json object to update values
    // type<str> : text (target el), list (el need to be first element of list)
    // listNames<arr> : list of names key on item, need to set data-name="nameKey" on el
    this.data = data;
    /* EXAMPLE
      {
        info: {
          el: document.querySelector("[data-info]"),
          value: `Anti-bot technology is designed to detect and mitigate suspicious or
            malicious bots, preventing them from reaching an organization's websites
            or IT ecosystem.`,
          type: "text",
        },

        items: {
          el: document.querySelector("[data-item]"),
          value: [],
          type: "list",
          listNames: ["server_name", "cn", "expire"],
        },
        // value : active / inactive / unknown
        status: {
          el: document.querySelector("[data-status]"),
          value: "unknown",
          type: "status",
          textEl: document.querySelector("[data-status-text]"),
        },
        */
    // Hidden elements that will be shown on success, like ping buttons or list rendering
    this.showOnSuccessEls = document.querySelectorAll(
      "[data-fetch-success-show]",
    );

    this.init();
  }

  init() {
    window.addEventListener("DOMContentLoaded", () => {
      this.createAlertEl();
      // Set default values and fetch
      this.updateDataDOM();
      this.updateAlert("fetch");

      fetch(this.url, {
        method: "POST",
        headers: {
          "X-CSRFToken": document.querySelector('input[name="csrf_token"]')
            .value,
        },
      })
        .then((res) => res.json())
        .then((res) => {
          // Update data and DOM
          this.getFetchDataByKey(res.data);
          this.updateDataDOM();
          // Show hidden elements
          this.showSuccessEls();
          // Feedback
          this.updateAlert("success");
        })
        .catch((error) => {
          this.updateAlert("error");
        });
    });
  }

  createAlertEl() {
    // Container
    this.alertEl = this.createEl(
      "div",
      [
        ["data-fetch", ""],
        ["role", "alert"],
      ],
      "bg-sky-500 p-4 mb-1 md:mb-3 md:mr-3 z-[1001] flex flex-col fixed bottom-0 right-0 w-full md:w-1/2 max-w-[300px] min-h-20 rounded-lg dark:brightness-110 hover:scale-102 transition shadow-md break-words dark:shadow-dark-xl bg-clip-border",
      "",
      "",
    );

    // Status
    this.alertStatusEl = this.createEl(
      "h5",
      [["data-fetch-status", ""]],
      "text-lg mb-0 text-white dark:text-gray-300",
      "Fetching",
      this.alertEl,
    );

    this.alertMsgEl = this.createEl(
      "p",
      [["data-fetch-msg", ""]],
      "text-white dark:text-gray-300 mb-0 text-sm",
      "Please wait...",
      this.alertEl,
    );

    document.body.appendChild(this.alertEl);
  }

  createEl(tag, attArr, className, text, parent) {
    const el = document.createElement(tag);
    attArr.forEach((att) => {
      el.setAttribute(att[0], att[1]);
    });
    if (className) el.className = className;
    if (text) el.textContent = text;
    if (parent) parent.appendChild(el);
    return el;
  }

  showSuccessEls() {
    this.showOnSuccessEls.forEach((el) => {
      el.classList.remove("hidden");
    });
  }

  // Key of fetch data need to match key of this.data
  getFetchDataByKey(fetchDataObj) {
    for (const [key, value] of Object.entries(this.data)) {
      // Case list
      if (Array.isArray(fetchDataObj[key])) {
        value["value"] = fetchDataObj[key] || value["value"] || "";
        continue;
      }
      // Case number
      if (!isNaN(fetchDataObj[key])) {
        value["value"] = fetchDataObj[key] == 0 ? "0" : fetchDataObj[key];
        continue;
      }
      // Others
      value["value"] = fetchDataObj[key] || value["value"] || "";
    }
  }

  updateDataDOM() {
    for (const [key, val] of Object.entries(this.data)) {
      const el = val["el"];
      const type = val["type"];
      const value = val["value"];

      // Case text
      if (type === "text") {
        el.textContent = value || "";
        continue;
      }

      // Case status
      if (type === "status") {
        const textEl = val["textEl"] || null;

        if (
          value === "active" ||
          value === "up" ||
          value === "yes" ||
          value === "success" ||
          value === "true"
        ) {
          this.setStatus(el, textEl, "success", "Active");
          continue;
        }

        if (
          value === "inactive" ||
          value === "down" ||
          value === "no" ||
          value === "error" ||
          value === "false"
        ) {
          this.setStatus(el, textEl, "error", "Inactive");
          continue;
        }

        //default
        this.setStatus(el, textEl, "info", "Unknown");
        continue;
      }

      // Case list, we will render elements after the selected elements
      if (type === "list") {
        // Case no list to render
        if (!value || value.length <= 0) continue;

        // Clone item element
        const itemEl = el.cloneNode(true);
        itemEl.classList.remove("hidden");
        const parentEl = el.parentNode;
        // Add item element after selected element
        const items = value.forEach((item) => {
          const newItemEl = itemEl.cloneNode(true);
          // Update item element values
          for (const [nameKey, nameValue] of Object.entries(item)) {
            newItemEl.querySelector(`[data-name="${nameKey}"]`).textContent =
              nameValue;
          }
          // Add item element after selected element
          parentEl.appendChild(newItemEl);
        });

        // Delete schema
        el.remove();
        continue;
      }
    }
  }

  setStatus(el, textEl, colorClass, text) {
    el.classList.remove("success", "error", "info");
    el ? el.classList.add(colorClass) : null;
    textEl ? (textEl.textContent = text) : null;
  }

  // Show fetch state alert
  // type<str> : fetch, success, error
  updateAlert(type) {
    if (!type) return;

    const [status, msg, color] = this.getAlertType(type);

    this.alertEl.classList.remove("bg-sky-500", "bg-green-500", "bg-red-500");

    this.alertStatusEl.textContent = status;
    this.alertMsgEl.textContent = msg;
    this.alertEl.classList.add(color);

    this.alertEl.classList.remove("hidden");

    if (type !== "fetch")
      setTimeout(() => this.alertEl.classList.add("hidden"), 5000);
  }

  getAlertType(type) {
    if (type === "fetch") return ["Fetching", "Please wait...", "bg-sky-500"];
    if (type === "error")
      return ["Error", "Something went wrong", "bg-red-500"];
    if (type === "success")
      return ["Success", "Data fetched successfully", "bg-green-500"];
  }
}
