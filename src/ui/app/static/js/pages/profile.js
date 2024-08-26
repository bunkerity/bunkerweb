$(document).ready(function () {
  function validatePassword() {
    const password = $("#new_password").val();
    let isValid = true;

    // Validate length
    if (password.length >= 8) {
      $("#length-check i")
        .removeClass("bx-x text-danger")
        .addClass("bx-check text-success");
    } else {
      isValid = false;
      $("#length-check i")
        .removeClass("bx-check text-success")
        .addClass("bx-x text-danger");
    }

    // Validate uppercase letter
    if (/[A-Z]/.test(password)) {
      $("#uppercase-check i")
        .removeClass("bx-x text-danger")
        .addClass("bx-check text-success");
    } else {
      isValid = false;
      $("#uppercase-check i")
        .removeClass("bx-check text-success")
        .addClass("bx-x text-danger");
    }

    // Validate number
    if (/\d/.test(password)) {
      $("#number-check i")
        .removeClass("bx-x text-danger")
        .addClass("bx-check text-success");
    } else {
      isValid = false;
      $("#number-check i")
        .removeClass("bx-check text-success")
        .addClass("bx-x text-danger");
    }

    // Validate special character
    if (/[ !"#$%&'()*+,\-./:;<=>?@[\\\]^_`{|}~]/.test(password)) {
      $("#special-check i")
        .removeClass("bx-x text-danger")
        .addClass("bx-check text-success");
    } else {
      isValid = false;
      $("#special-check i")
        .removeClass("bx-check text-success")
        .addClass("bx-x text-danger");
    }

    return isValid;
  }

  // Real-time validation as user types
  $("#new_password").on("input", function () {
    if (validatePassword()) {
      $(this).removeClass("is-invalid");
      $(this).addClass("is-valid");
    }
  });

  function matchPassword() {
    const newPassword = $("#new_password").val();
    const confirmPassword = $("#new_password_confirm").val();

    if (newPassword === confirmPassword) {
      $("#new_password_confirm").removeClass("is-invalid");
      $("#new_password_confirm").addClass("is-valid");
    } else {
      $("#new_password_confirm").removeClass("is-valid");
      $("#new_password_confirm").addClass("is-invalid");
    }
  }

  $("#new_password_confirm").on("input", function () {
    if (matchPassword()) {
      $(this).removeClass("is-invalid");
      $(this).addClass("is-valid");
    }
  });

  // Form submission validation
  $("#formPasswordSettings").on("submit", function (e) {
    const newPasswordInput = $("#new_password");
    const confirmPasswordInput = $("#new_password_confirm");

    let isValid = true;

    // Check if passwords match
    if (newPasswordInput.val() !== confirmPasswordInput.val()) {
      isValid = false;
      confirmPasswordInput.addClass("is-invalid");
    } else {
      confirmPasswordInput.removeClass("is-invalid");
      confirmPasswordInput.addClass("is-valid");
    }

    // Validate password using real-time checks
    if (!validatePassword()) {
      isValid = false;
      newPasswordInput.addClass("is-invalid");
    } else {
      newPasswordInput.removeClass("is-invalid");
      newPasswordInput.addClass("is-valid");
    }

    // Prevent form submission if validation fails
    if (!isValid) {
      e.preventDefault();
    }
  });

  // Listen for tab change
  $('button[data-bs-toggle="tab"]').on("shown.bs.tab", function (e) {
    // Get the target tab's ID (data-bs-target without the '#')
    var target = $(e.target)
      .data("bs-target")
      .substring(1)
      .replace("navs-pills-", "");

    if (target === "profile") {
      if (window.location.hash) {
        history.pushState(
          "",
          document.title,
          window.location.pathname + window.location.search,
        );
      }
      return;
    }

    // Update the URL fragment
    window.location.hash = target;
  });

  // On page load, activate the tab based on the URL fragment
  var hash = window.location.hash;
  if (hash) {
    var targetTab = $(
      `button[data-bs-target="#navs-pills-${hash.substring(1)}"]`,
    );
    if (targetTab.length) {
      targetTab.tab("show");
    }
  }
});
