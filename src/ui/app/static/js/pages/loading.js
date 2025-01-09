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
  check_reloading(); // Run immediately on load

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
          // Clear all intervals and timeout
          clearInterval(reloadingInterval);

          // Redirect to the sanitized nextEndpoint with the current hash if present
          const redirectUrl = new URL(nextEndpoint, window.location.origin);
          if (window.location.hash) {
            redirectUrl.hash = window.location.hash;
          }
          window.location.href = redirectUrl.href; // Use window.location.href for compatibility
        }
      },
      error: function (jqXHR, textStatus, errorThrown) {
        if (textStatus === "timeout") {
          // Handle timeout specifically if needed
          console.warn("Request timed out.");
        } else {
          // Handle other errors
          console.error("AJAX request failed: ", textStatus, errorThrown);
        }
      },
    });
  }
});
