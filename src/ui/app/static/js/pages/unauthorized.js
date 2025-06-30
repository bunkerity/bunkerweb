// filepath: /home/bunkerity/dev/bunkerweb-dev/src/ui/app/static/js/pages/unauthorized.js
$(document).ready(function () {
  const $goBackBtn = $("#go-back-btn");

  // Handle go back button click
  $goBackBtn.on("click", function () {
    // Check if there's browser history to go back to
    if (window.history.length > 1) {
      window.history.back();
    } else {
      // Fallback: redirect to home page if no history
      const nextEndpoint = $("#next-endpoint").val();
      if (nextEndpoint) {
        window.location.href = nextEndpoint;
      } else {
        window.location.href = "/";
      }
    }
  });
});
