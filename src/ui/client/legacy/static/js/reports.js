import { Filter, Dropdown } from "./utils/dashboard.js";

const setDropdown = new Dropdown("reports");

const filterContainer = document.querySelector("[data-reports-list-container]");
if (filterContainer) {
  const noMatchEl = document.querySelector("[data-reports-nomatch]");
  const filterEls = document.querySelectorAll(`[data-reports-item]`);
  const keywordFilter = {
    handler: document.querySelector("input#keyword"),
    handlerType: "input",
    value: document.querySelector("input#keyword").value,
    filterEls: filterEls,
    filterAtt: "data-reports-keyword",
    filterType: "keyword",
  };
  const countryFilter = {
    handler: document.querySelector(
      "[data-reports-setting-select-dropdown='country']",
    ),
    handlerType: "select",
    value: document
      .querySelector("[data-reports-setting-select-text='country']")
      .textContent.trim()
      .toLowerCase(),
    filterEls: filterEls,
    filterAtt: "data-reports-country",
    filterType: "match",
  };
  const methodFilter = {
    handler: document.querySelector(
      "[data-reports-setting-select-dropdown='method']",
    ),
    handlerType: "select",
    value: document
      .querySelector("[data-reports-setting-select-text='method']")
      .textContent.trim()
      .toLowerCase(),
    filterEls: filterEls,
    filterAtt: "data-reports-method",
    filterType: "match",
  };

  const statusFilter = {
    handler: document.querySelector(
      "[data-reports-setting-select-dropdown='status']",
    ),
    handlerType: "select",
    value: document
      .querySelector("[data-reports-setting-select-text='status']")
      .textContent.trim()
      .toLowerCase(),
    filterEls: filterEls,
    filterAtt: "data-reports-status",
    filterType: "match",
  };

  const reasonFilter = {
    handler: document.querySelector(
      "[data-reports-setting-select-dropdown='reason']",
    ),
    handlerType: "select",
    value: document
      .querySelector("[data-reports-setting-select-text='reason']")
      .textContent.trim()
      .toLowerCase(),
    filterEls: filterEls,
    filterAtt: "data-reports-reason",
    filterType: "match",
  };
  new Filter(
    "reports",
    [keywordFilter, countryFilter, methodFilter, statusFilter, reasonFilter],
    filterContainer,
    noMatchEl,
  );
}
