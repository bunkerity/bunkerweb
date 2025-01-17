$(document).ready(function () {
  // Select the Flatpickr input elements
  const $flatpickrDate = $("#flatpickr-date");

  // Initialize Flatpickr with altInput and altFormat
  $flatpickrDate.flatpickr({
    inline: true,
  });
});
