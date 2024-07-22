import {
  FolderNav,
  FolderEditor,
  FolderModal,
  FolderDropdown,
} from "./utils/file.manager.js";

import { Dropdown } from "./utils/dashboard.js";

class FilterManager {
  constructor(prefix = "configs") {
    this.prefix = prefix;
    this.container = document.querySelector(`[data-${this.prefix}-filter]`);
    this.confPathOnlyValue = "false";
    this.globalConfOnlyValue = "false";

    this.init();
  }

  init() {
    window.addEventListener("DOMContentLoaded", () => {
      this.setPathWithConfFilter();
      this.initHandler();
    });
  }

  setPathWithConfFilter() {
    // get all .conf by path
    const confs = document.querySelectorAll("[data-path*='.conf']");
    // for each, get previous path and set attribute data-path-to-a-conf
    confs.forEach((conf) => {
      const separatePath = conf.getAttribute("data-path").split("/");
      separatePath.shift();
      for (let i = 0; i < separatePath.length; i++) {
        // merge path to given index
        const path = separatePath
          .slice(0, i + 1)
          .join("/")
          .trim();
        // get element with
        const folder = document.querySelector(`[data-path="/${path}"]`);
        if (!folder) continue;
        // set attribute data-path-to-a-conf
        folder.setAttribute("data-path-to-a-conf", "");
      }
    });
  }

  initHandler() {
    this.container.addEventListener("click", (e) => {
      try {
        if (
          e.target
            .closest("button")
            .getAttribute(`data-${this.prefix}-setting-select-dropdown-btn`) ===
            "withconf" ||
          e.target
            .closest("button")
            .getAttribute(`data-${this.prefix}-setting-select-dropdown-btn`) ===
            "globalconf"
        ) {
          setTimeout(() => {
            // return to root to avoid conflict, filter logic is on file.manager.js
            document
              .querySelector('[data-configs-breadcrumb-item][data-level="0"]')
              .querySelector("button")
              .click();
          }, 50);
        }
      } catch (err) {}
    });
  }
}

class ConfigsInfo {
  constructor() {
    this.init();
  }

  init() {
    window.addEventListener("DOMContentLoaded", () => {
      this.totalInfo = document.querySelector("[data-info-total-conf]");
      this.globalInfo = document.querySelector("[data-info-global-conf]");
      this.totalInfo.textContent = document
        .querySelector("[data-configs-folders]")
        .querySelectorAll("[data-_type='file']").length;
      this.globalInfo.textContent = document
        .querySelector("[data-configs-folders]")
        .querySelectorAll("[data-_type='file'][data-level='2']").length;
    });
  }
}

// some configs are root only
class SetRootOnlyConf {
  constructor() {
    this.init();
    this.rootOnly = ["http", "default-http-server", "stream"];
  }

  init() {
    window.addEventListener("DOMContentLoaded", () => {
      //  remove server when config if root only
      const itemsToRemove = [];
      for (let i = 0; i < this.rootOnly.length; i++) {
        const rootName = this.rootOnly[i];
        itemsToRemove.push(
          ...document.querySelectorAll(
            `[data-path^="/etc/bunkerweb/configs/${rootName}"][data-_type="folder"][data-level="2"]`,
          ),
        );
      }
      itemsToRemove.forEach((item) => {
        item.remove();
      });
    });
  }
}

const setConfigsInfo = new ConfigsInfo();
const setModal = new FolderModal("configs");
const setEditor = new FolderEditor();
const setFolderNav = new FolderNav("configs");
const setDropdown = new FolderDropdown("configs");
const setFilterDropdown = new Dropdown("configs");
const setFilter = new FilterManager();
const setRootOnlyConf = new SetRootOnlyConf();
