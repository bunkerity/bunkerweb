$(document).ready(() => {
  // Initialize variables
  let toastNum = 1;
  let currentStep = 1;
  const CHECK_STEP = 4;
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

    if (currentStep === 4) {
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

        const $subscribeNewsletter = $("#setup-subscribe-newsletter");
        const $email = $("#email");
        if (
          $subscribeNewsletter.prop("checked") &&
          (!$email.val() || !$email.get(0).checkValidity())
        ) {
          $("#email").addClass("is-invalid");
          let $feedback = $("#email").siblings(".invalid-feedback");
          if (!$feedback.length) {
            const $textSpan = $("#email")
              .parent()
              .find("span.input-group-text");
            $feedback = $(
              '<div class="invalid-feedback">This field is required if you want to subscribe to the newsletter.</div>',
            ).insertAfter($textSpan.length ? $textSpan : $("#email"));
          } else {
            $feedback.text(
              "This field is required if you want to subscribe to the newsletter.",
            );
          }
          isStepValid = false;
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

      currentStep = newStep;
      navigateToStep(newStep);
    } else {
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
    if (currentStep !== 4) return;
    const $subscribeNewsletter = $("#setup-subscribe-newsletter");
    if ($subscribeNewsletter.prop("checked")) {
      const $email = $("#email");

      if (!$email.length || !$email.val() || !$email.get(0).checkValidity()) {
        // Show toast notification instead of validation error
        const feedbackToast = $("#feedback-toast").clone();
        feedbackToast.attr("id", `feedback-toast-${toastNum++}`);
        feedbackToast.addClass("border-warning");
        feedbackToast.find(".toast-header").addClass("text-warning");
        feedbackToast.find("span").text("Newsletter Subscription");
        feedbackToast
          .find("div.toast-body")
          .text(
            "Please enter a valid email address to subscribe to the newsletter.",
          );
        feedbackToast.appendTo("#feedback-toast-container");
        feedbackToast.toast("show");
        return;
      }

      $("#newsletter-email").val($email.val());
      $("#setup-newsletter-form").submit();
    }

    $("#loadingModal").modal("show");

    // Create a new FormData object
    const formData = new FormData();

    // Append the CSRF token
    formData.append("csrf_token", $csrfTokenInput.val() || "");

    // Append the Theme
    formData.append("theme", $("[name='theme']").val());

    // Append the PRO License Key
    formData.append("PRO_LICENSE_KEY", $("#PRO_LICENSE_KEY").val());

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
        "lets_encrypt_profile",
        $("#LETS_ENCRYPT_PROFILE").find(":selected").val(),
      );
      formData.append(
        "lets_encrypt_custom_profile",
        $("#LETS_ENCRYPT_CUSTOM_PROFILE").val(),
      );
      formData.append(
        "lets_encrypt_disable_public_suffixes",
        $("#LETS_ENCRYPT_DISABLE_PUBLIC_SUFFIXES").prop("checked")
          ? "yes"
          : "no",
      );
      formData.append(
        "lets_encrypt_dns_provider",
        $("#LETS_ENCRYPT_DNS_PROVIDER").find(":selected").val(),
      );
      formData.append(
        "lets_encrypt_dns_propagation",
        $("#LETS_ENCRYPT_DNS_PROPAGATION").val(),
      );

      // Fix: Process credentials items as separate entries
      const credentialItems = $("#LETS_ENCRYPT_DNS_CREDENTIAL_ITEMS")
        .val()
        .split(/\r?\n/)
        .map((item) => item.trim())
        .filter((item) => item !== "");

      credentialItems.forEach((item) => {
        formData.append("lets_encrypt_dns_credential_items", item);
      });

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
    const $wildcardCol = $wildcardCheckbox.closest(".col-4");
    const $dnsProvider = $("#LETS_ENCRYPT_DNS_PROVIDER");
    const $dnsProviderParent = $dnsProvider.parent();
    const $dnsPropagation = $("#LETS_ENCRYPT_DNS_PROPAGATION");
    const $dnsPropagationParent = $dnsPropagation.parent();
    const $dnsCredentialItems = $("#LETS_ENCRYPT_DNS_CREDENTIAL_ITEMS");
    const $dnsCredentialItemsParent = $dnsCredentialItems.parent();

    // Store original tooltip/i18n attributes if not already stored
    if (!$wildcardCol.data("orig-title")) {
      $wildcardCol.data(
        "orig-title",
        $wildcardCol.attr("data-bs-original-title") || "",
      );
      $wildcardCol.data("orig-i18n", $wildcardCol.attr("data-i18n") || "");
    }
    if (!$dnsProviderParent.data("orig-title")) {
      $dnsProviderParent.data(
        "orig-title",
        $dnsProviderParent.attr("data-bs-original-title") || "",
      );
      $dnsProviderParent.data(
        "orig-i18n",
        $dnsProviderParent.attr("data-i18n") || "",
      );
    }
    if (!$dnsPropagationParent.data("orig-title")) {
      $dnsPropagationParent.data(
        "orig-title",
        $dnsPropagationParent.attr("data-bs-original-title") || "",
      );
      $dnsPropagationParent.data(
        "orig-i18n",
        $dnsPropagationParent.attr("data-i18n") || "",
      );
    }
    if (!$dnsCredentialItemsParent.data("orig-title")) {
      $dnsCredentialItemsParent.data(
        "orig-title",
        $dnsCredentialItemsParent.attr("data-bs-original-title") || "",
      );
      $dnsCredentialItemsParent.data(
        "orig-i18n",
        $dnsCredentialItemsParent.attr("data-i18n") || "",
      );
    }

    if (challenge === "http") {
      $wildcardCheckbox.prop("checked", false).prop("disabled", true);
      $wildcardCol
        .attr("data-bs-toggle", "tooltip")
        .attr("data-bs-placement", "top")
        .attr(
          "data-bs-original-title",
          "Wildcard certificates are only supported with DNS challenges.",
        )
        .attr("data-i18n", "tooltip.wildcard_dns_only")
        .tooltip("dispose")
        .tooltip();

      $dnsProvider.prop("disabled", true);
      $dnsProviderParent
        .attr("data-bs-toggle", "tooltip")
        .attr("data-bs-placement", "top")
        .attr(
          "data-bs-original-title",
          "DNS provider is only supported with DNS challenges.",
        )
        .attr("data-i18n", "tooltip.dns_provider_dns_only")
        .tooltip("dispose")
        .tooltip();

      $dnsPropagation.prop("disabled", true);
      $dnsPropagationParent
        .attr("data-bs-toggle", "tooltip")
        .attr("data-bs-placement", "top")
        .attr(
          "data-bs-original-title",
          "DNS propagation is only supported with DNS challenges.",
        )
        .attr("data-i18n", "tooltip.dns_propagation_dns_only")
        .tooltip("dispose")
        .tooltip();

      $dnsCredentialItems.prop("disabled", true);
      $dnsCredentialItemsParent
        .attr("data-bs-toggle", "tooltip")
        .attr("data-bs-placement", "top")
        .attr(
          "data-bs-original-title",
          "Credentials are only supported with DNS challenges.",
        )
        .attr("data-i18n", "tooltip.dns_credentials_dns_only")
        .tooltip("dispose")
        .tooltip();
    } else {
      $wildcardCheckbox.prop("disabled", false);
      $wildcardCol
        .attr("data-bs-toggle", null)
        .attr("data-bs-placement", null)
        .attr("data-bs-original-title", $wildcardCol.data("orig-title"))
        .attr("data-i18n", $wildcardCol.data("orig-i18n"));
      $wildcardCol.tooltip("dispose");

      $dnsProvider.prop("disabled", false);
      $dnsProviderParent
        .attr("data-bs-toggle", null)
        .attr("data-bs-placement", null)
        .attr("data-bs-original-title", $dnsProviderParent.data("orig-title"))
        .attr("data-i18n", $dnsProviderParent.data("orig-i18n"));
      $dnsProviderParent.tooltip("dispose");

      $dnsPropagation.prop("disabled", false);
      $dnsPropagationParent
        .attr("data-bs-toggle", null)
        .attr("data-bs-placement", null)
        .attr(
          "data-bs-original-title",
          $dnsPropagationParent.data("orig-title"),
        )
        .attr("data-i18n", $dnsPropagationParent.data("orig-i18n"));
      $dnsPropagationParent.tooltip("dispose");

      $dnsCredentialItems.prop("disabled", false);
      $dnsCredentialItemsParent
        .attr("data-bs-toggle", null)
        .attr("data-bs-placement", null)
        .attr(
          "data-bs-original-title",
          $dnsCredentialItemsParent.data("orig-title"),
        )
        .attr("data-i18n", $dnsCredentialItemsParent.data("orig-i18n"));
      $dnsCredentialItemsParent.tooltip("dispose");
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

  // Fixed: Modify the newsletter form click handler to prevent interference with checkbox
  $("#setup-newsletter-form").on("click", function (e) {
    // Don't handle clicks on the checkbox itself or its label
    if (
      $(e.target).is(
        '#setup-subscribe-newsletter, label[for="privacyPolicyCheck"]',
      )
    ) {
      return true;
    }
    e.preventDefault();
    const $checkbox = $("#setup-subscribe-newsletter");
    $checkbox.prop("checked", !$checkbox.prop("checked"));
    $checkbox.trigger("change");
  });

  $("#setup-subscribe-newsletter").on("change", function () {
    $("#email-optional").toggleClass("d-none", this.checked);
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
