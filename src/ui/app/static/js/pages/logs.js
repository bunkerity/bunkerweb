$(document).ready(function () {
  const editorElement = $("#raw-logs");
  const initialContent = editorElement.text().trim();
  const editor = ace.edit(editorElement[0]);
  editor.setTheme("ace/theme/cloud9_day"); // cloud9_night when dark mode is supported
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

  $("#copy-logs").click(function () {
    $this = $(this);
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
});
