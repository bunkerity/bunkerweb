class Dropdown {
  constructor(prefix = "plugins") {
    this.prefix = prefix;
    this.container = document.querySelector("main");
    this.initDropdown();
  }

  initDropdown() {
    this.container.addEventListener("click", (e) => {
      //SELECT BTN LOGIC
      try {
        if (
          e.target
            .closest("button")
            .hasAttribute(`${this.prefix}-setting-select`) &&
          !e.target.closest("button").hasAttribute(`disabled`)
        ) {
          const btnName = e.target
            .closest("button")
            .getAttribute(`${this.prefix}-setting-select`);
          if (this.lastDrop !== btnName) {
            this.lastDrop = btnName;
            this.closeAllDrop();
          }

          this.toggleSelectBtn(e);
        }
      } catch (err) {}
      //SELECT DROPDOWN BTN LOGIC
      try {
        if (
          e.target
            .closest("button")
            .hasAttribute(`${this.prefix}-setting-select-dropdown-btn`)
        ) {
          const btn = e.target.closest("button");
          const btnValue = btn.getAttribute("value");
          const btnSetting = btn.getAttribute(
            `${this.prefix}-setting-select-dropdown-btn`
          );
          //stop if same value to avoid new fetching
          const isSameVal = this.isSameValue(btnSetting, btnValue);
          if (isSameVal) return this.hideDropdown(btnSetting);
          //else, add new value to custom
          this.setSelectNewValue(btnSetting, btnValue);
          //close dropdown and change style
          this.hideDropdown(btnSetting);
          this.changeDropBtnStyle(btnSetting, btn);
          //show / hide filter
          if (btnSetting === "instances") {
            this.hideFilterOnLocal(btn.getAttribute("_type"));
          }
        }
      } catch (err) {}
    });
  }

  closeAllDrop() {
    const drops = document.querySelectorAll(
      `[${this.prefix}-setting-select-dropdown]`
    );
    drops.forEach((drop) => {
      drop.classList.add("hidden");
      drop.classList.remove("flex");
      document
        .querySelector(
          `svg[${this.prefix}-setting-select="${drop.getAttribute(
            `${this.prefix}-setting-select-dropdown`
          )}"]`
        )
        .classList.remove("rotate-180");
    });
  }

  isSameValue(btnSetting, value) {
    const selectCustom = document.querySelector(
      `[${this.prefix}-setting-select-text="${btnSetting}"]`
    );
    const currVal = selectCustom.textContent;
    return currVal === value ? true : false;
  }

  setSelectNewValue(btnSetting, value) {
    const selectCustom = document.querySelector(
      `[${this.prefix}-setting-select="${btnSetting}"]`
    );
    selectCustom.querySelector(
      `[${this.prefix}-setting-select-text]`
    ).textContent = value;
  }

  hideDropdown(btnSetting) {
    //hide dropdown
    const dropdownEl = document.querySelector(
      `[${this.prefix}-setting-select-dropdown="${btnSetting}"]`
    );
    dropdownEl.classList.add("hidden");
    dropdownEl.classList.remove("flex");
    //svg effect
    const dropdownChevron = document.querySelector(
      `svg[${this.prefix}-setting-select="${btnSetting}"]`
    );
    dropdownChevron.classList.remove("rotate-180");
  }

  changeDropBtnStyle(btnSetting, selectedBtn) {
    const dropdownEl = document.querySelector(
      `[${this.prefix}-setting-select-dropdown="${btnSetting}"]`
    );
    //reset dropdown btns
    const btnEls = dropdownEl.querySelectorAll("button");

    btnEls.forEach((btn) => {
      btn.classList.remove(
        "dark:bg-primary",
        "bg-primary",
        "bg-primary",
        "text-gray-300",
        "text-gray-300"
      );
      btn.classList.add("bg-white", "dark:bg-slate-700", "text-gray-700");
    });
    //highlight clicked btn
    selectedBtn.classList.remove(
      "bg-white",
      "dark:bg-slate-700",
      "text-gray-700"
    );
    selectedBtn.classList.add("dark:bg-primary", "bg-primary", "text-gray-300");
  }

  toggleSelectBtn(e) {
    const attribut = e.target
      .closest("button")
      .getAttribute(`${this.prefix}-setting-select`);
    //toggle dropdown
    const dropdownEl = document.querySelector(
      `[${this.prefix}-setting-select-dropdown="${attribut}"]`
    );
    const dropdownChevron = document.querySelector(
      `svg[${this.prefix}-setting-select="${attribut}"]`
    );
    dropdownEl.classList.toggle("hidden");
    dropdownEl.classList.toggle("flex");
    dropdownChevron.classList.toggle("rotate-180");
  }

  //hide date filter on local
  hideFilterOnLocal(type) {
    if (type === "local") {
      this.hideInp(`input#from-date`);
      this.hideInp(`input#to-date`);
    }

    if (type !== "local") {
      this.showInp(`input#from-date`);
      this.showInp(`input#to-date`);
    }
  }

  showInp(selector) {
    document.querySelector(selector).closest("div").classList.add("flex");
    document.querySelector(selector).closest("div").classList.remove("hidden");
  }

  hideInp(selector) {
    document.querySelector(selector).closest("div").classList.add("hidden");
    document.querySelector(selector).closest("div").classList.remove("flex");
  }
}

