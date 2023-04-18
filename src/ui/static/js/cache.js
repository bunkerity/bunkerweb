import {
  FolderNav,
  FolderEditor,
  FolderModal,
  FolderDropdown,
} from "./utils/file.manager.js";

class Download {
  constructor(prefix = "cache") {
    this.prefix = prefix;
    this.listContainer = document.querySelector(`[cache-container]`);
    this.init();
  }

  init() {
    this.listContainer.addEventListener("click", (e) => {
      try {
        if (
          e.target.closest("button").hasAttribute(`${this.prefix}-download`)
        ) {
          const btnEl = e.target.closest("button");
          const jobName = btnEl.getAttribute("cache-download");
          const fileName = btnEl.getAttribute("cache-file");
          this.sendFileToDL(jobName, fileName);
        }
      } catch (err) {}
    });
  }

  async sendFileToDL(jobName, fileName) {
    window.open(
      `${location.href.replace(
        "cache",
        "jobs"
      )}/download?job_name=${jobName}&file_name=${fileName}`
    );
  }
}

const setModal = new FolderModal("cache");
const setEditor = new FolderEditor();
const setFolderNav = new FolderNav("cache");
const setDropdown = new FolderDropdown("cache");
const setDownload = new Download();
