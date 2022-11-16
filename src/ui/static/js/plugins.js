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
    this.dragNdrop.addEventListener("dargenter", () => {
      console.log("enter");
      this.dragNdrop.classList.add("border", "border-red-500");
    });
    this.dragNdrop.addEventListener("dargover", () => {
      this.dragNdrop.classList.add("border", "border-red-500");
    });
    this.dragNdrop.addEventListener("drop", (e) => {
      let dt = e.dataTransfer;
      let files = dt.files;
      console.log(files);
    });

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

const setUpload = new Upload("plugins");
