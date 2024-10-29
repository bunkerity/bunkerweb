$(document).ready(function () {
  const editorElement = $("#cache-value");
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

  $("#dark-mode-toggle").on("change", function () {
    setTimeout(() => {
      theme = $("#theme").val();
      setEditorTheme();
    }, 30);
  });

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

  editorElement.removeClass("visually-hidden");
  $("#cache-waiting").addClass("visually-hidden");
});
