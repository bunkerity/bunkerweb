class Ping {
  constructor(
    url = `${location.origin}${location.pathname}`,
    statusTextEl = null,
    statusColorEl = null,
    key_to_check = "ping",
  ) {
    this.url = url;
    this.statusColorEl = statusColorEl;
    this.statusTextEl = statusTextEl;
    this.key_to_check = key_to_check;
    this.init();
  }

  init() {
      this.createAlertEl();
      this.updateAlert("fetch");

      // Case no status element
      if (!this.statusColorEl || !this.statusTextEl)
        return this.updateAlert("error");

      fetch(this.url, {
        method: "POST",
        headers: {
          "X-CSRFToken": document.querySelector('input[name="csrf_token"]')
            .value,
        },
      })
        .then((res) => res.json())
        .then((res) => {
          // Update data
          this.updateEl(res.data);
        })
        .catch((error) => {
          this.updateAlert("error");
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

  // Key of fetch data need to match key of this.data
  updateEl(data) {
    try {
      const successValues = [
        "success",
        "ok",
        "200",
        "201",
        "202",
        "203",
        "204",
        "205",
        "206",
        "207",
        "208",
        "226",
      ];
      const isSuccess = successValues.includes(
        data[this.key_to_check].toString(),
      );

      if (isSuccess) {
        this.setStatus("success", "Success");
        this.updateAlert("success");
      }

      if (!isSuccess) {
        this.setStatus("error", "Error");
        this.updateAlert("error");
      }
    } catch (e) {
      this.setStatus("error", "Error");
      this.updateAlert("error");
      return;
    }

    // Feedback
    this.updateAlert("success");
  }

  setStatus(colorClass, text) {
    this.statusColorEl.classList.remove("success", "error", "info");
    this.statusColorEl.classList.add(colorClass);
    this.statusTextEl.textContent = text;
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
