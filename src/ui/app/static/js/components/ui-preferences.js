/* Per-user comfort preferences (#3820): dismiss a repeating notice, hide a Home card,
 * restore every hidden card.
 *
 * One delegated listener on `document`, so it also catches controls injected after load --
 * the MFA reminder is a toast built by the flash machinery, not server-rendered markup.
 * Every action reloads the page: the preferences are read server-side (session-cached in
 * main.py's before_request) and the affected blocks are rendered conditionally, so a reload
 * is what makes the change visible, and it is also what proves it persisted.
 */
(function () {
  // The app is not necessarily mounted at the domain root: the documented production
  // topology puts the UI on a subpath behind BunkerWeb (REVERSE_PROXY_URL +
  // X-Forwarded-Prefix -> SCRIPT_NAME). A root-absolute "/preferences/..." would leave the
  // app there and 404 in a way this file used to swallow whole. base.html stamps the mount
  // point on <body>; empty string at the root, so the URLs are unchanged in that case.
  const appRoot = document.body?.getAttribute("data-app-root") || "";

  function post(path, payload, done) {
    fetch(`${appRoot}${path}`, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRFToken": document.getElementById("csrf_token")?.value || "",
      },
      body: JSON.stringify(payload),
    })
      .then((response) => {
        if (!response.ok) {
          // Say so. The previous silence is how a whole feature can be dead in a supported
          // deployment while every page still looks fine.
          console.warn(
            `Preference update ${appRoot}${path} failed: ${response.status}`,
          );
          return null;
        }
        return response.json();
      })
      .then((data) => {
        // `saved: false` is the read-only database saying so out loud; reloading would just
        // put the notice straight back, which is honest but looks like the click did nothing.
        // Say why in the console, like the other two failure branches -- a dead click with no
        // trace anywhere is the shape of bug this file already shipped once.
        if (!data) return;
        if (data.status === "success" && !data.saved) {
          console.warn(`Preference not saved: ${data.message}`);
          return;
        }
        if (data.status === "success" && data.saved) done();
      })
      .catch((error) => {
        console.warn(`Preference update ${appRoot}${path} failed:`, error);
      });
  }

  document.addEventListener("click", (event) => {
    const notice = event.target.closest("[data-dismiss-notice]");
    if (notice) {
      event.preventDefault();
      post(
        "/preferences/notice",
        { notice: notice.getAttribute("data-dismiss-notice") },
        () => window.location.reload(),
      );
      return;
    }

    const hide = event.target.closest("[data-hide-card]");
    if (hide) {
      event.preventDefault();
      post(
        "/preferences/home-cards",
        { card: hide.getAttribute("data-hide-card"), hidden: true },
        () => window.location.reload(),
      );
      return;
    }

    const restore = event.target.closest("[data-restore-cards]");
    if (restore) {
      event.preventDefault();
      post("/preferences/home-cards", { restore: true }, () =>
        window.location.reload(),
      );
    }
  });
})();

/* Look preferences: contrast and density.
 *
 * Per-browser, localStorage only (no server round trip, no DB column). base.html applies the
 * stored value to <html> before the stylesheets load, so the first paint is already right;
 * this file wires the two topbar toggles and keeps the attribute, the stored value and the
 * button state in step. Defaults: high contrast, compact density.
 *
 *   data-contrast = "high" | "standard"      key: bw-contrast
 *   data-density  = "compact" | "comfortable"  key: bw-density
 */
(function () {
  const PREFS = {
    contrast: { key: "bw-contrast", on: "high", off: "standard" },
    density: { key: "bw-density", on: "compact", off: "comfortable" },
  };

  function read(name) {
    const pref = PREFS[name];
    const value = document.documentElement.getAttribute(`data-${name}`);
    return value === pref.off ? pref.off : pref.on;
  }

  function reflect(name) {
    const isOn = read(name) === PREFS[name].on;
    document.querySelectorAll(`[data-bw-pref="${name}"]`).forEach((button) => {
      button.setAttribute("aria-pressed", String(isOn));
      button.classList.toggle("is-on", isOn);
      if (name === "density") {
        const icon = button.querySelector(".bx");
        if (icon) {
          icon.classList.toggle("bx-collapse-vertical", isOn);
          icon.classList.toggle("bx-expand-vertical", !isOn);
        }
      }
    });
  }

  function set(name, value) {
    const pref = PREFS[name];
    document.documentElement.setAttribute(`data-${name}`, value);
    try {
      localStorage.setItem(pref.key, value);
    } catch (e) {
      // Storage unavailable (private mode): the choice holds for this page only.
    }
    reflect(name);
    // Charts and editors that read computed colours can listen for this.
    document.dispatchEvent(
      new CustomEvent("bw:ui-preference", { detail: { name, value } }),
    );
  }

  window.bwUiPreferences = {
    get: read,
    set,
    toggle: (name) =>
      set(
        name,
        read(name) === PREFS[name].on ? PREFS[name].off : PREFS[name].on,
      ),
  };

  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-bw-pref]");
    if (!button) return;
    const name = button.getAttribute("data-bw-pref");
    if (PREFS[name]) window.bwUiPreferences.toggle(name);
  });

  Object.keys(PREFS).forEach(reflect);
})();
