$(document).ready(function () {
  // Password validation functions
  function validatePassword() {
    const password = $("#new_password").val();
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
  }

  function validateCondition(condition, selector, currentValidity) {
    if (condition) {
      $(selector)
        .removeClass("bx-x text-danger")
        .addClass("bx-check text-success");
    } else {
      $(selector)
        .removeClass("bx-check text-success")
        .addClass("bx-x text-danger");
      return false;
    }
    return currentValidity;
  }

  function matchPassword() {
    const newPassword = $("#new_password").val();
    const confirmPassword = $("#new_password_confirm").val();
    const match = newPassword === confirmPassword;
    updateValidationState("#new_password_confirm", match);
    return match;
  }

  function updateValidationState(selector, isValid) {
    $(selector)
      .toggleClass("is-valid", isValid)
      .toggleClass("is-invalid", !isValid);
  }

  // Real-time validation as user types
  $("#new_password").on("input", function () {
    const isValid = validatePassword();
    updateValidationState(this, isValid);
  });

  $("#new_password_confirm").on("input", matchPassword);

  // Form submission validation
  $("#formPasswordSettings").on("submit", function (e) {
    const isValidPassword = validatePassword();
    const isMatchingPassword = matchPassword();

    if (!isValidPassword || !isMatchingPassword) {
      e.preventDefault();
    }
  });

  // Tab change handling
  $('button[data-bs-toggle="tab"]').on("shown.bs.tab", function (e) {
    handleTabChange($(e.target).data("bs-target"));
  });

  function handleTabChange(targetClass) {
    const target = targetClass.substring(1).replace("navs-pills-pane-", "");
    const isProfileTab = target === "profile";
    const isSessionsTab = target === "sessions";
    const sessionsPagination = $("#navs-pills-sessions-pagination");

    if (sessionsPagination.length) {
      if (!isSessionsTab) {
        sessionsPagination.removeClass("show active");
        setTimeout(() => {
          sessionsPagination.parent().addClass("d-none");
          $(".nav-pills .tf-icons")
            .parent()
            .find("span")
            .removeClass("d-xxxl-inline")
            .addClass("d-sm-inline");
          $(".nav-pills .tf-icons").closest("div").removeClass("col-md-4");
        }, 200);
      } else {
        sessionsPagination.parent().removeClass("d-none");
        setTimeout(() => {
          sessionsPagination.addClass("show active");
          $(".nav-pills .tf-icons")
            .parent()
            .find("span")
            .removeClass("d-sm-inline")
            .addClass("d-xxxl-inline");
          $(".nav-pills .tf-icons").closest("div").addClass("col-md-4");
        }, 200);
      }
    }

    if (isProfileTab && window.location.hash) {
      history.pushState(
        "",
        document.title,
        window.location.pathname + window.location.search,
      );
    } else {
      window.location.hash = target;
    }
  }

  // On page load, activate the tab based on the URL fragment
  const hash = window.location.hash;
  if (hash) {
    const targetTab = $(
      `button[data-bs-target="#navs-pills-pane-${hash.substring(1)}"]`,
    );
    if (targetTab.length) {
      targetTab.tab("show");
    }
  }

  // Pagination and session content handling
  const totalPages = $(".page-item").length - 2;
  const currentCardClasses = "border-primary border-1 position-relative";
  const currentCardIcon = "bx-star text-warning";
  const currentItemsClasses = "text-primary";
  const otherCardClasses = "border-secondary";
  const otherCardIcon = "bx-history";
  const otherItemsClasses = "text-secondary";

  let clickLock = false;

  $(".page-item").on("click", function () {
    if (clickLock) return;
    clickLock = true;

    const currentPage = parseInt($("#sessions-current-page").text().trim());
    let page = $(this).hasClass("prev")
      ? currentPage - 1
      : $(this).hasClass("next")
        ? currentPage + 1
        : parseInt($(this).text().trim());

    if (page === currentPage || page < 1 || page > totalPages) {
      clickLock = false;
      return;
    }

    updatePagination(page, currentPage);
    setPlaceholders(3);

    setTimeout(() => {
      fadeInPlaceholders();
      setTimeout(() => {
        loadSessionData(page);
      }, 200);
    }, 50);
  });

  function updatePagination(newPage, oldPage) {
    $("#sessions-current-page").text(newPage);
    $(`.page-item[data-page=${oldPage}]`).removeClass("active");
    $(`.page-item[data-page=${newPage}]`).addClass("active");

    $(".page-item.prev").toggleClass("disabled", newPage === 1);
    $(".page-item.next").toggleClass("disabled", newPage === totalPages);
  }

  function setPlaceholders(numPlaceholders) {
    const placeholders = Array.from(
      { length: numPlaceholders },
      (_, i) => `
      <div id="session-placeholder-${i}" class="card border-secondary shadow-sm mb-4 placeholder-transition">
        <div class="card-header d-flex align-items-center justify-content-between placeholder-glow">
          <div class="d-flex align-items-center gap-2 placeholder-glow">
            <span class="placeholder col-2"></span>
            <h5 class="card-title mb-0">Session</h5>
          </div>
          <span class="placeholder col-2"></span>
        </div>
        <div class="card-body">
          <div class="list-group list-group-flush placeholder-glow">
            ${generatePlaceholderItems()}
          </div>
        </div>
      </div>
    `,
    ).join("");

    $("#sessions-page-content").html(placeholders);
  }

  function generatePlaceholderItems() {
    const items = [
      "bx-window-alt",
      "Browser",
      "bx-layer",
      "Operating System",
      "bx-devices",
      "Device",
      "bx-network-chart",
      "IP Address",
      "bx-time",
      "Creation date",
      "bx-time",
      "Last Activity",
    ];

    return items
      .map((icon, i) =>
        i % 2 === 0
          ? `
      <div class="list-group-item d-flex align-items-center">
        <strong><i class="bx ${icon} text-secondary"></i> ${
          items[i + 1]
        }:</strong>
        &nbsp;<span class="placeholder col-4"></span>
      </div>
    `
          : "",
      )
      .join("");
  }

  function fadeInPlaceholders() {
    $(".placeholder-transition").addClass("fade-in");
  }

  function loadSessionData(page) {
    const url = `${window.location.pathname}/sessions?page=${page}`;

    fetch(url)
      .then((response) => {
        // Check if the response is OK (status code 200-299)
        if (!response.ok) {
          throw new Error("Network response was not ok");
        }
        return response.json(); // Parse the JSON data from the response
      })
      .then((data) => {
        updateSessionContent(data); // Update the session content with the data
        removeExtraPlaceholders(data.length); // Remove any extra placeholders
        clickLock = false; // Unlock the clickLock variable
      })
      .catch((error) => {
        handleError(); // Handle any errors that occurred during the fetch
        clickLock = false; // Ensure clickLock is unlocked even in case of error
        console.error("Fetch error:", error); // Log the error to the console
      });
  }

  function updateSessionContent(sessions) {
    sessions.forEach((session, index) => {
      const content = generateSessionContent(session, index);
      const placeholder = $(`#session-placeholder-${index}`);

      const sanitizedText = DOMPurify.sanitize(content);

      placeholder
        .html(sanitizedText)
        .removeClass("placeholder-transition fade-in")
        .addClass("card-transition")
        .toggleClass(currentCardClasses, session.current)
        .toggleClass(otherCardClasses, !session.current);
    });
  }

  // Mirrors components/card.html's header shape (icon + card-title, header_right slot)
  // plus components/badge.html's pill markup for the "Current Session" tag, so paginated
  // (AJAX-loaded) cards stay identical to the {% call card(...) %} block profile.html
  // renders server-side for the first page.
  function generateSessionContent(session, index) {
    const icon = session.current ? currentCardIcon : otherCardIcon;
    const badge = session.current
      ? '<span class="badge rounded-pill bg-label-bw-green d-inline-flex align-items-center fs-6"><i class="bx bx-user-check me-1" aria-hidden="true"></i><span data-i18n="profile.session.current_session">Current Session</span></span>'
      : "";
    return `
      <div class="card-header d-flex align-items-center justify-content-between">
        <div class="d-flex align-items-center gap-2">
          <i class="bx ${icon}" aria-hidden="true"></i>
          <div class="d-flex flex-column">
            <h5 class="card-title mb-0" data-i18n="profile.session.title">Session</h5>
          </div>
        </div>
        ${badge}
      </div>
      <div class="card-body">
        <div class="list-group list-group-flush">
          ${generateSessionItems(session, index)}
        </div>
      </div>
    `;
  }

  // Mirrors components/text-group.html's markup (label above, value below, colored
  // icon) so paginated (AJAX-loaded) cards stay identical to the server-rendered ones.
  function generateTextGroupItem(icon, label, i18nKey, value, itemsClasses) {
    return `
      <div class="list-group-item">
        <div class="d-flex align-items-center gap-2 ${itemsClasses}">
          <i class="bx ${icon}" aria-hidden="true"></i>
          <div>
            <div class="text-muted" data-i18n="${i18nKey}">${label}</div>
            <div class="fw-semibold">${value}</div>
          </div>
        </div>
      </div>
    `;
  }

  // Mirrors components/secret-field.html's masked-value markup (fixed-length mask,
  // reveal/copy buttons) -- static/js/components/secret-field.js is document-delegated
  // and idempotent, so it wires these buttons the same way whether rendered by Jinja
  // on first load or injected here on pagination.
  function generateIpItem(session, index, itemsClasses) {
    const id = `ip-${index}`;
    const mask = "•".repeat(16);
    return `
      <div class="list-group-item d-flex align-items-center gap-2">
        <strong class="d-flex align-items-center gap-1 ${itemsClasses}">
          <i class="bx bx-network-chart" aria-hidden="true"></i>
          <span data-i18n="profile.session.ip_address">IP Address</span>:
        </strong>
        <div class="d-flex align-items-center gap-2">
          <code id="${id}" class="secret-field courier-prime" data-secret="${session.ip}" data-secret-label="Secret value" data-mask-count="16" data-secret-shown="0" aria-label="Secret value (hidden)">${mask}</code>
          <button type="button" class="btn btn-sm btn-outline-secondary p-1 lh-1 secret-toggle" data-secret-toggle="${id}" aria-controls="${id}" aria-pressed="false" aria-label="Reveal value" data-i18n="aria.label.reveal_value">
            <i class="bx bx-show bx-xs" aria-hidden="true"></i>
          </button>
          <button type="button" class="btn btn-sm btn-outline-secondary p-1 lh-1 secret-copy" data-secret-copy="${id}" aria-label="Copy" data-i18n="button.copy">
            <i class="bx bx-copy-alt bx-xs" aria-hidden="true"></i>
          </button>
        </div>
      </div>
    `;
  }

  function generateSessionItems(session, index) {
    const itemsClasses = session.current
      ? currentItemsClasses
      : otherItemsClasses;

    const head = [
      ["bx-window-alt", "Browser", "profile.session.browser", session.browser],
      ["bx-layer", "Operating System", "profile.session.os", session.os],
      ["bx-devices", "Device", "profile.session.device", session.device],
    ]
      .map(([icon, label, i18nKey, value]) =>
        generateTextGroupItem(icon, label, i18nKey, value, itemsClasses),
      )
      .join("");

    const tail = [
      [
        "bx-time",
        "Creation date",
        "profile.session.creation_date",
        session.creation_date,
      ],
      [
        "bx-time",
        "Last Activity",
        "profile.session.last_activity",
        session.last_activity,
      ],
    ]
      .map(([icon, label, i18nKey, value]) =>
        generateTextGroupItem(icon, label, i18nKey, value, itemsClasses),
      )
      .join("");

    return head + generateIpItem(session, index, itemsClasses) + tail;
  }

  function removeExtraPlaceholders(sessionCount) {
    $(`#sessions-page-content .card:gt(${sessionCount - 1})`).remove();
  }

  function handleError() {
    $("#session-page-content").html(
      "<p>Error loading data. Please try again.</p>",
    );
  }

  function initializeAccountImageHandling() {
    const accountUserImage = $("#uploadedAvatar");
    const fileInput = $(".account-file-input");
    const resetFileInput = $(".account-image-reset");

    if (accountUserImage.length === 0) return;

    const originalImageSrc = accountUserImage.attr("src");

    fileInput.on("change", function () {
      const file = this.files[0];
      if (file) {
        accountUserImage.attr("src", URL.createObjectURL(file));
      }
    });

    resetFileInput.on("click", function () {
      fileInput.val("");
      accountUserImage.attr("src", originalImageSrc);
    });
  }

  initializeAccountImageHandling();
});
