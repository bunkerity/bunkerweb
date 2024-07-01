class BackLogin {
  constructor(currEndpoint, backEndpoint) {
    this.init();
    this.currEndpoint = currEndpoint;
    this.backEndpoint = backEndpoint;
  }

  init() {
    window.addEventListener("load", () => {
      document.querySelectorAll("[data-back-login]").forEach((el) => {
        el.setAttribute(
          "href",
          window.location.href.replace(
            `/${this.currEndpoint}`,
            `/${this.backEndpoint}`,
          ),
        );
      });
    });
  }
}

const setBackLogin = new BackLogin("totp", "login");
