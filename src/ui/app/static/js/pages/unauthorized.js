// filepath: /home/bunkerity/dev/bunkerweb-dev/src/ui/app/static/js/pages/unauthorized.js
$(document).ready(function () {
  const $goBackBtn = $("#go-back-btn");

  // Helper to check if endpoint is a safe relative path
  const RELATIVE_PATH_REGEX = /^\/[a-zA-Z0-9\-._\/?&=%#]*$/;
  function isSafeEndpoint(endpoint) {
    if (typeof endpoint !== "string") return false;
    // Only allow relative paths starting with `/` and composed of safe URL characters.
    // This implicitly disallows schemes like `javascript:` or `http://` and
    // blocks characters such as `<` and `>` that could be used for XSS.
    return RELATIVE_PATH_REGEX.test(endpoint);
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
