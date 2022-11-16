var editor_path = "";
var decoder = new TextDecoder("utf-8");

$(document).ready(function () {
  $("textarea").numberedtextarea({ allowTabChar: true });

  $("#modal-edit-new-file").on("show.bs.modal", function (event) {
    var button = $(event.relatedTarget);
    var path = button.data("path");
    $("#file-path").val(path);
    var new_path = path.split("/");
    var name = new_path.pop().replace(".conf", "");
    var action = button.data("action");
    $("#file-operation").val(action);
    var content = button.data("content");
    $("#modal-edit-new-file-label").html(
      `<div class="d-flex align-items-center"><div class="flex-grow-1">${
        action == "edit" ? "Editing" : "New"
      } file: <span class="d-md-inline d-none">${
        action == "edit" ? new_path.join("/") : path
      }</span><span class="d-md-none">.../${
        action == "edit" ? new_path.pop() : path.split("/").pop()
      }</span>/</div><div class="d-sm-flex align-items-center"><input type="text" class="form-control" id="new-file-name" name="name" value="${
        action == "edit" ? name : ""
      }" placeholder="File name" required="" pattern="^[a-zA-Z0-9_-]{1,64}$" title="File name can only contain numbers, letters, underscores and hyphens (min 1 character and max 64)" />.conf</div></div>`
    );

    var editor = $("#editor");

    if (action == "edit") {
      if (editor_path != path) {
        editor.html(atob(content));
      }
    } else {
      editor.html("");
    }

    editor.keyup();
    editor_path = path;
  });

  $("#modal-edit-new-folder").on("show.bs.modal", function (event) {
    var button = $(event.relatedTarget);
    var path = button.data("path");
    $("#folder-path").val(path);
    var action = button.data("action");
    $("#folder-operation").val(action);
    var foldername = path.split("/").pop();
    $("#modal-edit-new-folder-label").html(
      `<div class="d-flex align-items-center"><div class="flex-grow-1">${
        action == "edit" ? "Editing" : "New"
      } folder: <span class="d-md-inline d-none">${path}</span><span class="d-md-none">.../${path
        .split("/")
        .pop()}</span>/</div><div class="d-sm-flex align-items-center"><input type="text" class="form-control" id="new-folder-name" name="name" placeholder="Folder name" value="${
        action == "edit" ? foldername : ""
      }" required="" pattern="^[a-zA-Z0-9_-]{1,64}$" title="Folder name can only contain numbers, letters, underscores and hyphens (min 1 character and max 64)" /></div></div>`
    );
  });

  $("#modal-delete").on("show.bs.modal", function (event) {
    var button = $(event.relatedTarget);
    var path = button.data("path");
    $("#delete-path").val(path);
    var name = path.split("/").pop();
    $("#modal-delete-label").html(
      `Deleting ${name.includes(".") ? "file" : "folder"}`
    );
    $("#modal-delete-body").html(
      `Are you sure you want to delete <b>${path}</b> ?`
    );
  });

  $(".collapse-div").click(function () {
    $(this).find(".rotate-icon").toggleClass("down");
  });

  $("form").on("focus", ".form-control", function () {
    if ($(this).attr("type") == "text" && $(this).prop("validity").valid) {
      $(this).addClass("is-valid");
    }
  });

  $("form").on("focusout", ".form-control", function () {
    if ($(this).attr("type") == "text") {
      $(this).removeClass("is-valid");
    }
  });

  $("form").on("change", ".form-control", function () {
    if ($(this).attr("type") == "text" && !$(this).prop("validity").valid) {
      $(this).addClass("is-invalid");
    } else {
      $(this).removeClass("is-invalid");
    }
  });
});
