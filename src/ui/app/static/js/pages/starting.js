$(document).ready(() => {
  const $uiErrorMessage = $("#ui-error-message");

  if (!$uiErrorMessage.length) {
    // Automatically refresh the page after 3 seconds
    setTimeout(() => {
      window.location.reload();
    }, 3000);
  }
});
