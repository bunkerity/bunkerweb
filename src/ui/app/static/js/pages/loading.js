$(document).ready(function () {
  // Retrieve targetEndpoint and nextEndpoint from server-side variables safely
  const $targetEndpoint = $("#target-endpoint");
  const targetEndpoint = $targetEndpoint.length
    ? $targetEndpoint.val().trim()
    : null;

  let nextEndpoint = $("#next-endpoint").val().trim();

  // Function to validate and sanitize the URL
  function sanitizeUrl(url) {
    try {
      // Ensure the URL is either relative or shares the same origin
      const validUrl = new URL(url, window.location.origin);
      return validUrl.href;
    } catch (e) {
      console.error("Invalid URL detected:", url);
    }
    return null; // Return null if the URL is invalid
  }

  // Sanitize nextEndpoint
  nextEndpoint = sanitizeUrl(nextEndpoint);
  if (!nextEndpoint) {
    console.error("Invalid or missing nextEndpoint. Redirect aborted.");
    return; // Abort further execution if the endpoint is invalid
  }

  // Start the reloading interval to check every 2 seconds
  var reloadingInterval = setInterval(check_reloading, 2000);
  setTimeout(check_reloading, 500); // Run after a brief delay

  // Function to check if reloading is needed
  function check_reloading() {
    $.ajax({
      url: targetEndpoint
        ? targetEndpoint
        : location.href.replace("/loading", "/check_reloading"),
      method: "GET",
      dataType: "json",
      timeout: 2000, // 2 seconds timeout
      success: function (response) {
        if (
          response &&
          (response.message === "ok" || response.reloading === false)
        ) {
          clearInterval(reloadingInterval);
          const redirectUrl = new URL(nextEndpoint, window.location.origin);
          if (window.location.hash) {
            redirectUrl.hash = window.location.hash;
          }
          window.location.href = redirectUrl.href;
        }
      },
      error: function (jqXHR, textStatus, errorThrown) {
        if (textStatus === "timeout") {
          console.warn("Request timed out.");
        } else if (textStatus === "parsererror") {
          if (
            !$targetEndpoint.length &&
            !window.location.pathname.includes("/setup/loading")
          ) {
            const redirectUrl =
              jqXHR.getResponseHeader("Location") || nextEndpoint;
            const finalUrl = new URL(redirectUrl, window.location.origin);
            if (window.location.hash) {
              finalUrl.hash = window.location.hash;
            }
            window.location.href = finalUrl.href;
          }
        } else {
          console.error(
            "AJAX request failed:",
            jqXHR.status,
            textStatus,
            errorThrown,
          );
        }
      },
    });
  }
});
