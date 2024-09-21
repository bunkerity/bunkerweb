$(document).ready(function () {
  const editorElement = $("#cache-value");
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

  editorElement.removeClass("visually-hidden");
  $("#cache-waiting").addClass("visually-hidden");
});
