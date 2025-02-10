$(document).ready(() => {
  // Initialize variables
  let toastNum = 1;
  let currentStep = 1;
  const CHECK_STEP = 3;
  const uiUser = $("#ui_user").val() === "yes";
  const uiReverseProxy = $("#ui_reverse_proxy").val() === "yes";

  // Cache jQuery selectors for performance
  const $window = $(window);
  const $passwordInput = $("#password");
  // const $2faInput = $("#2fa_code");
  const $confirmPasswordInput = $("#confirm_password");
  const $serverNameInput = $("#SERVER_NAME");
  // const $overview2faEnabled = $("#overview-2fa-enabled");
  const $overviewUniqueServerName = $("#overview-unique-server-name");
  const $saveSettingsButton = $(".save-settings");
  const $previousStepButton = $(".previous-step");
  const $nextStepButton = $(".next-step");
  const $breadcrumbItems = $(".template-steps-container .breadcrumb-item");
  const $csrfTokenInput = $("#csrf_token");

  // Utility Functions

  /**
   * Validates a password based on multiple conditions.
   * @returns {boolean} True if the password is valid, else false.
   */
  const validatePassword = () => {
    const password = $passwordInput.val();
    let isValid = true;

    isValid = validateCondition(
      password.length >= 8,
      "#length-check i",
      isValid,
    );
    isValid = validateCondition(
      /[A-Z]/.test(password),
      "#uppercase-check i",
      isValid,
    );
    isValid = validateCondition(
      /\d/.test(password),
      "#number-check i",
      isValid,
    );
    isValid = validateCondition(
      /[^a-zA-Z0-9]/.test(password),
      "#special-check i",
      isValid,
    ); // Check for special characters

    return isValid;
  };

  /**
   * Updates the UI based on a validation condition.
   * @param {boolean} condition - The validation condition.
   * @param {string} selector - The selector for the UI element to update.
   * @param {boolean} currentValidity - The current validity state.
   * @returns {boolean} Updated validity state.
   */
  const validateCondition = (condition, selector, currentValidity) => {
    const $element = $(selector);
    if (condition) {
      $element
        .removeClass("bx-x text-danger")
        .addClass("bx-check text-success");
    } else {
      $element
        .removeClass("bx-check text-success")
        .addClass("bx-x text-danger");
    }
    return currentValidity && condition;
  };

  /**
   * Toggles validation classes based on the validity of an input.
   * @param {string} selector - The selector for the input element.
   * @param {boolean} isValid - The validity state.
   */
  const updateValidationState = (selector, isValid) => {
    $(selector)
      .toggleClass("is-valid", isValid)
      .toggleClass("is-invalid", !isValid);
  };

  /**
   * Extracts and encodes the server name from the input.
   * @returns {string} Encoded server name.
   */
  const getServerName = () => {
    const serverName = $serverNameInput.val().trim().split(" ")[0];
    return encodeURIComponent(serverName); // Encode to prevent injection
  };

  /**
   * Performs a DNS check by fetching the given URL.
   * @param {string} url - The URL to fetch.
   * @returns {Promise<boolean>} True if the check is successful, else false.
   */
  const fetchCheck = async (url) => {
    try {
      const response = await fetch(url, { cache: "no-store" }); // Prevent caching
      const text = (await response.text()).trim().toLowerCase();
      if (response.status === 200 && text === "ok") {
        return true;
      } else if (text === "error") {
        return "Server name check failed";
      }
      return false;
    } catch (error) {
      return error.message;
    }
  };

  /**
   * Handles the DNS checking logic with primary and fallback URLs.
   */
  const checkDNS = async () => {
    $overviewUniqueServerName
      .find("i")
      .toggleClass("bx-check text-success bx-x text-danger", false)
      .toggleClass("bx-question-mark text-warning", true);

    const serverName = getServerName();
    if (!serverName) {
      $checkResultSpan.text("Invalid server name.");
      return;
    }

    const primaryURL = `https://${serverName}/setup/check`;
    const fallbackURL = `${window.location.origin}/setup/check?server_name=${serverName}`;

    let result = await fetchCheck(primaryURL);

    if (!result || typeof result === "string") {
      result = await fetchCheck(fallbackURL);
    }

    const $input = $("#SERVER_NAME");
    const isValid = result && typeof result !== "string";

    // Toggle valid/invalid classes
    $input.toggleClass("is-invalid", !isValid);

    // Manage the invalid-feedback element
    let $feedback = $input.siblings(".invalid-feedback");
    if (!$feedback.length) {
      const $textSpan = $input.parent().find("span.input-group-text");
      $feedback = $('<div class="invalid-feedback"></div>').insertAfter(
        $textSpan.length ? $textSpan : $input,
      );
    }

    const feedbackToast = $("#feedback-toast").clone(); // Clone the feedback toast
    feedbackToast.attr("id", `feedback-toast-${toastNum++}`); // Corrected to set the ID for the toast
    if (!isValid) {
      $feedback.text("Server name is not unique.");
      feedbackToast.addClass("border-danger");
      feedbackToast.find(".toast-header").addClass("text-danger");
      feedbackToast.find("span").text("Server name is not unique.");
      feedbackToast
        .find("div.toast-body")
        .text("Please choose a different server name.");
      if (typeof result !== "string")
        $overviewUniqueServerName
          .find("i")
          .toggleClass(
            "bx-question-mark text-warning bx-check text-success",
            false,
          )
          .toggleClass("bx-x text-danger", true);
    } else {
      $feedback.text("");
      feedbackToast.addClass("border-primary");
      feedbackToast.find(".toast-header").addClass("text-primary");
      feedbackToast.find("span").text("Server name is unique.");
      feedbackToast
        .find("div.toast-body")
        .text("You can proceed with the setup.");
      $overviewUniqueServerName
        .find("i")
        .toggleClass("bx-check text-success", true)
        .toggleClass("bx-question-mark text-warning bx-x text-danger", false);
    }

    feedbackToast.appendTo("#feedback-toast-container"); // Ensure the toast is appended to the container
    feedbackToast.toast("show");

    return result;
  };

  /**
   * Validates all inputs within the current step.
   * @param {jQuery} $currentStepContainer - The container of the current step.
   * @returns {boolean} True if the step is valid, else false.
   */
  const validateCurrentStepInputs = ($currentStepContainer) => {
    let isStepValid = true;

    $currentStepContainer.find(".plugin-setting").each(function () {
      const $input = $(this);
      const value = $input.val();
      const isRequired = $input.prop("required");
      const pattern = $input.attr("pattern");
      const fieldName =
        $input.data("field-name") || $input.attr("name") || "This field";

      let errorMessage = "";
      let isValid = true;

      // Custom error messages
      const requiredMessage =
        $input.data("required-message") || `${fieldName} is required.`;
      const patternMessage =
        $input.data("pattern-message") || `Please enter a valid ${fieldName}.`;

      // Check if the field is required and not empty
      if (isRequired && value === "") {
        errorMessage = requiredMessage;
        isValid = false;
      }

      // Validate based on pattern if the input is not empty
      if (isValid && pattern && value !== "") {
        const regex = new RegExp(pattern);
        if (!regex.test(value)) {
          errorMessage = patternMessage;
          isValid = false;
        }
      }

      // Toggle valid/invalid classes
      $input.toggleClass("is-invalid", !isValid);

      // Manage the invalid-feedback element
      let $feedback = $input.siblings(".invalid-feedback");
      if (!$feedback.length) {
        const $textSpan = $input.parent().find("span.input-group-text");
        $feedback = $('<div class="invalid-feedback"></div>').insertAfter(
          $textSpan.length ? $textSpan : $input,
        );
      }

      if (!isValid) {
        $feedback.text(errorMessage);
        isStepValid = false;
      } else {
        $feedback.text("");
      }
    });

    if (!isStepValid) {
      // Focus the first invalid input
      $currentStepContainer.find(".is-invalid").first().focus();
    }

    return isStepValid;
  };

  /**
   * Navigates to the specified step.
   * @param {number} newStep - The step number to navigate to.
   */
  const navigateToStep = (newStep) => {
    const $newTabTrigger = $(`button[data-bs-target="#navs-steps-${newStep}"]`);

    // Update breadcrumb UI
    $breadcrumbItems.each(function () {
      $(this)
        .find("div.text-primary")
        .removeClass("text-primary")
        .addClass("text-muted");
      $(this).find("button").addClass("disabled");
    });

    // Activate the new tab
    const newTab = new bootstrap.Tab($newTabTrigger[0]);
    newTab.show();

    // Update breadcrumb item
    $newTabTrigger
      .parent()
      .find("div.text-muted")
      .removeClass("text-muted")
      .addClass("text-primary");
    $newTabTrigger.removeClass("disabled");

    // Scroll into view
    $newTabTrigger[0].scrollIntoView({
      behavior: "smooth",
      block: "nearest",
      inline: "center",
    });

    currentStep = newStep;

    // Toggle button states based on the new step
    toggleButtonStates();
  };

  /**
   * Toggles the visibility and state of navigation buttons based on the current step.
   */
  const toggleButtonStates = () => {
    if (currentStep === 1) {
      $previousStepButton.addClass("disabled");
    } else {
      $previousStepButton.removeClass("disabled");
    }

    if (currentStep === 3) {
      $nextStepButton.addClass("d-none");
      $saveSettingsButton.removeClass("d-none");
      populateOverview();
    } else {
      if (
        !uiUser &&
        currentStep === 2 &&
        $("#EMAIL_LETS_ENCRYPT").length &&
        $("#EMAIL_LETS_ENCRYPT").val().trim() === ""
      ) {
        $("#EMAIL_LETS_ENCRYPT").val($("#email").val().trim());
      }
      $nextStepButton.removeClass("d-none");
      $saveSettingsButton.addClass("d-none");
    }
  };

  /**
   * Populates the overview fields with the entered data.
   */
  const populateOverview = () => {
    if (!uiUser) {
      const $overviewEmail = $("#overview_email");
      const $overviewUsername = $("#overview_username");
      const $overviewPassword = $("#overview_password");
      const adminEmail = $("#email").val();

      if (adminEmail) {
        $overviewEmail.val(adminEmail);
        $overviewEmail.parent().removeClass("d-none");
      } else {
        $overviewEmail.parent().addClass("d-none");
      }
      $overviewUsername.val($("#username").val());
      $overviewPassword.val($("#password").val());
    }
    if (!uiReverseProxy) {
      $("#overview_service_url").val(
        `https://${getServerName()}${$("#REVERSE_PROXY_URL").val()}`,
      );
    }
  };

  /**
   * Handles navigation to the next or previous step.
   * @param {boolean} isNext - True if navigating forward, false if backward.
   */
  const handleStepNavigation = async (isNext, force = false) => {
    const newStep = isNext ? currentStep + 1 : currentStep - 1;
    const $currentStepContainer = $(`#navs-steps-${currentStep}`);

    if (!force && isNext) {
      let isStepValid = validateCurrentStepInputs($currentStepContainer);

      // Additional validation for step 1 (password confirmation)
      if (!uiUser && currentStep === 1) {
        const password = $passwordInput.val();
        const confirmPassword = $confirmPasswordInput.val();

        if (password !== confirmPassword) {
          $confirmPasswordInput.addClass("is-invalid");
          let $feedback = $confirmPasswordInput.siblings(".invalid-feedback");
          if (!$feedback.length) {
            const $textSpan = $confirmPasswordInput
              .parent()
              .find("span.input-group-text");
            $feedback = $(
              '<div class="invalid-feedback">Passwords do not match.</div>',
            ).insertAfter($textSpan.length ? $textSpan : $confirmPasswordInput);
          } else {
            $feedback.text("Passwords do not match.");
          }
          isStepValid = false;
        } else {
          $confirmPasswordInput.removeClass("is-invalid");
          $confirmPasswordInput.siblings(".invalid-feedback").text("");
        }
      } else if (!uiReverseProxy && currentStep === 2) {
        const autoLetsEncrypt = $("#AUTO_LETS_ENCRYPT").prop("checked");
        const letsEncryptChallenge = $("#LETS_ENCRYPT_CHALLENGE")
          .find(":selected")
          .val();
        if (autoLetsEncrypt && letsEncryptChallenge === "dns") {
          const $letsEncryptProvider = $("#LETS_ENCRYPT_DNS_PROVIDER");
          if (!$letsEncryptProvider.find(":selected").val()) {
            $letsEncryptProvider.addClass("is-invalid");
            let $feedback = $letsEncryptProvider.siblings(".invalid-feedback");
            if (!$feedback.length) {
              const $textSpan = $letsEncryptProvider
                .parent()
                .find("span.input-group-text");
              $feedback = $(
                '<div class="invalid-feedback">This field is required when using DNS challenge.</div>',
              ).insertAfter(
                $textSpan.length ? $textSpan : $letsEncryptProvider,
              );
            } else {
              $feedback.text(
                "This field is required when using DNS challenge.",
              );
            }
            return;
          }

          const $letsEncryptCredentialItems = $(
            "#LETS_ENCRYPT_DNS_CREDENTIAL_ITEMS",
          );
          if (!$letsEncryptCredentialItems.val()) {
            $letsEncryptCredentialItems.addClass("is-invalid");
            let $feedback =
              $letsEncryptCredentialItems.siblings(".invalid-feedback");
            if (!$feedback.length) {
              const $textSpan = $letsEncryptCredentialItems
                .parent()
                .find("span.input-group-text");
              $feedback = $(
                '<div class="invalid-feedback">This field is required when using DNS challenge.</div>',
              ).insertAfter(
                $textSpan.length ? $textSpan : $letsEncryptCredentialItems,
              );
            } else {
              $feedback.text(
                "This field is required when using DNS challenge.",
              );
            }
            return;
          }
        }

        const $customSslCert = $("#CUSTOM_SSL_CERT");
        const $customSslKey = $("#CUSTOM_SSL_KEY");
        if (
          $("#USE_CUSTOM_SSL").prop("checked") &&
          (!$customSslCert.val() || !$customSslKey.val())
        ) {
          if (!$customSslCert.val()) {
            $customSslCert.addClass("is-invalid");
            let $feedback = $customSslCert.siblings(".invalid-feedback");
            if (!$feedback.length) {
              const $textSpan = $customSslCert
                .parent()
                .find("span.input-group-text");
              $feedback = $(
                '<div class="invalid-feedback">This field is required when using custom SSL.</div>',
              ).insertAfter($textSpan.length ? $textSpan : $customSslCert);
            } else {
              $feedback.text("This field is required when using custom SSL.");
            }
          }
          if (!$customSslKey.val()) {
            $customSslKey.addClass("is-invalid");
            let $feedback = $customSslKey.siblings(".invalid-feedback");
            if (!$feedback.length) {
              const $textSpan = $customSslKey
                .parent()
                .find("span.input-group-text");
              $feedback = $(
                '<div class="invalid-feedback">This field is required when using custom SSL.</div>',
              ).insertAfter($textSpan.length ? $textSpan : $customSslKey);
            } else {
              $feedback.text("This field is required when using custom SSL.");
            }
          }
          return;
        }

        const result = await checkDNS();
        const modal = $("#modal-confirm-dns");
        const $checkUrl = $("#check-url");
        const serverName = getServerName();
        $checkUrl.attr("href", `https://${serverName}/setup/check`);
        isStepValid = false;

        if (typeof result === "string") {
          $("#dns-check-title").text("Error");
          $("#dns-check-result").html(
            `Are you sure you want to proceed to the next step?<br/>Error: ${result}`,
          );
          modal.modal("show");
        } else if (!result) {
          $("#dns-check-title").text("Server name is not unique");
          $("#dns-check-result").html(
            `Are you sure you want to proceed to the next step?<br/>Server name "${serverName}" is not unique.`,
          );
          modal.modal("show");
        } else {
          isStepValid = true;
        }
      }

      if (!isStepValid) return;

      if (currentStep === 1 && isNext) {
        $(".authentication-inner .card-body").removeClass("pb-10");
        $(".join-newsletter").addClass("d-none");
      }

      currentStep = newStep;
      navigateToStep(newStep);
    } else {
      if (currentStep === 2) {
        $(".authentication-inner .card-body").addClass("pb-10");
        $(".join-newsletter").removeClass("d-none");
      }

      currentStep = newStep;
      navigateToStep(newStep);
    }
  };

  // Event Handlers

  // Real-time password validation
  $passwordInput.on(
    "input",
    debounce(function () {
      const isValid = validatePassword();
      updateValidationState(this, isValid);
    }, 100),
  );

  // Real-time validation for other plugin settings
  $(document).on(
    "input",
    ".plugin-setting",
    debounce(function (event) {
      const $this = $(event.target);
      const pattern = $this.attr("pattern");
      const value = $this.val();
      const isValid = pattern ? new RegExp(pattern).test(value) : true;
      $this
        .toggleClass("is-valid", isValid)
        .toggleClass("is-invalid", !isValid);
    }, 100),
  );

  // Remove validation state on focus out
  $(document).on("focusout", ".plugin-setting", function () {
    $(this).removeClass("is-valid");
    $(".invalid-feedback").remove();
  });

  // Save Settings Button Click
  $saveSettingsButton.on("click", function (e) {
    e.preventDefault();
    if (currentStep !== 3) return;
    $("#loadingModal").modal("show");

    // Create a new FormData object
    const formData = new FormData();

    // Append the CSRF token
    formData.append("csrf_token", $csrfTokenInput.val() || "");

    // Append the Theme
    formData.append("theme", $("[name='theme']").val());

    const server_name = getServerName();
    const ui_url = $("#REVERSE_PROXY_URL").val();

    if (!uiUser) {
      formData.append("admin_username", $("#username").val());
      formData.append("admin_email", $("#email").val());
      formData.append("admin_password", $("#password").val());
      formData.append("admin_password_check", $("#confirm_password").val());
      // formData.append("2fa_code", $("#2fa_code").val());
    }

    if (!uiReverseProxy) {
      formData.append("server_name", server_name);
      formData.append("ui_host", $("#REVERSE_PROXY_HOST").val());
      formData.append("ui_url", ui_url);
      formData.append(
        "auto_lets_encrypt",
        $("#AUTO_LETS_ENCRYPT").prop("checked") ? "yes" : "no",
      );
      formData.append(
        "lets_encrypt_staging",
        $("#USE_LETS_ENCRYPT_STAGING").prop("checked") ? "yes" : "no",
      );
      formData.append(
        "lets_encrypt_wildcard",
        $("#USE_LETS_ENCRYPT_WILDCARD").prop("checked") ? "yes" : "no",
      );
      formData.append("email_lets_encrypt", $("#EMAIL_LETS_ENCRYPT").val());
      formData.append(
        "lets_encrypt_challenge",
        $("#LETS_ENCRYPT_CHALLENGE").find(":selected").val(),
      );
      formData.append(
        "lets_encrypt_dns_provider",
        $("#LETS_ENCRYPT_DNS_PROVIDER").find(":selected").val(),
      );
      formData.append(
        "lets_encrypt_dns_propagation",
        $("#LETS_ENCRYPT_DNS_PROPAGATION").val(),
      );
      formData.append(
        "lets_encrypt_dns_credential_items",
        $("#LETS_ENCRYPT_DNS_CREDENTIAL_ITEMS")
          .val()
          .split("\n")
          .map((item) => item.trim())
          .filter((item) => item !== ""),
      );
      formData.append(
        "use_custom_ssl",
        $("#USE_CUSTOM_SSL").prop("checked") ? "yes" : "no",
      );
      formData.append(
        "custom_ssl_cert_priority",
        $("#CUSTOM_SSL_CERT_PRIORITY").find(":selected").val(),
      );
      formData.append("custom_ssl_cert", $("#CUSTOM_SSL_CERT").val());
      formData.append("custom_ssl_key", $("#CUSTOM_SSL_KEY").val());
      formData.append("custom_ssl_cert_data", $("#CUSTOM_SSL_CERT_DATA").val());
      formData.append("custom_ssl_key_data", $("#CUSTOM_SSL_KEY_DATA").val());
    }

    // Remove beforeunload event to prevent prompt on form submission
    $window.off("beforeunload");

    if (!uiReverseProxy) {
      var api = `https://${server_name}`;
      if (!ui_url.startsWith("/")) {
        api = `${api}/`;
      }
      api = `${api}${ui_url}${ui_url !== "/" ? "/" : ""}check`;
      var redirect = `https://${server_name}/setup/loading?target_endpoint=${api}`;
    } else {
      var redirect = window.location.href.replace("setup", "login");
    }

    // Submit the form
    fetch(window.location.href, {
      method: "POST",
      body: formData,
      redirect: "error",
    })
      .then((res) => {
        if (res.status === 200) {
          setTimeout(() => {
            window.location.href = redirect;
          }, 1000);
        }
      })
      .catch((err) => {
        $("#loadingModal").modal("hide");
        setTimeout(() => {
          const feedbackToast = $("#feedback-toast").clone(); // Clone the feedback toast
          feedbackToast.attr("id", `feedback-toast-${toastNum++}`); // Corrected to set the ID for the failed toast
          feedbackToast.addClass("border-danger");
          feedbackToast.find(".toast-header").addClass("text-danger");
          feedbackToast.find("span").text("Error");
          feedbackToast
            .find("div.toast-body")
            .text("Error while setting up web UI. Please try again.");
          feedbackToast.appendTo("#feedback-toast-container"); // Ensure the toast is appended to the container
          feedbackToast.toast("show");
        }, 400);
        setTimeout(() => {
          location.reload();
        }, 2500);
      });
  });

  // Next and Previous Step Buttons Click
  $(document).on("click", ".next-step, .previous-step", function (e) {
    e.preventDefault();

    const isNext = $(this).hasClass("next-step");
    const confirmDNS = this.id === "confirm-dns";
    handleStepNavigation(isNext, confirmDNS);
  });

  $(document).on("keydown", ".plugin-setting", function (e) {
    if (e.key === "Enter" || e.keyCode === 13) {
      if ($("#LETS_ENCRYPT_DNS_CREDENTIAL_ITEMS").is(":focus")) return;
      $("#next-step").trigger("click");
    }
  });

  // $2faInput.on("input", function () {
  //   if (uiUser) return;

  //   const $this = $(this);
  //   const value = $this.val();
  //   const isValid = /^[0-9]{6}$/.test(value);
  //   updateValidationState(this, isValid);

  //   $overview2faEnabled
  //     .find("i")
  //     .toggleClass("bx-x text-danger bx-check text-success", false)
  //     .toggleClass("bx-question-mark text-warning", value === "");
  //   $overview2faEnabled.tooltip("enable");
  //   if (value) {
  //     if (isValid) {
  //       $overview2faEnabled
  //         .find("i")
  //         .toggleClass("bx-x text-danger", false)
  //         .toggleClass("bx-check text-success", true);
  //       $overview2faEnabled.tooltip("disable");
  //     } else {
  //       $overview2faEnabled
  //         .find("i")
  //         .toggleClass("bx-check text-success", false)
  //         .toggleClass("bx-x text-danger", true);
  //     }
  //   }
  // });

  $("#LETS_ENCRYPT_CHALLENGE").on("change", function () {
    const challenge = $(this).find(":selected").val();
    const $wildcardCheckbox = $("#USE_LETS_ENCRYPT_WILDCARD");
    const $dnsProvider = $("#LETS_ENCRYPT_DNS_PROVIDER");
    const $dnsPropagation = $("#LETS_ENCRYPT_DNS_PROPAGATION");
    const $dnsCredentialItems = $("#LETS_ENCRYPT_DNS_CREDENTIAL_ITEMS");

    if (challenge === "http") {
      $wildcardCheckbox.prop("checked", false).prop("disabled", true);
      $wildcardCheckbox
        .closest(".col-4")
        .attr("data-bs-toggle", "tooltip")
        .attr("data-bs-placement", "top")
        .attr(
          "data-bs-original-title",
          "Wildcard certificates are only supported with DNS challenges.",
        )
        .tooltip();

      $dnsProvider.prop("disabled", true);
      $dnsProvider
        .parent()
        .attr("data-bs-toggle", "tooltip")
        .attr("data-bs-placement", "top")
        .attr(
          "data-bs-original-title",
          "DNS provider is only supported with DNS challenges.",
        )
        .tooltip();

      $dnsPropagation.prop("disabled", true);
      $dnsPropagation
        .parent()
        .attr("data-bs-toggle", "tooltip")
        .attr("data-bs-placement", "top")
        .attr(
          "data-bs-original-title",
          "DNS propagation is only supported with DNS challenges.",
        )
        .tooltip();

      $dnsCredentialItems.prop("disabled", true);
      $dnsCredentialItems
        .parent()
        .attr("data-bs-toggle", "tooltip")
        .attr("data-bs-placement", "top")
        .attr(
          "data-bs-original-title",
          "Credentials are only supported with DNS challenges",
        )
        .tooltip();
    } else {
      $wildcardCheckbox.prop("disabled", false);
      $wildcardCheckbox
        .closest(".col-4")
        .attr("data-bs-toggle", null)
        .attr("data-bs-placement", null)
        .attr("data-bs-original-title", null)
        .tooltip("dispose");

      $dnsProvider.prop("disabled", false);
      $dnsProvider
        .parent()
        .attr("data-bs-toggle", null)
        .attr("data-bs-placement", null)
        .attr("data-bs-original-title", null)
        .tooltip("dispose");

      $dnsPropagation.prop("disabled", false);
      $dnsPropagation
        .parent()
        .attr("data-bs-toggle", null)
        .attr("data-bs-placement", null)
        .attr("data-bs-original-title", null)
        .tooltip("dispose");

      $dnsCredentialItems.prop("disabled", false);
      $dnsCredentialItems
        .parent()
        .attr("data-bs-toggle", null)
        .attr("data-bs-placement", null)
        .attr("data-bs-original-title", null)
        .tooltip("dispose");
    }
  });

  $("#USE_CUSTOM_SSL").on("change", function () {
    const isChecked = $(this).prop("checked");
    const $certPriority = $("#CUSTOM_SSL_CERT_PRIORITY");
    const $cert = $("#CUSTOM_SSL_CERT");
    const $key = $("#CUSTOM_SSL_KEY");
    const $certData = $("#CUSTOM_SSL_CERT_DATA");
    const $keyData = $("#CUSTOM_SSL_KEY_DATA");

    $certPriority.prop("disabled", !isChecked);
    $cert.prop("disabled", !isChecked);
    $key.prop("disabled", !isChecked);
    $certData.prop("disabled", !isChecked);
    $keyData.prop("disabled", !isChecked);
  });

  $(document).on("click", ".submit-newsletter", function (e) {
    e.preventDefault();
    const $email = $("#email");
    const emailElement = $email.get(0);
    if (!$email.val() || !emailElement.checkValidity()) {
      const feedbackToast = $("#feedback-toast").clone(); // Clone the feedback toast
      feedbackToast.attr("id", `feedback-toast-${toastNum++}`); // Set the ID for the toast
      feedbackToast.addClass("border-danger");
      feedbackToast.find(".toast-header").addClass("text-danger");
      feedbackToast.find("span").text("Error");
      feedbackToast
        .find("div.toast-body")
        .text(
          "Please enter a valid email address to subscribe to the newsletter.",
        );
      feedbackToast.appendTo("#feedback-toast-container"); // Append the toast to the container
      feedbackToast.toast("show");
      return;
    }

    const $privacyPolicy = $("#setup-private-policy");
    if (!$privacyPolicy.prop("checked")) {
      const feedbackToast = $("#feedback-toast").clone(); // Clone the feedback toast
      feedbackToast.attr("id", `feedback-toast-${toastNum++}`); // Set the ID for the toast
      feedbackToast.addClass("border-danger");
      feedbackToast.find(".toast-header").addClass("text-danger");
      feedbackToast.find("span").text("Error");
      feedbackToast
        .find("div.toast-body")
        .text(
          "Please accept the privacy policy to subscribe to the newsletter.",
        );
      feedbackToast.appendTo("#feedback-toast-container"); // Append the toast to the container
      feedbackToast.toast("show");
      return;
    }

    $("#newsletter-email").val($email.val());
    $("#setup-newsletter-form").submit();
  });

  // Before Unload Event to Warn Users About Unsaved Changes
  $window.on("beforeunload", function (e) {
    const message =
      "Are you sure you want to leave? Changes you made may not be saved.";
    e.returnValue = message; // Standard for most browsers
    return message; // Required for some browsers
  });

  // Initialize the UI based on the initial step
  toggleButtonStates();
});
