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
