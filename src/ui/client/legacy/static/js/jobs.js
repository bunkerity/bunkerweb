import { Filter, Dropdown } from "./utils/dashboard.js";

class Download {
  constructor(prefix = "jobs") {
    this.prefix = prefix;
    this.listContainer = document.querySelector(`[data-${this.prefix}-list]`);
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
          const btnEl = e.target.closest("button");
          const pluginId = btnEl.getAttribute("data-jobs-plugin");
          const jobName = btnEl.getAttribute("data-jobs-download");
          const fileName = btnEl.getAttribute("data-jobs-file");
          this.sendFileToDL(pluginId, jobName, fileName);
        }
      } catch (err) {}
    });
  }

  async sendFileToDL(pluginId, jobName, fileName) {
    window.open(
      `${location.href}/download?plugin_id=${pluginId}&job_name=${jobName}&file_name=${fileName}`,
    );
  }
}

const setDropdown = new Dropdown("jobs");
const setDownload = new Download();

const filterContainer = document.querySelector("[data-jobs-list-container]");
if (filterContainer) {
  const noMatchEl = document.querySelector("[data-jobs-nomatch]");
  const filterEls = document.querySelectorAll(`[data-jobs-item]`);
  const keywordFilter = {
    handler: document.querySelector("input#keyword"),
    handlerType: "input",
    value: document.querySelector("input#keyword").value,
    filterEls: filterEls,
    filterAtt: "data-jobs-name",
    filterType: "keyword",
  };
  const successFilter = {
    handler: document.querySelector(
      "[data-jobs-setting-select-dropdown='success']",
    ),
    handlerType: "select",
    value: document
      .querySelector("[data-jobs-setting-select-text='success']")
      .textContent.trim()
      .toLowerCase(),
    filterEls: filterEls,
    filterAtt: "data-jobs-success",
    filterType: "bool",
  };
  const reloadFilter = {
    handler: document.querySelector(
      "[data-jobs-setting-select-dropdown='reload']",
    ),
    handlerType: "select",
    value: document
      .querySelector("[data-jobs-setting-select-text='reload']")
      .textContent.trim()
      .toLowerCase(),
    filterEls: filterEls,
    filterAtt: "data-jobs-reload",
    filterType: "bool",
  };
  const everyFilter = {
    handler: document.querySelector(
      "[data-jobs-setting-select-dropdown='every']",
    ),
    handlerType: "select",
    value: document
      .querySelector("[data-jobs-setting-select-text='every']")
      .textContent.trim()
      .toLowerCase(),
    filterEls: filterEls,
    filterAtt: "data-jobs-every",
    filterType: "match",
  };
  new Filter(
    "jobs",
    [keywordFilter, successFilter, reloadFilter, everyFilter],
    filterContainer,
    noMatchEl,
  );
}
