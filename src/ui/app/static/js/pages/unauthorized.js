// filepath: /home/bunkerity/dev/bunkerweb-dev/src/ui/app/static/js/pages/unauthorized.js
$(document).ready(function () {
  const $goBackBtn = $("#go-back-btn");

  // Helper to check if endpoint is a safe relative path
  function isSafeEndpoint(endpoint) {
    if (typeof endpoint !== "string") return false;
    // Only allow relative paths starting with /
    // Disallow `:` or `//` to prevent scheme/protocol and protocol-relative URLs
    return endpoint.startsWith("/") &&
           !endpoint.includes("://") &&
           !endpoint.trim().toLowerCase().startsWith("javascript:") &&
           !endpoint.includes("<") &&
           !endpoint.includes(">");
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
