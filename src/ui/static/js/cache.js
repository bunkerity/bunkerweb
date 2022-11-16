var editor_path = "";

$(document).ready(function () {
  $("textarea").numberedtextarea({ allowTabChar: true });

  $("#modal-see-file").on("show.bs.modal", function (event) {
    var button = $(event.relatedTarget);
    var path = button.data("path");
    var content = button.data("content");
    $("#modal-see-file-label").html(`File: ${path}`);

    if (editor_path != path) {
      $("#editor").html(atob(content));
    }

    editor_path = path;
  });

  $(".download-button").click(function () {
    var filepath = $(this).attr("data-path");
    windows.open(`${location.href}/download?path=${filepath}`, "_blank");
  });

  $(".collapse-div").click(function () {
    $(this).find(".rotate-icon").toggleClass("down");
  });
});
