$(document).ready(function () {
  const editorElement = $("#raw-logs");
  const initialContent = editorElement.text().trim();
  const editor = ace.edit(editorElement[0]);
  var theme = $("#theme").val();

  function setEditorTheme() {
    if (theme === "dark") {
      editor.setTheme("ace/theme/cloud9_night");
    } else {
      editor.setTheme("ace/theme/cloud9_day");
    }
  }

  setEditorTheme();
  editor.session.setMode("ace/mode/text");
  editor.setReadOnly(true);

  // Set the editor's initial content
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
});