class Filter {
  constructor(prefix = "plugins") {
    this.prefix = prefix;
    this.container = document.querySelector(`[${this.prefix}-filter]`);
    this.keyInp = document.querySelector("input#keyword");
    this.lastType = "all";
    this.initHandler();
  }

  initHandler() {
    //TYPE HANDLER
    this.container.addEventListener("click", (e) => {
      try {
        if (
          e.target
            .closest("button")
            .getAttribute(`${this.prefix}-setting-select-dropdown-btn`) ===
          "types"
        ) {
          const btn = e.target.closest("button");
          const btnValue = btn.getAttribute("value");

          this.lastType = btnValue;
          //run filter
          this.filter();
        }
      } catch (err) {}
    });
    //KEYWORD HANDLER
    this.keyInp.addEventListener("input", (e) => {
      this.filter();
    });
  }

  filter() {
    const logs = document.querySelector(`[${this.prefix}-list]`).children;
    if (logs.length === 0) return;
    //reset
    for (let i = 0; i < logs.length; i++) {
      const el = logs[i];
      el.classList.remove("hidden");
    }
    //filter type
    this.setFilterType(logs);
    this.setFilterKeyword(logs);
  }

  setFilterType(logs) {
    if (this.lastType === "all") return;
    for (let i = 0; i < logs.length; i++) {
      const el = logs[i];
      const type = el.getAttribute(`${this.prefix}-external`).trim();
      if (type !== this.lastType) el.classList.add("hidden");
    }
  }

  setFilterKeyword(logs) {
    const keyword = this.keyInp.value.trim().toLowerCase();
    if (!keyword) return;
    for (let i = 0; i < logs.length; i++) {
      const el = logs[i];
      const content = el
        .querySelector(`[${this.prefix}-content]`)
        .textContent.trim()
        .toLowerCase();

      if (!content.includes(keyword)) el.classList.add("hidden");
    }
  }
}

class Upload {
  constructor() {
    this.container = document.querySelector("[plugins-upload]");
    this.form = document.querySelector("#dropzone-form");
    this.dropZoneElement = document.querySelector(".drop-zone");
    this.fileInput = document.querySelector(".file-input");
    this.progressArea = document.querySelector(".progress-area");
    this.uploadedArea = document.querySelector(".uploaded-area");
    this.init();
  }

  init() {
    //form click launch input file
    this.form.addEventListener("click", () => {
      this.fileInput.click();
    });
    //dropzone logic
    this.dropZoneElement.addEventListener("dragover", (e) => {
      e.preventDefault();
      this.dropZoneElement.classList.add("bg-gray-100 dark:bg-gray-800");
    });

    ["dragleave", "dragend"].forEach((type) => {
      this.dropZoneElement.addEventListener(type, (e) => {
        this.dropZoneElement.classList.remove("bg-gray-100 dark:bg-gray-800");
      });
    });

    this.dropZoneElement.addEventListener("drop", (e) => {
      e.preventDefault();
      this.fileInput.files = e.dataTransfer.files;
      this.fileInput.dispatchEvent(new Event("change"));
      this.dropZoneElement.classList.remove("bg-gray-100 dark:bg-gray-800");
    });
    //when added file, set upload logic
    this.fileInput.addEventListener("change", () => {
      const timeout = 500;
      for (let i = 0; i < this.fileInput.files.length; i++) {
        setTimeout(() => this.uploadFile(this.fileInput.files[i]), timeout * i);
      }
    });
    //close fail/success log
    this.container.addEventListener("click", (e) => {
      try {
        if (e.target.closest("button").hasAttribute("upload-message-delete")) {
          const message = e.target.closest("div[upload-message]");
          message.remove();
        }
      } catch (err) {}
    });
  }

