/* ============================================================================
   components/file-upload.html -- dropzone affordance
   ----------------------------------------------------------------------------
   Generic, event-delegated click / keyboard / drag-drop wiring for the
   variant="dropzone" shape rendered by components/file-upload.html. Scoped to
   `[data-bw-file-upload="dropzone"]` only -- a marker only that macro renders --
   so this can never double-wire the existing hand-rolled dropzones in
   plugins.html (#drag-area) or template_edit.html (#raw-config-dropzone /
   #missing-configs-dropzone), which keep their own bespoke page JS untouched.

   This file only makes the box behave like a dropzone (open the native file
   dialog on click/Enter/Space, toggle "is-dragover" while dragging, forward
   dropped files into the underlying <input type="file"> and fire a native
   "change" event on it). Reading/validating/listing the files stays real
   page-specific business logic, wired by whichever page adopts this macro --
   same division of responsibility as plugins.js / template_edit.js today.

   variant="inline" needs no such file -- it's wired for free by the
   already-shipped static/js/plugins-settings.js (class + data-attribute
   driven, not page-specific).
   ============================================================================ */
(function () {
  "use strict";

  function targetInput(box) {
    var sel = box.getAttribute("data-file-input");
    return sel ? document.querySelector(sel) : null;
  }

  function isDisabled(box) {
    return (
      box.classList.contains("is-disabled") ||
      box.getAttribute("aria-disabled") === "true"
    );
  }

  document.addEventListener("click", function (e) {
    var box =
      e.target.closest && e.target.closest('[data-bw-file-upload="dropzone"]');
    if (!box || isDisabled(box)) return;
    // Clicks on the styled Browse affordance bubble to this single control.
    var input = targetInput(box);
    if (input) input.click();
  });

  document.addEventListener("keydown", function (e) {
    if (e.key !== "Enter" && e.key !== " " && e.key !== "Spacebar") return;
    var box =
      e.target.closest && e.target.closest('[data-bw-file-upload="dropzone"]');
    if (!box || isDisabled(box)) return;
    e.preventDefault();
    var input = targetInput(box);
    if (input) input.click();
  });

  function onDragOver(e) {
    var box =
      e.target.closest && e.target.closest('[data-bw-file-upload="dropzone"]');
    if (!box || isDisabled(box)) return;
    e.preventDefault();
    if (e.dataTransfer) e.dataTransfer.dropEffect = "copy";
    box.classList.add("is-dragover");
  }
  document.addEventListener("dragenter", onDragOver, false);
  document.addEventListener("dragover", onDragOver, false);

  document.addEventListener(
    "dragleave",
    function (e) {
      var box =
        e.target.closest &&
        e.target.closest('[data-bw-file-upload="dropzone"]');
      if (!box) return;
      if (!box.contains(e.relatedTarget)) box.classList.remove("is-dragover");
    },
    false,
  );

  document.addEventListener(
    "drop",
    function (e) {
      var box =
        e.target.closest &&
        e.target.closest('[data-bw-file-upload="dropzone"]');
      if (!box) return;
      e.preventDefault();
      box.classList.remove("is-dragover");
      if (isDisabled(box)) return;
      var input = targetInput(box);
      var dt = e.dataTransfer;
      if (input && dt && dt.files && dt.files.length) {
        input.files = dt.files;
        input.dispatchEvent(new Event("change", { bubbles: true }));
      }
    },
    false,
  );
})();
