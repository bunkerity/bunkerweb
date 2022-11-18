class Upload {
  constructor(prefix) {
    this.prefix = prefix;
    this.uploadDOM = document.querySelector(`[${this.prefix}-upload-button]`);
    this.uploadTxt = document.querySelector(`[${this.prefix}-upload-text]`);
    this.uploadInp = document.querySelector(`[${this.prefix}-upload-input]`);
    this.dragNdrop = document.querySelector(`[${this.prefix}-drag-and-drop]`);
    this.init();
  }

  init() {
    this.uploadDOM.addEventListener("click", (e) => {
      this.uploadInp.click();
    });

    this.uploadInp.addEventListener("change", (e) => {
      this.uploadTxt.textContent = "FILES : ";
      const files = this.uploadInp.files;
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const spanEl = document.createElement("span");
        spanEl.textContent =
          i == files.length - 1 ? `${file.name};` : `${file.name}, `;
        this.uploadTxt.append(spanEl);
      }
    });
  }
}

const dropEl = document.querySelector("#dropzone");
const drop = new Dropzone(dropEl, {
  paramName: "file",
  method: "post",
  maxFiles: 100,
  autoProcessQueue: false,
  uploadMultiple: true,
  parallelUploads: 100,
  url: "#",
});

const submit = dropEl.querySelector('button[type="submit"]');
submit.addEventListener("click", (e) => {
  e.preventDefault();
  e.stopPropagation();
  drop.processQueue();
});
