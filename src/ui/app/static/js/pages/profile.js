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
      /[ -~]/.test(password),
      "#special-check i",
      isValid,
    );

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
    const target = targetClass.substring(1).replace("navs-pills-", "");
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
      `button[data-bs-target="#navs-pills-${hash.substring(1)}"]`,
    );
    if (targetTab.length) {
      targetTab.tab("show");
    }
  }

  // Pagination and session content handling
  const totalPages = $(".page-item").length - 2;
  const currentCardClasses = "border-primary border-1 position-relative";
  const currentCardHeaderClasses = "bg-primary text-white";
  const currentCardIcon = "bx-star text-warning";
  const currentItemsClasses = "text-primary";
  const otherCardClasses = "border-secondary";
  const otherCardHeaderClasses = "bg-secondary";
  const otherCardIcon = "bx-history text-white";
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
        <div class="card-header bg-secondary d-flex justify-content-between align-items-center mb-2 p-3 placeholder-glow">
          <div class="d-flex align-items-center placeholder-glow">
            <span class="placeholder col-2"></span>
            <h5 class="mb-0 text-white ms-2">Session</h5>
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

      placeholder
        .html(content)
        .removeClass("placeholder-transition fade-in")
        .addClass("card-transition")
        .toggleClass(currentCardClasses, session.current)
        .toggleClass(otherCardClasses, !session.current);
    });
  }

  function generateSessionContent(session, index) {
    const items = [
      ["bx-window-alt", "Browser", session.browser],
      ["bx-layer", "Operating System", session.os],
      ["bx-devices", "Device", session.device],
      [
        "bx-network-chart",
        "IP Address",
        `<input id="ip-${index}" class="form-control" type="password" autocomplete="off" value="${session.ip}" readonly />`,
      ],
      ["bx-time", "Creation date", session.creation_date],
      ["bx-time", "Last Activity", session.last_activity],
    ];

    return `
      <div class="card-header ${
        session.current ? currentCardHeaderClasses : otherCardHeaderClasses
      }
        d-flex justify-content-between align-items-center mb-2 p-3">
        <div class="d-flex align-items-center">
          <i class="bx ${
            session.current ? currentCardIcon : otherCardIcon
          }"></i>
          <h5 class="mb-0 text-white ms-2">Session</h5>
        </div>
        ${
          session.current
            ? '<span class="badge bg-bw-green text-white fs-6"><i class="bx bx-user-check"></i> Current Session</span>'
            : ""
        }
      </div>
      <div class="card-body">
        <div class="list-group list-group-flush">
          ${generateSessionItems(items, session)}
        </div>
      </div>
    `;
  }

  function generateSessionItems(items, session) {
    return items
      .map(
        ([icon, label, value]) => `
      <div class="list-group-item d-flex align-items-center">
        <strong><i class="bx ${icon} ${
          session.current ? currentItemsClasses : otherItemsClasses
        }"></i> ${label}:</strong>
        &nbsp;${value}
      </div>
    `,
      )
      .join("");
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
