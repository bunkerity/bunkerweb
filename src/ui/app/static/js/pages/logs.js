$(document).ready(function () {
  // Ensure i18next is loaded before using it
  const t =
    typeof i18next !== "undefined"
      ? i18next.t
      : (key, fallback, options) => {
          // Basic fallback supporting simple interpolation
          let translated = fallback || key;
          if (options) {
            for (const optKey in options) {
              translated = translated.replace(`{{${optKey}}}`, options[optKey]);
            }
          }
          return translated;
        };

  const editorElement = $("#raw-logs");
  const initialContent = editorElement.text().trim();
  const editor = ace.edit(editorElement[0]);
  var theme = $("#theme").val();
  let eventSource = null;
  let isFollowing = false;

  // Get current file from URL parameters
  const urlParams = new URLSearchParams(window.location.search);
  const currentFile = urlParams.get("file");

  // Constants for log management
  const MAX_LOG_LINES = 5000;

  // Function to trim log content when it gets too long
  function trimLogContent() {
    const content = editor.getValue();
    const lines = content.split("\n");

    if (lines.length > MAX_LOG_LINES) {
      const trimmedCount = lines.length - MAX_LOG_LINES;
      const trimmedLines = lines.slice(-MAX_LOG_LINES);
      const notice = t(
        "logs.trimmed_notice",
        "--- {{count}} older log lines were removed for performance ---",
        { count: trimmedCount },
      );
      const newContent = notice + "\n" + trimmedLines.join("\n");
      editor.setValue(newContent, -1);
    }
  }

  function setEditorTheme() {
    if (theme === "dark") {
      editor.setTheme("ace/theme/cloud9_night");
    } else {
      editor.setTheme("ace/theme/cloud9_day");
    }
  }

  setEditorTheme();
  editor.session.setMode("ace/mode/text");
  editor.setReadOnly(true); // Set the editor's initial content
  editor.setValue(initialContent, -1); // The second parameter moves the cursor to the start

  editor.setOptions({
    fontSize: "14px",
    showPrintMargin: false,
    tabSize: 2,
    useSoftTabs: true,
    wrap: true,
  });

  editor.renderer.setScrollMargin(10, 10);

  // Scroll to bottom with smooth animation after content is loaded
  setTimeout(() => {
    const totalLines = editor.session.getLength();
    const startLine = 0;
    const endLine = totalLines;
    const duration = 1000; // 1 second animation
    const startTime = Date.now();

    function smoothScroll() {
      const elapsed = Date.now() - startTime;
      const progress = Math.min(elapsed / duration, 1);

      // Easing function for smooth animation (ease-out)
      const easeOut = 1 - Math.pow(1 - progress, 3);

      const currentLine = Math.floor(
        startLine + (endLine - startLine) * easeOut,
      );
      editor.gotoLine(currentLine, 0, false);

      if (progress < 1) {
        requestAnimationFrame(smoothScroll);
      }
    }

    smoothScroll();
  }, 100); // Small delay to ensure editor is fully rendered

  editorElement.removeClass("visually-hidden");
  $("#logs-waiting").addClass("visually-hidden");

  // Follow logs functionality using Server-Sent Events
  function startFollowing() {
    if (!currentFile || isFollowing) return;

    isFollowing = true;
    const $followBtn = $("#follow-logs");
    $followBtn.find("i").removeClass("bx-play").addClass("bx-stop");
    $followBtn.find("span").text(t("button.stop", "Stop"));
    $followBtn
      .removeClass("btn-outline-primary")
      .addClass("btn-outline-danger");

    // Create EventSource for streaming
    eventSource = new EventSource(
      `${window.location.pathname}/stream?file=${encodeURIComponent(
        currentFile,
      )}`,
    );

    eventSource.onmessage = function (event) {
      try {
        const data = JSON.parse(event.data);

        switch (data.type) {
          case "refresh":
            // Initial refresh with full file content
            if (data.content !== undefined) {
              editor.setValue(data.content, -1);
              setTimeout(() => {
                editor.gotoLine(editor.session.getLength(), 0, false);
              }, 50);
            }
            console.log(
              t(
                "logs.stream_initialized",
                "Stream initialized with refresh, file size: {{size}}",
                { size: data.size },
              ),
            );
            break;

          case "init":
            console.log(
              t("logs.stream_init", "Stream initialized, file size: {{size}}", {
                size: data.size,
              }),
            );
            break;

          case "append":
            if (data.content) {
              // Append new content
              const currentContent = editor.getValue();
              editor.setValue(currentContent + data.content, -1);

              // Call trimLogContent after appending new content
              trimLogContent();

              // Scroll to bottom smoothly
              setTimeout(() => {
                editor.gotoLine(editor.session.getLength(), 0, false);
              }, 50);
            }
            break;

          case "rotated":
            if (data.content) {
              // File was rotated, replace all content
              editor.setValue(data.content, -1);

              // Scroll to bottom smoothly
              setTimeout(() => {
                editor.gotoLine(editor.session.getLength(), 0, false);
              }, 50);
            }
            break;

          case "heartbeat":
            // Keep-alive message, do nothing
            break;

          case "error":
            console.error(
              t("logs.stream_error", "Stream error: {{message}}", {
                message: data.message,
              }),
            );
            stopFollowing();
            break;
        }
      } catch (e) {
        console.error(
          t("logs.parse_error", "Failed to parse stream data: {{error}}", {
            error: e.message,
          }),
        );
      }
    };

    eventSource.onerror = function (event) {
      console.error(
        t("logs.eventsource_failed", "EventSource connection failed"),
      );
      stopFollowing();
    };
  }

  function stopFollowing() {
    if (!isFollowing) return;

    isFollowing = false;
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }

    const $followBtn = $("#follow-logs");
    $followBtn.find("i").removeClass("bx-stop").addClass("bx-play");
    $followBtn.find("span").text(t("button.follow", "Follow"));
    $followBtn
      .removeClass("btn-outline-danger")
      .addClass("btn-outline-primary");
  }

  function updateFollowButtonState() {
    const followBtn = $("#follow-btn");
    const currentFile = $("#file-select").val();
    const currentPage = $("#page-select").val();
    const totalPages = parseInt($("#page-select option").last().val()) || 1;

    // Only enable follow if we have a file and we're on the latest page (or no pagination)
    const isOnLatestPage = !currentPage || parseInt(currentPage) === totalPages;

    if (!currentFile) {
      followBtn.prop("disabled", true);
      followBtn.attr(
        "title",
        t(
          "tooltip.select_file_to_follow",
          "Select a file to enable follow mode",
        ),
      );
    } else if (!isOnLatestPage) {
      followBtn.prop("disabled", true);
      followBtn.attr(
        "title",
        t(
          "tooltip.follow_latest_page_only",
          "Follow mode is only available on the latest page",
        ),
      );
    } else {
      followBtn.prop("disabled", false);
      followBtn.removeAttr("title");
    }
  }

  function trimLogContent() {
    const session = editor.getSession();
    const lineCount = session.getLength();

    if (lineCount > MAX_LOG_LINES) {
      const linesToRemove = lineCount - MAX_LOG_LINES;
      const range = new ace.Range(0, 0, linesToRemove, 0);
      session.remove(range);

      // Add a notice at the top that some lines were trimmed
      session.insert(
        { row: 0, column: 0 },
        "... (older log entries trimmed for performance) ...\n",
      );
    }
  }

  $("#follow-logs").click(function () {
    if (isFollowing) {
      stopFollowing();
    } else {
      startFollowing();
    }
  });

  $("#copy-logs").click(function () {
    const $this = $(this);
    editor.selectAll();
    editor.focus();
    navigator.clipboard
      .writeText(editor.getSelectedText())
      .then(() => {
        // Success
        console.log("Copied to clipboard");
      })
      .catch((err) => {
        // Error
        console.error("Failed to copy to clipboard", err);
      });
    $this.attr("data-bs-original-title", "Copied!").tooltip("show");

    // Hide tooltip after 2 seconds
    setTimeout(() => {
      $this.tooltip("hide").attr("data-bs-original-title", "");
    }, 2000);
  });

  $("#dark-mode-toggle").on("change", function () {
    setTimeout(() => {
      theme = $("#theme").val();
      setEditorTheme();
    }, 30);
  });

  // Wait for window.i18nextReady = true before continuing
  if (typeof window.i18nextReady === "undefined" || !window.i18nextReady) {
    const waitForI18next = (resolve) => {
      if (window.i18nextReady) {
        resolve();
      } else {
        setTimeout(() => waitForI18next(resolve), 50);
      }
    };
    new Promise((resolve) => {
      waitForI18next(resolve);
    }).then(() => {
      // Initialize any i18n-dependent features here if needed
      updateFollowButtonState();
    });
  } else {
    // i18next is ready, initialize immediately
    updateFollowButtonState();
  }

  // Update button states when page changes
  $(document).on("change", "select, input", function () {
    updateFollowButtonState();
  });

  // Clean up EventSource when page is unloaded
  $(window).on("beforeunload", function () {
    if (eventSource) {
      eventSource.close();
    }
  });
});
