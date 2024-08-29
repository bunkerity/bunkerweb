$(document).ready(function () {
  new DataTable("#instances", {
    autoFill: false,
  });

  $("#instance-form").on("submit", function (event) {
    event.preventDefault(); // Prevent the default form submission

    const form = $(this);
    const clickedButton = form.find('button[type="submit"]:focus'); // Find the button that triggered the submit
    const action = clickedButton.data("action"); // Get the action from the button
    const actionSplit = form.attr("action").split("/");
    const instanceHostname = actionSplit[actionSplit.length - 1];

    if (
      action === "delete" &&
      $(`#method-${instanceHostname}`).val() !== "ui"
    ) {
      return;
    } else if ($(`#status-${instanceHostname}`).val() !== "Up") {
      return;
    }

    form.attr("action", `${form.attr("action")}/${action}`);

    // Now, submit the form with the updated action
    form.off("submit").submit();
  });
});
