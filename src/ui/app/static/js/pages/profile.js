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
    // The pager lives inside the sessions card: shown with that tab only
    const sessionsPagination = $("#navs-pills-sessions-pagination");
    sessionsPagination.parent().toggleClass("d-none", !isSessionsTab);

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

  // Pagination and session content handling: the sessions table is swapped row by row,
  // 3 sessions per page, from the JSON `/profile/sessions?page=N` already serves.
  const totalPages = $(".page-item").length - 2;

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
    const cells = '<td><span class="placeholder col-8"></span></td>'.repeat(6);
    const rows = Array.from(
      { length: numPlaceholders },
      (_, i) =>
        `<tr id="session-placeholder-${i}" class="placeholder-glow placeholder-transition">${cells}</tr>`,
    ).join("");

    $("#sessions-page-content").html(rows);
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
        updateSessionContent(data); // Update the session rows with the data
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
      $(`#session-placeholder-${index}`)
        .empty()
        .append(generateSessionCells(session, index))
        .removeClass("placeholder-transition fade-in placeholder-glow")
        .addClass("card-transition")
        .toggleClass("session-current", !!session.current);
    });
  }

  // Mirrors the server-rendered row in profile.html. Values go in through `.text()` and
  // `.attr()`, never as markup, so a hostile User-Agent string stays inert.
  function generateSessionCells(session, index) {
    const $browser = $("<td>").append(
      $('<span class="fw-semibold">').text(session.browser),
    );
    if (session.current) {
      $browser.append(
        $(
          '<span class="badge rounded-pill bg-label-bw-green d-inline-flex align-items-center ms-2"><i class="bx bx-user-check me-1" aria-hidden="true"></i></span>',
        ).append(
          $("<span>").text(
            t("profile.session.current_session", "Current Session"),
          ),
        ),
      );
    }
    return [
      $browser,
      $("<td>").text(session.os),
      $("<td>").text(session.device),
      $('<td class="cell-ip">').append(generateIpItem(session, index)),
      $("<td>").text(session.creation_date),
      $("<td>").text(session.last_activity),
    ];
  }

  // Mirrors components/secret-field.html's masked-value markup (fixed-length mask,
  // reveal/copy buttons) -- static/js/components/secret-field.js is document-delegated
  // and idempotent, so it wires these buttons the same way whether rendered by Jinja
  // on first load or injected here on pagination.
  function generateIpItem(session, index) {
    const id = `ip-${index}`;
    const $code = $(
      '<code class="secret-field courier-prime" data-secret-shown="0" data-mask-count="16"></code>',
    )
      .attr("id", id)
      .attr("data-secret", session.ip)
      .attr("data-secret-label", t("aria.label.secret_value", "Secret value"))
      .attr(
        "aria-label",
        t("aria.label.value_hidden", "{{name}} (hidden)", {
          name: t("aria.label.secret_value", "Secret value"),
        }),
      )
      .text("\u2022".repeat(16));
    const $reveal = $(
      '<button type="button" class="btn btn-sm btn-outline-secondary p-1 lh-1 secret-toggle" aria-pressed="false"><i class="bx bx-show bx-xs" aria-hidden="true"></i></button>',
    )
      .attr("data-secret-toggle", id)
      .attr("aria-controls", id)
      .attr("aria-label", t("aria.label.reveal_value", "Reveal value"));
    const $copy = $(
      '<button type="button" class="btn btn-sm btn-outline-secondary p-1 lh-1 secret-copy"><i class="bx bx-copy-alt bx-xs" aria-hidden="true"></i></button>',
    )
      .attr("data-secret-copy", id)
      .attr("aria-label", t("button.copy", "Copy"));
    return $('<div class="d-flex align-items-center gap-2">').append(
      $code,
      $reveal,
      $copy,
    );
  }

  function removeExtraPlaceholders(sessionCount) {
    $(`#sessions-page-content tr:gt(${sessionCount - 1})`).remove();
  }

  function handleError() {
    $("#sessions-page-content").html(
      $("<tr>").append(
        $('<td colspan="6" class="text-center text-muted">').text(
          t(
            "profile.session.load_error",
            "Error loading data. Please try again.",
          ),
        ),
      ),
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