  uploadFile(file) {
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

      const progressHTML = this.fileLoad(name, fileSize);

      this.uploadedArea.classList.add("onprogress");
      this.progressArea.innerHTML = progressHTML;
    });

    xhr.addEventListener("readystatechange", () => {
      if (xhr.readyState === XMLHttpRequest.DONE) {
        this.progressArea.innerHTML = "";
        let uploadedHTML =
          xhr.status == 201
            ? this.fileSuccess(name, fileSize)
            : this.fileFail(name, fileSize);
        this.uploadedArea.insertAdjacentHTML("afterbegin", uploadedHTML);
      }
    });

    let data = new FormData();
    data.set("file", file);
    data.set("csrf_token", document.querySelector("#csrf_token").value);
    xhr.send(data);
  }

  fileLoad(name, fileSize) {
    const str = `<div u class="mt-2 rounded p-2 w-full bg-gray-100 dark:bg-gray-800">
  <div class="flex items-center justify-between">
  <svg class="fill-sky-500 h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><!--! Font Awesome Pro 6.2.1 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license (Commercial License) Copyright 2022 Fonticons, Inc. --><path d="M256 512c141.4 0 256-114.6 256-256S397.4 0 256 0S0 114.6 0 256S114.6 512 256 512zM385 215c9.4 9.4 9.4 24.6 0 33.9s-24.6 9.4-33.9 0l-71-71V392c0 13.3-10.7 24-24 24s-24-10.7-24-24V177.9l-71 71c-9.4 9.4-24.6 9.4-33.9 0s-9.4-24.6 0-33.9L239 103c9.4-9.4 24.6-9.4 33.9 0L385 215z"/></svg>  
  <span class="text-sm text-slate-700 dark:text-gray-300 mr-4">${name} </span>
    <span class="text-sm text-slate-700 dark:text-gray-300">${fileSize}</span>
    <svg  class="cursor-pointer fill-gray-600 dark:fill-gray-300 dark:opacity-80 h-3 w-3 " xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><!--! Font Awesome Pro 6.2.1 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license (Commercial License) Copyright 2022 Fonticons, Inc. --><path d="M256 512c141.4 0 256-114.6 256-256S397.4 0 256 0S0 114.6 0 256S114.6 512 256 512z"/></svg>
  </div>
</div>
</div>`;
    return str;
  }

  fileSuccess(name, fileSize) {
    const str = `<div upload-message class="mt-2 rounded p-2 w-full bg-gray-100 dark:bg-gray-800">
  <div class="flex items-center justify-between">
  <svg
  class="fill-green-500 h-5 w-5"
  xmlns="http://www.w3.org/2000/svg"
  viewBox="0 0 512 512"
>
  <path
    d="M256 512c141.4 0 256-114.6 256-256S397.4 0 256 0S0 114.6 0 256S114.6 512 256 512zM369 209L241 337c-9.4 9.4-24.6 9.4-33.9 0l-64-64c-9.4-9.4-9.4-24.6 0-33.9s24.6-9.4 33.9 0l47 47L335 175c9.4-9.4 24.6-9.4 33.9 0s9.4 24.6 0 33.9z"
  />
</svg>          
  <span class="text-sm text-slate-700 dark:text-gray-300 mr-4">${name} </span>
    <span class="text-sm text-slate-700 dark:text-gray-300">${fileSize}</span>
    <button type="button" upload-message-delete>
    <svg  class="cursor-pointer fill-gray-600 dark:fill-gray-300 dark:opacity-80 h-4 w-4 " xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 512">
<path  d="M310.6 150.6c12.5-12.5 12.5-32.8 0-45.3s-32.8-12.5-45.3 0L160 210.7 54.6 105.4c-12.5-12.5-32.8-12.5-45.3 0s-12.5 32.8 0 45.3L114.7 256 9.4 361.4c-12.5 12.5-12.5 32.8 0 45.3s32.8 12.5 45.3 0L160 301.3 265.4 406.6c12.5 12.5 32.8 12.5 45.3 0s12.5-32.8 0-45.3L205.3 256 310.6 150.6z"></path>
</svg>
</button>
  </div>
</div>
</div>`;
    return str;
  }

  fileFail(name, fileSize) {
    const str = `<div upload-message class="mt-2 rounded p-2 w-full bg-gray-100 dark:bg-gray-800">
  <div class="flex items-center justify-between">
  <svg
  class="fill-red-500 h-5 w-5 mr-4"
  xmlns="http://www.w3.org/2000/svg"
  viewBox="0 0 512 512"
>
  <path
    d="M256 512c141.4 0 256-114.6 256-256S397.4 0 256 0S0 114.6 0 256S114.6 512 256 512zM175 175c9.4-9.4 24.6-9.4 33.9 0l47 47 47-47c9.4-9.4 24.6-9.4 33.9 0s9.4 24.6 0 33.9l-47 47 47 47c9.4 9.4 9.4 24.6 0 33.9s-24.6 9.4-33.9 0l-47-47-47 47c-9.4 9.4-24.6 9.4-33.9 0s-9.4-24.6 0-33.9l47-47-47-47c-9.4-9.4-9.4-24.6 0-33.9z"
  />
</svg>                
  <span class="text-sm text-slate-700 dark:text-gray-300 mr-4">${name} </span>
    <span class="text-sm text-slate-700 dark:text-gray-300">${fileSize}</span>
    <button type="button" upload-message-delete>

    <svg  class="cursor-pointer fill-gray-600 dark:fill-gray-300 dark:opacity-80 h-4 w-4 " xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 512">
<path  d="M310.6 150.6c12.5-12.5 12.5-32.8 0-45.3s-32.8-12.5-45.3 0L160 210.7 54.6 105.4c-12.5-12.5-32.8-12.5-45.3 0s-12.5 32.8 0 45.3L114.7 256 9.4 361.4c-12.5 12.5-12.5 32.8 0 45.3s32.8 12.5 45.3 0L160 301.3 265.4 406.6c12.5 12.5 32.8 12.5 45.3 0s12.5-32.8 0-45.3L205.3 256 310.6 150.6z"></path>
</svg>
</button>

  </div>
</div>
</div>`;
    return str;
  }
}

