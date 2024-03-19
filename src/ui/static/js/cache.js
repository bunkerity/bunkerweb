import {
  FolderNav,
  FolderEditor,
  FolderModal,
  FolderDropdown,
} from "./utils/file.manager.js";

class Download {
  constructor(prefix = "cache") {
    this.prefix = prefix;
    this.listContainer = document.querySelector(`[data-cache-container]`);
    this.init();
  }

  init() {
    this.listContainer.addEventListener("click", (e) => {
      try {
        if (
          e.target
            .closest("button")
            .hasAttribute(`data-${this.prefix}-download`)
        ) {
          const dataValue = e.target
            .closest('div:has(span[data-cache-content=""])')
            .firstElementChild.getAttribute("data-value");
          const btnEl = e.target.closest("button");
          const jobName = btnEl.getAttribute(`data-${this.prefix}-job`);
          const fileName = btnEl.getAttribute(`data-${this.prefix}-download`);
          const pluginId = document
            .querySelector('[data-level="1"]')
            .getAttribute("data-name");
          var serviceId = null;
          if (
            document.querySelector(
              '[data-level="2"][data-cache-breadcrumb-item=""]:not(.hidden)',
            )
          ) {
            serviceId = document
              .querySelector('[data-level="2"]')
              .getAttribute("data-name");
          }

          if (dataValue !== "Download file to view content") {
            this.download(fileName, dataValue);
          } else {
            this.sendFileToDL(pluginId, jobName, fileName, serviceId);
          }
        }
      } catch (err) {}
    });
  }

  download(filename, text) {
    var element = document.createElement("a");
    element.setAttribute(
      "href",
      "data:text/plain;charset=utf-8," + encodeURIComponent(text),
    );
    element.setAttribute("download", filename);

    element.style.display = "none";
    document.body.appendChild(element);

    element.click();

    document.body.removeChild(element);
  }

  async sendFileToDL(pluginId, jobName, fileName, serviceId) {
    window.open(
      `${location.href.replace(
        "cache",
        "jobs",
      )}/download?plugin_id=${pluginId}&job_name=${jobName}&file_name=${fileName}` +
        (serviceId ? `&service_id=${serviceId}` : ""),
    );
  }
}

const setModal = new FolderModal("cache");
const setEditor = new FolderEditor();
const setFolderNav = new FolderNav("cache");
const setDropdown = new FolderDropdown("cache");
const setDownload = new Download();
