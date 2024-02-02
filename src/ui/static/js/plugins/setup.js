class SetupPlugin {
  constructor(data) {
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

      fetch(location.href, {
        method: "POST",
        headers: {
          "X-CSRFToken": "{{ csrf_token() }}",
        },
      })
        .then((res) => res.json())
        .then((res) => {
          // Update data and DOM
          this.getFetchDataByKey(res.data.data);
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
      "bg-sky-500 p-4 mb-1 md:mb-3 md:mr-3 z-[1001] flex flex-col fixed bottom-0 right-0 w-full md:w-1/2 max-w-[300px] min-h-20 rounded-lg dark:brightness-110 hover:scale-102 transition shadow-md break-words dark:bg-slate-850 dark:shadow-dark-xl bg-clip-border",
      "",
      "",
    );

    this.alertCloseEl = this.createEl(
      "button",
      [["data-fetch-close", ""]],
      "absolute right-7 top-1.5",
      "",
      this.alertEl,
    );

    this.alertCloseIconEl = this.createEl(
      "svg",
      [
        ["xmlns", "http://www.w3.org/2000/svg"],
        ["viewBox", "0 0 320 512"],
      ],
      "cursor-pointer fill-white dark:fill-gray-300 dark:opacity-80 absolute h-5 w-5",
      "",
      this.alertCloseEl,
    );

    // Close icon paths
    const paths = [
      "M11.7 2.805a.75.75 0 0 1 .6 0A60.65 60.65 0 0 1 22.83 8.72a.75.75 0 0 1-.231 1.337 49.948 49.948 0 0 0-9.902 3.912l-.003.002c-.114.06-.227.119-.34.18a.75.75 0 0 1-.707 0A50.88 50.88 0 0 0 7.5 12.173v-.224c0-.131.067-.248.172-.311a54.615 54.615 0 0 1 4.653-2.52.75.75 0 0 0-.65-1.352 56.123 56.123 0 0 0-4.78 2.589 1.858 1.858 0 0 0-.859 1.228 49.803 49.803 0 0 0-4.634-1.527.75.75 0 0 1-.231-1.337A60.653 60.653 0 0 1 11.7 2.805Z",
      ,
      "M13.06 15.473a48.45 48.45 0 0 1 7.666-3.282c.134 1.414.22 2.843.255 4.284a.75.75 0 0 1-.46.711 47.87 47.87 0 0 0-8.105 4.342.75.75 0 0 1-.832 0 47.87 47.87 0 0 0-8.104-4.342.75.75 0 0 1-.461-.71c.035-1.442.121-2.87.255-4.286.921.304 1.83.634 2.726.99v1.27a1.5 1.5 0 0 0-.14 2.508c-.09.38-.222.753-.397 1.11.452.213.901.434 1.346.66a6.727 6.727 0 0 0 .551-1.607 1.5 1.5 0 0 0 .14-2.67v-.645a48.549 48.549 0 0 1 3.44 1.667 2.25 2.25 0 0 0 2.12 0Z",
      ,
      "M4.462 19.462c.42-.419.753-.89 1-1.395.453.214.902.435 1.347.662a6.742 6.742 0 0 1-1.286 1.794.75.75 0 0 1-1.06-1.06Z",
    ];
    paths.forEach((path) => {
      this.createEl("path", [["d", path]], "", "", this.alertCloseIconEl);
    });
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

    this.alertCloseEl.addEventListener("click", () => {
      this.alertEl.classList.add("hidden");
    });
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

        if (value === "active")
          this.setStatus(el, textEl, "fill-green-500", "Active");
        if (value === "inactive")
          this.setStatus(el, textEl, "fill-red-500", "Inactive");
        if (value === "unknown")
          this.setStatus(el, textEl, "fill-sky-500", "Unknown");
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
    el.classList.remove("fill-green-500", "fill-red-500", "fill-sky-500");
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