class Modal {
  constructor(prefix = "plugins") {
    this.prefix = prefix;
    this.container = document.querySelector(`[${this.prefix}-list]`);
    this.modal = document.querySelector(`[${this.prefix}-modal]`);
    this.modalNameInp = this.modal.querySelector("input#name");
    this.modalExtInp = this.modal.querySelector("input#external");

    this.modalTitle = this.modal.querySelector(`[${this.prefix}-modal-title]`);
    this.modalTxt = this.modal.querySelector(`[${this.prefix}-modal-text]`);
    this.init();
  }

  init() {
    this.container.addEventListener("click", (e) => {
      //DELETE HANDLER
      try {
        if (
          e.target.closest("button").getAttribute(`${this.prefix}-action`) ===
          "delete"
        ) {
          const btnEl = e.target.closest("button");
          this.setModal(btnEl);
          this.showModal();
        }
      } catch (err) {}
    });

    this.modal.addEventListener("click", (e) => {
      //CLOSE MODAL HANDLER
      try {
        if (
          e.target.closest("button").hasAttribute(`${this.prefix}-modal-close`)
        ) {
          this.hideModal();
        }
      } catch (err) {}
    });
  }

  setModal(el) {
    //name
    const elName = el.getAttribute("name");
    this.modalNameInp.value = elName;
    this.modalTitle.textContent = `DELETE ${elName}`;
    this.modalTxt.textContent = `Are you sure you want to delete ${elName} ?`;
    //external
    const isExternal = el
      .closest("[plugins-external]")
      .getAttribute("plugins-external")
      .trim()
      .includes("external")
      ? "True"
      : "False";
    this.modalExtInp.value = isExternal;
  }

  showModal() {
    this.modal.classList.add("flex");
    this.modal.classList.remove("hidden");
  }

  hideModal() {
    this.modal.classList.add("hidden");
    this.modal.classList.remove("flex");
  }
}

const setDropdown = new Dropdown("plugins");
const setFilter = new Filter("plugins");
const setUpload = new Upload();
const setModal = new Modal("plugins");
