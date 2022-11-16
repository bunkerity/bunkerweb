$(document).ready(function () {
  $("#modal-delete").on("show.bs.modal", function (event) {
    var button = $(event.relatedTarget);
    var path = button.data("path");
    $("#delete-path").val(path);
    var name = path.split("/").pop();
    $("#modal-delete-label").html("Deleting plugin");
    $("#modal-delete-body").html(
      `Are you sure you want to delete <b>${path}</b> ?`
    );
  });

  $(".collapse-div").click(function () {
    $(this).find(".rotate-icon").toggleClass("down");
  });
});

const form = document.querySelector("form"),
  dropZoneElement = document.querySelector(".drop-zone"),
  fileInput = document.querySelector(".file-input"),
  progressArea = document.querySelector(".progress-area"),
  uploadedArea = document.querySelector(".uploaded-area");

form.addEventListener("click", () => {
  fileInput.click();
});

fileInput.onchange = ({ target }) => {
  timeout = 500;
  for (let i = 0; i < target.files.length; i++) {
    setTimeout(() => uploadFile(target.files[i]), timeout * i);
  }
};

dropZoneElement.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropZoneElement.classList.add("drop-zone--over");
});

["dragleave", "dragend"].forEach((type) => {
  dropZoneElement.addEventListener(type, (e) => {
    dropZoneElement.classList.remove("drop-zone--over");
  });
});

dropZoneElement.addEventListener("drop", (e) => {
  e.preventDefault();
  fileInput.files = e.dataTransfer.files;
  fileInput.dispatchEvent(new Event("change"));
  dropZoneElement.classList.remove("drop-zone--over");
});

function uploadFile(file) {
  let name = file.name;
  if (name.length >= 12) {
    let splitName = name.split(".");
    name = splitName[0].substring(0, 13) + "... ." + splitName[1];
  }

  let xhr = new XMLHttpRequest();
  xhr.open("POST", "plugins/upload");
  let fileSize;

  xhr.upload.addEventListener("progress", ({ loaded, total }) => {
    let fileLoaded = Math.floor((loaded / total) * 100);
    let fileTotal = Math.floor(total / 1000);

    fileTotal < 1024
      ? (fileSize = fileTotal + " KB")
      : (fileSize = (loaded / (1024 * 1024)).toFixed(2) + " MB");

    let progressHTML = `<li class="row">
    <span class="fa-solid fa-file-zipper"></span>
                          <span class="content">
                            <div class="details">
                              <span class="name">${name} • Uploading</span>
                              <span class="percent">${fileLoaded}%</span>
                            </div>
                            <div class="progress-bar">
                              <div class="progress" style="width: ${fileLoaded}%"></div>
                            </div>
                          </span>
                        </li>`;

    uploadedArea.classList.add("onprogress");
    progressArea.innerHTML = progressHTML;
  });

  xhr.onreadystatechange = function () {
    if (xhr.readyState === XMLHttpRequest.DONE) {
      progressArea.innerHTML = "";
      let uploadedHTML =
        xhr.status == 201
          ? `<li class="row">
                            <div class="content upload">
                            <i class="fa-solid fa-file-zipper"></i>
                              <div class="details">
                                <span class="name">${name} • Uploaded</span>
                                <span class="size">${fileSize}</span>
                              </div>
                            </div>
                            <i class="fa-solid fa-check"></i>
                          </li>`
          : `<li class="row failed">
                          <div class="content upload">
                          <i class="fa-solid fa-file-zipper"></i>
                            <div class="details">
                              <span class="name">${name} • Failed</span>
                              <span class="size">${fileSize}</span>
                            </div>
                          </div>
                          <i class="fa-solid fa-xmark"></i>
                        </li>`;

      uploadedArea.classList.remove("onprogress");
      uploadedArea.insertAdjacentHTML("afterbegin", uploadedHTML);
    }
  };

  let data = new FormData();
  data.set("file", file);
  data.set("csrf_token", $("#csrf_token").val());
  xhr.send(data);
}
