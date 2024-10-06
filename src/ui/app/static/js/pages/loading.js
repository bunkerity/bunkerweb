$(document).ready(function () {
  // Retrieve targetEndpoint and nextEndpoint from server-side variables safely
  const $targetEndpoint = $("#target-endpoint");
  const targetEndpoint = $targetEndpoint.length
    ? $targetEndpoint.val().trim()
    : null;

  const nextEndpoint = $("#next-endpoint").val().trim();

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

          // Redirect to the next page with the current hash if present
          window.location.replace(nextEndpoint + (window.location.hash || ""));
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
