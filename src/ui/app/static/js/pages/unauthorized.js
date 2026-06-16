// filepath: /home/bunkerity/dev/bunkerweb-dev/src/ui/app/static/js/pages/unauthorized.js
$(document).ready(function () {
  const $goBackBtn = $("#go-back-btn");

  // Helper to check if endpoint is a safe SAME-ORIGIN relative path
  const RELATIVE_PATH_REGEX = /^\/[a-zA-Z0-9\-._\/?&=%#]*$/;
  function isSafeEndpoint(endpoint) {
    if (typeof endpoint !== "string") return false;
    // Reject protocol-relative ("//host", "/\\host" -- browsers fold "\\" to "/"),
    // schemes, backslashes, and ".." segments (which normalize to a protocol-relative
    // path in the URL parser and escape the origin). The regex alone is insufficient:
    // it permits a second leading slash, so "//evil.com" would pass.
    if (
      !endpoint.startsWith("/") ||
      endpoint[1] === "/" ||
      endpoint[1] === "\\"
    )
      return false;
    if (endpoint.includes("\\") || endpoint.includes("://")) return false;
    if (endpoint.split("/").includes("..")) return false;
    if (!RELATIVE_PATH_REGEX.test(endpoint)) return false;
    try {
      const u = new URL(endpoint, window.location.origin);
      return (
        u.origin === window.location.origin && !u.pathname.startsWith("//")
      );
    } catch (e) {
      return false;
    }
  }

  // Handle go back button click
  $goBackBtn.on("click", function () {
    // Check if there's browser history to go back to
    if (window.history.length > 1) {
      window.history.back();
    } else {
      // Fallback: redirect to home page if no history
      const nextEndpoint = $("#next-endpoint").val();
      if (nextEndpoint && isSafeEndpoint(nextEndpoint)) {
        window.location.href = nextEndpoint;
      } else {
        window.location.href = "/";
      }
    }
  });
});
