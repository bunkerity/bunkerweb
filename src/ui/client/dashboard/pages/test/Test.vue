<script setup>
import { ref, reactive, onMounted, Teleport, computed, onUnmounted } from "vue";
import Icons from "@components/Widget/Icons.vue";
import Text from "@components/Widget/Text.vue";
import Fields from "@components/Form/Fields.vue";
import Button from "@components/Widget/Button.vue";
import ButtonGroup from "@components/Widget/ButtonGroup.vue";
import { TabulatorFull as Tabulator } from "tabulator-tables"; //import Tabulator library
import { useEqualStr } from "@utils/global.js";
import { addSorter } from "@utils/tabulator.js";

// TODO : ADD JSDOC COMPONENT

const customComponents = ["Icons", "Text", "Fields", "Button", "ButtonGroup"];

const props = defineProps({
  columns: {
    type: Array,
    required: true,
    default: [
      { title: "Name", field: "name", width: 150 },
      { title: "Icon", field: "icon", formatter: "icons" },
    ],
  },
  data: {
    type: Array,
    required: false,
    default: [
      { id: 1, name: "Oli Bob", icon: { iconName: "box", color: "amber" } },
      {
        id: 2,
        name: "Mary May",
        icon: { iconName: "document", color: "blue" },
      },
      {
        id: 3,
        name: "Christine Lobowski",
        icon: { iconName: "box", color: "amber" },
      },
      {
        id: 4,
        name: "Brendon Philips",
        icon: { iconName: "document", color: "blue" },
      },
      {
        id: 5,
        name: "Margret Marmajuke",
        icon: { iconName: "box", color: "amber" },
      },
      {
        id: 6,
        name: "Frank Harbours",
        icon: { iconName: "document", color: "blue" },
      },
      {
        id: 7,
        name: "Jamie Newhart",
        icon: { iconName: "box", color: "amber" },
      },
      {
        id: 8,
        name: "Gemma Jane",
        icon: { iconName: "document", color: "blue" },
      },
      { id: 9, name: "Emily Sykes", icon: { iconName: "box", color: "amber" } },
      {
        id: 10,
        name: "James Newman",
        icon: { iconName: "document", color: "blue" },
      },
      {
        id: 11,
        name: "James Newman",
        icon: { iconName: "document", color: "blue" },
      },
      {
        id: 12,
        name: "James Newman",
        icon: { iconName: "document", color: "blue" },
      },
      {
        id: 13,
        name: "James Newman",
        icon: { iconName: "document", color: "blue" },
      },
      {
        id: 14,
        name: "James Newman",
        icon: { iconName: "document", color: "blue" },
      },
      {
        id: 15,
        name: "James Newman",
        icon: { iconName: "document", color: "blue" },
      },
      {
        id: 16,
        name: "James Newman",
        icon: { iconName: "document", color: "blue" },
      },
    ],
  },
  isPagination: {
    type: Boolean,
    required: false,
    default: true,
  },
  paginationSize: {
    type: Number,
    required: false,
    default: 10,
  },
  paginationInitialPage: {
    type: Number,
    required: false,
    default: 1,
  },
  paginationSizeSelector: {
    type: Array,
    required: false,
    default: [10, 25, 50, 100, true],
  },
});

const tableEl = ref(null); //reference to your table element

const table = reactive({
  test: true,
  instance: null,
  columns: props.columns,
  data: props.data,
  customComponents: [],
  options: computed(() => {
    const opts = {
      data: table.data, //link data to table
      reactiveData: true, //enable data reactivity
    };

    // columns formatting
    let columns = JSON.parse(JSON.stringify(table.columns));
    columns = addSortComponents(columns);
    opts.columns = columns;

    if (props.isPagination) {
      opts.pagination = true;
      opts.paginationSize = props.paginationSize;
      opts.paginationInitialPage = props.paginationInitialPage;
      opts.paginationButtonCount = 2;
      opts.paginationSizeSelector = props.paginationSizeSelector;
      opts.paginationCounter = "rows";
    }
    return opts;
  }),
});

/**
 *  @name addCustomComponent
 *  @description Utils to add needed data when we have a custom component.
 *  We will use the type to render the Vue component, the values to pass and the elDOM to teleport the component inside the right cell.
 *  @example { type: "Icons", values: { iconName: "box", color: "amber" }, elDOM: HTMLElement }
 *  @param {str} type -  The type is the name of the component.
 *  @param {object} values - The values are the props that we want to pass to the component.
 *  @param {HTMLElement} elDOM - The elDOM is the element where we want to teleport the component.
 *  @returns {void}
 */
function addCustomComponent(type, values, elDOM) {
  table.customComponents.push({
    type: type,
    values: values,
    elDOM: elDOM,
  });
}

/**
 *  @name addComponentsFormats
 *  @description Add all custom components on a list to later add them to each tabulator cell.
 *  We are using the Tabulart.extendModule() that allow use to execute a custom function when we are matching a custom formatter.
 *  We need to define on rows the formatter that we want to use to render the custom component.
 *  @returns {void}
 */
function addComponentsFormats() {
  const formatOpts = {};
  for (let i = 0; i < customComponents.length; i++) {
    const module = customComponents[i];
    formatOpts[module.toLowerCase()] = function (cell, formatterParams) {
      addCustomComponent(module, cell.getValue(), cell.getElement());
      return "";
    };
  }
  Tabulator.extendModule("format", "formatters", formatOpts);
}

/**
 *  @name addSortComponents
 *  @description Check every columns and add a custom sort for some components, so this is link to customComponents list and previous formatters set.
 *  @example For Icons, we will add a custom sorter that will check between iconNames.
 *  @param {array} columns -  The columns are the list of columns that we want to check.
 *  @returns {array} - Return the columns with the custom sort added.
 */
function addSortComponents(columns) {
  for (let i = 0; i < columns.length; i++) {
    const column = columns[i];
    if (!("formatter" in column)) continue;
    const formatName = column.formatter.toLowerCase();

    addSorter(column, formatName);
  }
  return columns;
}

onMounted(() => {
  addComponentsFormats();
  table.instance = new Tabulator(tableEl.value, table.options);
});

onUnmounted(() => {
  table.instance.destroy();
  table.instance = null;
});
</script>

<template>
  <div ref="tableEl"></div>
  <template
    :key="table.customComponents"
    v-for="comp in table.customComponents"
  >
    <Teleport :to="comp.elDOM">
      <Icons
        v-if="useEqualStr(comp.type, 'Icons')"
        v-bind="{ ...comp.values }"
      />
      <Text v-if="useEqualStr(comp.type, 'Text')" v-bind="{ ...comp.values }" />
      <Fields
        v-if="useEqualStr(comp.type, 'Fields')"
        v-bind="{ ...comp.values }"
      />
      <Button
        v-if="useEqualStr(comp.type, 'Button')"
        v-bind="{ ...comp.values }"
      />
      <ButtonGroup
        v-if="useEqualStr(comp.type, 'ButtonGroup')"
        v-bind="{ ...comp.values }"
      />
    </Teleport>
  </template>
</template>

<style>
.tabulator {
  position: relative;
  border: 1px solid rgba(34, 36, 38, 0.15);
  background-color: #ffffff;
  font-size: 14px;
  text-align: left;
  overflow: hidden;
  -webkit-transform: translateZ(0);
  -moz-transform: translateZ(0);
  -ms-transform: translateZ(0);
  -o-transform: translateZ(0);
  transform: translateZ(0);
}

.tabulator[tabulator-layout="fitDataFill"]
  .tabulator-tableholder
  .tabulator-table {
  min-width: 100%;
}

.tabulator[tabulator-layout="fitDataTable"] {
  display: inline-block;
}

.tabulator.tabulator-block-select {
  user-select: none;
}

.tabulator.tabulator-ranges .tabulator-cell:not(.tabulator-editing) {
  user-select: none;
}

.tabulator .tabulator-header {
  position: relative;
  box-sizing: border-box;
  width: 100%;
  border-bottom: 1px solid #999;
  background-color: #f9fafb;
  color: rgba(0, 0, 0, 0.87);
  font-weight: bold;
  white-space: nowrap;
  overflow: hidden;
  -moz-user-select: none;
  -khtml-user-select: none;
  -webkit-user-select: none;
  -o-user-select: none;
  outline: none;
}

.tabulator .tabulator-header.tabulator-header-hidden {
  display: none;
}

.tabulator .tabulator-header .tabulator-header-contents {
  position: relative;
  overflow: hidden;
}

.tabulator .tabulator-header .tabulator-header-contents .tabulator-headers {
  display: inline-block;
}

.tabulator .tabulator-header .tabulator-col {
  display: inline-flex;
  position: relative;
  box-sizing: border-box;
  flex-direction: column;
  justify-content: flex-start;
  border-right: 1px solid #ddd;
  background: #f9fafb;
  text-align: left;
  vertical-align: bottom;
  overflow: hidden;
}

.tabulator .tabulator-header .tabulator-col.tabulator-moving {
  position: absolute;
  border: 1px solid #999;
  background: #dae1e7;
  pointer-events: none;
}

.tabulator .tabulator-header .tabulator-col.tabulator-range-highlight {
  background-color: #d6d6d6;
  color: #000000;
}

.tabulator .tabulator-header .tabulator-col.tabulator-range-selected {
  background-color: #3876ca;
  color: #ffffff;
}

.tabulator .tabulator-header .tabulator-col .tabulator-col-content {
  box-sizing: border-box;
  position: relative;
  padding: 4px;
}

.tabulator
  .tabulator-header
  .tabulator-col
  .tabulator-col-content
  .tabulator-header-popup-button {
  padding: 0 8px;
}

.tabulator
  .tabulator-header
  .tabulator-col
  .tabulator-col-content
  .tabulator-header-popup-button:hover {
  cursor: pointer;
  opacity: 0.6;
}

.tabulator
  .tabulator-header
  .tabulator-col
  .tabulator-col-content
  .tabulator-col-title-holder {
  position: relative;
}

.tabulator
  .tabulator-header
  .tabulator-col
  .tabulator-col-content
  .tabulator-col-title {
  box-sizing: border-box;
  width: 100%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  vertical-align: bottom;
}

.tabulator
  .tabulator-header
  .tabulator-col
  .tabulator-col-content
  .tabulator-col-title.tabulator-col-title-wrap {
  white-space: normal;
  text-overflow: initial;
}

.tabulator
  .tabulator-header
  .tabulator-col
  .tabulator-col-content
  .tabulator-col-title
  .tabulator-title-editor {
  box-sizing: border-box;
  width: 100%;
  border: 1px solid #999;
  padding: 1px;
  background: #fff;
}

.tabulator
  .tabulator-header
  .tabulator-col
  .tabulator-col-content
  .tabulator-col-title
  .tabulator-header-popup-button
  + .tabulator-title-editor {
  width: calc(100% - 22px);
}

.tabulator
  .tabulator-header
  .tabulator-col
  .tabulator-col-content
  .tabulator-col-sorter {
  display: flex;
  align-items: center;
  position: absolute;
  top: 0;
  bottom: 0;
  right: 4px;
}

.tabulator
  .tabulator-header
  .tabulator-col
  .tabulator-col-content
  .tabulator-col-sorter
  .tabulator-arrow {
  width: 0;
  height: 0;
  border-left: 6px solid transparent;
  border-right: 6px solid transparent;
  border-bottom: 6px solid #bbb;
}

.tabulator
  .tabulator-header
  .tabulator-col.tabulator-col-group
  .tabulator-col-group-cols {
  position: relative;
  display: flex;
  border-top: 1px solid #ddd;
  overflow: hidden;
  margin-right: -1px;
}

.tabulator .tabulator-header .tabulator-col .tabulator-header-filter {
  position: relative;
  box-sizing: border-box;
  margin-top: 2px;
  width: 100%;
  text-align: center;
}

.tabulator .tabulator-header .tabulator-col .tabulator-header-filter textarea {
  height: auto !important;
}

.tabulator .tabulator-header .tabulator-col .tabulator-header-filter svg {
  margin-top: 3px;
}

.tabulator
  .tabulator-header
  .tabulator-col
  .tabulator-header-filter
  input::-ms-clear {
  width: 0;
  height: 0;
}

.tabulator
  .tabulator-header
  .tabulator-col.tabulator-sortable
  .tabulator-col-title {
  padding-right: 25px;
}

@media (hover: hover) and (pointer: fine) {
  .tabulator
    .tabulator-header
    .tabulator-col.tabulator-sortable.tabulator-col-sorter-element:hover {
    cursor: pointer;
    background-color: #dae1e7;
  }
}

.tabulator
  .tabulator-header
  .tabulator-col.tabulator-sortable[aria-sort="none"]
  .tabulator-col-content
  .tabulator-col-sorter {
  color: #bbb;
}

@media (hover: hover) and (pointer: fine) {
  .tabulator
    .tabulator-header
    .tabulator-col.tabulator-sortable[aria-sort="none"]
    .tabulator-col-content
    .tabulator-col-sorter.tabulator-col-sorter-element
    .tabulator-arrow:hover {
    cursor: pointer;
    border-bottom: 6px solid #555;
  }
}

.tabulator
  .tabulator-header
  .tabulator-col.tabulator-sortable[aria-sort="none"]
  .tabulator-col-content
  .tabulator-col-sorter
  .tabulator-arrow {
  border-top: none;
  border-bottom: 6px solid #bbb;
}

.tabulator
  .tabulator-header
  .tabulator-col.tabulator-sortable[aria-sort="ascending"]
  .tabulator-col-content
  .tabulator-col-sorter {
  color: #666;
}

@media (hover: hover) and (pointer: fine) {
  .tabulator
    .tabulator-header
    .tabulator-col.tabulator-sortable[aria-sort="ascending"]
    .tabulator-col-content
    .tabulator-col-sorter.tabulator-col-sorter-element
    .tabulator-arrow:hover {
    cursor: pointer;
    border-bottom: 6px solid #555;
  }
}

.tabulator
  .tabulator-header
  .tabulator-col.tabulator-sortable[aria-sort="ascending"]
  .tabulator-col-content
  .tabulator-col-sorter
  .tabulator-arrow {
  border-top: none;
  border-bottom: 6px solid #666;
}

.tabulator
  .tabulator-header
  .tabulator-col.tabulator-sortable[aria-sort="descending"]
  .tabulator-col-content
  .tabulator-col-sorter {
  color: #666;
}

@media (hover: hover) and (pointer: fine) {
  .tabulator
    .tabulator-header
    .tabulator-col.tabulator-sortable[aria-sort="descending"]
    .tabulator-col-content
    .tabulator-col-sorter.tabulator-col-sorter-element
    .tabulator-arrow:hover {
    cursor: pointer;
    border-top: 6px solid #555;
  }
}

.tabulator
  .tabulator-header
  .tabulator-col.tabulator-sortable[aria-sort="descending"]
  .tabulator-col-content
  .tabulator-col-sorter
  .tabulator-arrow {
  border-bottom: none;
  border-top: 6px solid #666;
  color: #666;
}

.tabulator
  .tabulator-header
  .tabulator-col.tabulator-col-vertical
  .tabulator-col-content
  .tabulator-col-title {
  writing-mode: vertical-rl;
  text-orientation: mixed;
  display: flex;
  align-items: center;
  justify-content: center;
}

.tabulator
  .tabulator-header
  .tabulator-col.tabulator-col-vertical.tabulator-col-vertical-flip
  .tabulator-col-title {
  transform: rotate(180deg);
}

.tabulator
  .tabulator-header
  .tabulator-col.tabulator-col-vertical.tabulator-sortable
  .tabulator-col-title {
  padding-right: 0;
  padding-top: 20px;
}

.tabulator
  .tabulator-header
  .tabulator-col.tabulator-col-vertical.tabulator-sortable.tabulator-col-vertical-flip
  .tabulator-col-title {
  padding-right: 0;
  padding-bottom: 20px;
}

.tabulator
  .tabulator-header
  .tabulator-col.tabulator-col-vertical.tabulator-sortable
  .tabulator-col-sorter {
  justify-content: center;
  left: 0;
  right: 0;
  top: 4px;
  bottom: auto;
}

.tabulator .tabulator-header .tabulator-frozen {
  position: sticky;
  left: 0;
  z-index: 11;
}

.tabulator .tabulator-header .tabulator-frozen.tabulator-frozen-left {
  border-right: 2px solid #ddd;
}

.tabulator .tabulator-header .tabulator-frozen.tabulator-frozen-right {
  border-left: 2px solid #ddd;
}

.tabulator .tabulator-header .tabulator-calcs-holder {
  box-sizing: border-box;
  display: inline-block;
  background: white !important;
  border-top: 1px solid #ddd;
  border-bottom: 1px solid #ddd;
}

.tabulator .tabulator-header .tabulator-calcs-holder .tabulator-row {
  background: white !important;
}

.tabulator
  .tabulator-header
  .tabulator-calcs-holder
  .tabulator-row
  .tabulator-col-resize-handle {
  display: none;
}

.tabulator .tabulator-header .tabulator-frozen-rows-holder {
  display: inline-block;
}

.tabulator .tabulator-header .tabulator-frozen-rows-holder:empty {
  display: none;
}

.tabulator .tabulator-tableholder {
  position: relative;
  width: 100%;
  white-space: nowrap;
  overflow: auto;
  -webkit-overflow-scrolling: touch;
}

.tabulator .tabulator-tableholder:focus {
  outline: none;
}

.tabulator .tabulator-tableholder .tabulator-placeholder {
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 100%;
  width: 100%;
}

.tabulator
  .tabulator-tableholder
  .tabulator-placeholder[tabulator-render-mode="virtual"] {
  min-height: 100%;
}

.tabulator
  .tabulator-tableholder
  .tabulator-placeholder
  .tabulator-placeholder-contents {
  display: inline-block;
  text-align: center;
  padding: 10px;
  color: #ccc;
  font-weight: bold;
  font-size: 20px;
  white-space: normal;
}

.tabulator .tabulator-tableholder .tabulator-table {
  position: relative;
  display: inline-block;
  background-color: #fff;
  white-space: nowrap;
  overflow: visible;
  color: #333;
}

.tabulator
  .tabulator-tableholder
  .tabulator-table
  .tabulator-row.tabulator-calcs {
  font-weight: bold;
  background: #e2e2e2 !important;
}

.tabulator
  .tabulator-tableholder
  .tabulator-table
  .tabulator-row.tabulator-calcs.tabulator-calcs-top {
  border-bottom: 2px solid #ddd;
}

.tabulator
  .tabulator-tableholder
  .tabulator-table
  .tabulator-row.tabulator-calcs.tabulator-calcs-bottom {
  border-top: 2px solid #ddd;
}

.tabulator .tabulator-tableholder .tabulator-range-overlay {
  position: absolute;
  inset: 0;
  z-index: 10;
  pointer-events: none;
}

.tabulator .tabulator-tableholder .tabulator-range-overlay .tabulator-range {
  position: absolute;
  box-sizing: border-box;
  border: 1px solid #2975dd;
}

.tabulator
  .tabulator-tableholder
  .tabulator-range-overlay
  .tabulator-range.tabulator-range-active::after {
  content: "";
  position: absolute;
  right: -3px;
  bottom: -3px;
  width: 6px;
  height: 6px;
  background-color: #2975dd;
  border-radius: 999px;
}

.tabulator
  .tabulator-tableholder
  .tabulator-range-overlay
  .tabulator-range-cell-active {
  position: absolute;
  box-sizing: border-box;
  border: 2px solid #2975dd;
}

.tabulator .tabulator-footer {
  border-top: 1px solid #999;
  background-color: #fff;
  color: #555;
  font-weight: bold;
  white-space: nowrap;
  user-select: none;
  -moz-user-select: none;
  -khtml-user-select: none;
  -webkit-user-select: none;
  -o-user-select: none;
}

.tabulator .tabulator-footer .tabulator-footer-contents {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  padding: 5px 10px;
}

.tabulator .tabulator-footer .tabulator-footer-contents:empty {
  display: none;
}

.tabulator .tabulator-footer .tabulator-spreadsheet-tabs {
  margin-top: -5px;
  overflow-x: auto;
}

.tabulator
  .tabulator-footer
  .tabulator-spreadsheet-tabs
  .tabulator-spreadsheet-tab {
  display: inline-block;
  padding: 5px;
  border: rgba(34, 36, 38, 0.15) 1px solid;
  border-top: none;
  border-bottom-left-radius: 5px;
  border-bottom-right-radius: 5px;
  font-size: 0.9em;
}

.tabulator
  .tabulator-footer
  .tabulator-spreadsheet-tabs
  .tabulator-spreadsheet-tab:hover {
  cursor: pointer;
  opacity: 0.7;
}

.tabulator
  .tabulator-footer
  .tabulator-spreadsheet-tabs
  .tabulator-spreadsheet-tab.tabulator-spreadsheet-tab-active {
  background: #fff;
}

.tabulator .tabulator-footer .tabulator-calcs-holder {
  box-sizing: border-box;
  width: 100%;
  text-align: left;
  background: white !important;
  border-bottom: 1px solid #ddd;
  border-top: 1px solid #ddd;
  overflow: hidden;
}

.tabulator .tabulator-footer .tabulator-calcs-holder .tabulator-row {
  display: inline-block;
  background: white !important;
}

.tabulator
  .tabulator-footer
  .tabulator-calcs-holder
  .tabulator-row
  .tabulator-col-resize-handle {
  display: none;
}

.tabulator .tabulator-footer .tabulator-calcs-holder:only-child {
  margin-bottom: -5px;
  border-bottom: none;
}

.tabulator .tabulator-footer > * + .tabulator-page-counter {
  margin-left: 10px;
}

.tabulator .tabulator-footer .tabulator-page-counter {
  font-weight: normal;
}

.tabulator .tabulator-footer .tabulator-paginator {
  flex: 1;
  text-align: right;
  color: #555;
  font-family: inherit;
  font-weight: inherit;
  font-size: inherit;
}

.tabulator .tabulator-footer .tabulator-page-size {
  display: inline-block;
  margin: 0 5px;
  padding: 2px 5px;
  border: 1px solid #aaa;
  border-radius: 3px;
}

.tabulator .tabulator-footer .tabulator-pages {
  margin: 0 7px;
}

.tabulator .tabulator-footer .tabulator-page {
  display: inline-block;
  margin: 0 2px;
  padding: 2px 5px;
  border: 1px solid #aaa;
  border-radius: 3px;
  background: rgba(255, 255, 255, 0.2);
}

.tabulator .tabulator-footer .tabulator-page.active {
  color: #d00;
}

.tabulator .tabulator-footer .tabulator-page:disabled {
  opacity: 0.5;
}

@media (hover: hover) and (pointer: fine) {
  .tabulator .tabulator-footer .tabulator-page:not(disabled):hover {
    cursor: pointer;
    background: rgba(0, 0, 0, 0.2);
    color: #fff;
  }
}

.tabulator .tabulator-col-resize-handle {
  position: relative;
  display: inline-block;
  width: 6px;
  margin-left: -3px;
  margin-right: -3px;
  z-index: 11;
  vertical-align: middle;
}

@media (hover: hover) and (pointer: fine) {
  .tabulator .tabulator-col-resize-handle:hover {
    cursor: ew-resize;
  }
}

.tabulator .tabulator-col-resize-handle:last-of-type {
  width: 3px;
  margin-right: 0;
}

.tabulator .tabulator-col-resize-guide {
  position: absolute;
  top: 0;
  width: 4px;
  height: 100%;
  margin-left: -0.5px;
  background-color: #999;
  opacity: 0.5;
}

.tabulator .tabulator-row-resize-guide {
  position: absolute;
  left: 0;
  width: 100%;
  height: 4px;
  margin-top: -0.5px;
  background-color: #999;
  opacity: 0.5;
}

.tabulator .tabulator-alert {
  position: absolute;
  display: flex;
  align-items: center;
  top: 0;
  left: 0;
  z-index: 100;
  height: 100%;
  width: 100%;
  background: rgba(0, 0, 0, 0.4);
  text-align: center;
}

.tabulator .tabulator-alert .tabulator-alert-msg {
  display: inline-block;
  margin: 0 auto;
  padding: 10px 20px;
  border-radius: 10px;
  background: #fff;
  font-weight: bold;
  font-size: 16px;
}

.tabulator .tabulator-alert .tabulator-alert-msg.tabulator-alert-state-msg {
  border: 4px solid #333;
  color: #000;
}

.tabulator .tabulator-alert .tabulator-alert-msg.tabulator-alert-state-error {
  border: 4px solid #d00;
  color: #590000;
}

.tabulator-row {
  position: relative;
  box-sizing: border-box;
  min-height: 22px;
  background-color: #fff;
}

.tabulator-row.tabulator-row-even {
  background-color: #efefef;
}

@media (hover: hover) and (pointer: fine) {
  .tabulator-row.tabulator-selectable:hover {
    background-color: #bbb;
    cursor: pointer;
  }
}

.tabulator-row.tabulator-selected {
  background-color: #9abcea;
}

@media (hover: hover) and (pointer: fine) {
  .tabulator-row.tabulator-selected:hover {
    background-color: #769bcc;
    cursor: pointer;
  }
}

.tabulator-row.tabulator-row-moving {
  border: 1px solid #000;
  background: #fff;
}

.tabulator-row.tabulator-moving {
  position: absolute;
  border-top: 1px solid #ddd;
  border-bottom: 1px solid #ddd;
  pointer-events: none;
  z-index: 15;
}

.tabulator-row.tabulator-range-highlight
  .tabulator-cell.tabulator-range-row-header {
  background-color: #d6d6d6;
  color: #000000;
}

.tabulator-row.tabulator-range-highlight.tabulator-range-selected
  .tabulator-cell.tabulator-range-row-header {
  background-color: #3876ca;
  color: #ffffff;
}

.tabulator-row.tabulator-range-selected
  .tabulator-cell.tabulator-range-row-header {
  background-color: #3876ca;
  color: #ffffff;
}

.tabulator-row .tabulator-row-resize-handle {
  position: absolute;
  right: 0;
  bottom: 0;
  left: 0;
  height: 5px;
}

.tabulator-row .tabulator-row-resize-handle.prev {
  top: 0;
  bottom: auto;
}

@media (hover: hover) and (pointer: fine) {
  .tabulator-row .tabulator-row-resize-handle:hover {
    cursor: ns-resize;
  }
}

.tabulator-row .tabulator-responsive-collapse {
  box-sizing: border-box;
  padding: 5px;
  border-top: 1px solid #ddd;
  border-bottom: 1px solid #ddd;
}

.tabulator-row .tabulator-responsive-collapse:empty {
  display: none;
}

.tabulator-row .tabulator-responsive-collapse table {
  font-size: 14px;
}

.tabulator-row .tabulator-responsive-collapse table tr td {
  position: relative;
}

.tabulator-row .tabulator-responsive-collapse table tr td:first-of-type {
  padding-right: 10px;
}

.tabulator-row .tabulator-cell {
  display: inline-block;
  position: relative;
  box-sizing: border-box;
  padding: 4px;
  border-right: 1px solid #ddd;
  vertical-align: middle;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  outline: none;
}

.tabulator-row .tabulator-cell.tabulator-row-header {
  border-right: 1px solid rgba(34, 36, 38, 0.15);
  border-bottom: 1px solid #ddd;
  background: #f9fafb;
}

.tabulator-row .tabulator-cell.tabulator-frozen {
  display: inline-block;
  position: sticky;
  left: 0;
  background-color: inherit;
  z-index: 11;
}

.tabulator-row .tabulator-cell.tabulator-frozen.tabulator-frozen-left {
  border-right: 2px solid #ddd;
}

.tabulator-row .tabulator-cell.tabulator-frozen.tabulator-frozen-right {
  border-left: 2px solid #ddd;
}

.tabulator-row .tabulator-cell.tabulator-editing {
  border: 1px solid #1d68cd;
  outline: none;
  padding: 0;
}

.tabulator-row .tabulator-cell.tabulator-editing input,
.tabulator-row .tabulator-cell.tabulator-editing select {
  border: 1px;
  background: transparent;
  outline: none;
}

.tabulator-row .tabulator-cell.tabulator-validation-fail {
  border: 1px solid #db2828;
}

.tabulator-row .tabulator-cell.tabulator-validation-fail input,
.tabulator-row .tabulator-cell.tabulator-validation-fail select {
  border: 1px;
  background: transparent;
  color: #db2828;
}

.tabulator-row .tabulator-cell.tabulator-row-handle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  -moz-user-select: none;
  -khtml-user-select: none;
  -webkit-user-select: none;
  -o-user-select: none;
}

.tabulator-row .tabulator-cell.tabulator-row-handle .tabulator-row-handle-box {
  width: 80%;
}

.tabulator-row
  .tabulator-cell.tabulator-row-handle
  .tabulator-row-handle-box
  .tabulator-row-handle-bar {
  width: 100%;
  height: 3px;
  margin-top: 2px;
  background: #666;
}

.tabulator-row
  .tabulator-cell.tabulator-range-selected:not(
    .tabulator-range-only-cell-selected
  ):not(.tabulator-range-row-header) {
  background-color: #9abcea;
}

.tabulator-row .tabulator-cell .tabulator-data-tree-branch-empty {
  display: inline-block;
  width: 7px;
}

.tabulator-row .tabulator-cell .tabulator-data-tree-branch {
  display: inline-block;
  vertical-align: middle;
  height: 9px;
  width: 7px;
  margin-top: -9px;
  margin-right: 5px;
  border-bottom-left-radius: 1px;
  border-left: 2px solid #ddd;
  border-bottom: 2px solid #ddd;
}

.tabulator-row .tabulator-cell .tabulator-data-tree-control {
  display: inline-flex;
  justify-content: center;
  align-items: center;
  vertical-align: middle;
  height: 11px;
  width: 11px;
  margin-right: 5px;
  border: 1px solid #333;
  border-radius: 2px;
  background: rgba(0, 0, 0, 0.1);
  overflow: hidden;
}

@media (hover: hover) and (pointer: fine) {
  .tabulator-row .tabulator-cell .tabulator-data-tree-control:hover {
    cursor: pointer;
    background: rgba(0, 0, 0, 0.2);
  }
}

.tabulator-row
  .tabulator-cell
  .tabulator-data-tree-control
  .tabulator-data-tree-control-collapse {
  display: inline-block;
  position: relative;
  height: 7px;
  width: 1px;
  background: transparent;
}

.tabulator-row
  .tabulator-cell
  .tabulator-data-tree-control
  .tabulator-data-tree-control-collapse:after {
  position: absolute;
  content: "";
  left: -3px;
  top: 3px;
  height: 1px;
  width: 7px;
  background: #333;
}

.tabulator-row
  .tabulator-cell
  .tabulator-data-tree-control
  .tabulator-data-tree-control-expand {
  display: inline-block;
  position: relative;
  height: 7px;
  width: 1px;
  background: #333;
}

.tabulator-row
  .tabulator-cell
  .tabulator-data-tree-control
  .tabulator-data-tree-control-expand:after {
  position: absolute;
  content: "";
  left: -3px;
  top: 3px;
  height: 1px;
  width: 7px;
  background: #333;
}

.tabulator-row .tabulator-cell .tabulator-responsive-collapse-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  -moz-user-select: none;
  -khtml-user-select: none;
  -webkit-user-select: none;
  -o-user-select: none;
  height: 15px;
  width: 15px;
  border-radius: 20px;
  background: #666;
  color: #fff;
  font-weight: bold;
  font-size: 1.1em;
}

@media (hover: hover) and (pointer: fine) {
  .tabulator-row .tabulator-cell .tabulator-responsive-collapse-toggle:hover {
    opacity: 0.7;
    cursor: pointer;
  }
}

.tabulator-row
  .tabulator-cell
  .tabulator-responsive-collapse-toggle.open
  .tabulator-responsive-collapse-toggle-close {
  display: initial;
}

.tabulator-row
  .tabulator-cell
  .tabulator-responsive-collapse-toggle.open
  .tabulator-responsive-collapse-toggle-open {
  display: none;
}

.tabulator-row .tabulator-cell .tabulator-responsive-collapse-toggle svg {
  stroke: #fff;
}

.tabulator-row
  .tabulator-cell
  .tabulator-responsive-collapse-toggle
  .tabulator-responsive-collapse-toggle-close {
  display: none;
}

.tabulator-row .tabulator-cell .tabulator-traffic-light {
  display: inline-block;
  height: 14px;
  width: 14px;
  border-radius: 14px;
}

.tabulator-row.tabulator-group {
  box-sizing: border-box;
  border-bottom: 1px solid #999;
  border-right: 1px solid #ddd;
  border-top: 1px solid #999;
  padding: 5px;
  padding-left: 10px;
  background: #ccc;
  font-weight: bold;
  min-width: 100%;
}

@media (hover: hover) and (pointer: fine) {
  .tabulator-row.tabulator-group:hover {
    cursor: pointer;
    background-color: rgba(0, 0, 0, 0.1);
  }
}

.tabulator-row.tabulator-group.tabulator-group-visible .tabulator-arrow {
  margin-right: 10px;
  border-left: 6px solid transparent;
  border-right: 6px solid transparent;
  border-top: 6px solid #666;
  border-bottom: 0;
}

.tabulator-row.tabulator-group.tabulator-group-level-1 {
  padding-left: 30px;
}

.tabulator-row.tabulator-group.tabulator-group-level-2 {
  padding-left: 50px;
}

.tabulator-row.tabulator-group.tabulator-group-level-3 {
  padding-left: 70px;
}

.tabulator-row.tabulator-group.tabulator-group-level-4 {
  padding-left: 90px;
}

.tabulator-row.tabulator-group.tabulator-group-level-5 {
  padding-left: 110px;
}

.tabulator-row.tabulator-group .tabulator-group-toggle {
  display: inline-block;
}

.tabulator-row.tabulator-group .tabulator-arrow {
  display: inline-block;
  width: 0;
  height: 0;
  margin-right: 16px;
  border-top: 6px solid transparent;
  border-bottom: 6px solid transparent;
  border-right: 0;
  border-left: 6px solid #666;
  vertical-align: middle;
}

.tabulator-row.tabulator-group span {
  margin-left: 10px;
  color: #d00;
}

.tabulator-toggle {
  box-sizing: border-box;
  display: flex;
  flex-direction: row;
  border: 1px solid #ccc;
  background: #dcdcdc;
}

.tabulator-toggle.tabulator-toggle-on {
  background: #1c6cc2;
}

.tabulator-toggle .tabulator-toggle-switch {
  box-sizing: border-box;
  border: 1px solid #ccc;
  background: #fff;
}

.tabulator-popup-container {
  position: absolute;
  display: inline-block;
  box-sizing: border-box;
  background: #fff;
  border: 1px solid #ddd;
  box-shadow: 0 0 5px 0 rgba(0, 0, 0, 0.2);
  font-size: 14px;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  z-index: 10000;
}

.tabulator-popup {
  padding: 5px;
  border-radius: 3px;
}

.tabulator-tooltip {
  max-width: Min(500px, 100%);
  padding: 3px 5px;
  border-radius: 2px;
  box-shadow: none;
  font-size: 12px;
  pointer-events: none;
}

.tabulator-menu .tabulator-menu-item {
  position: relative;
  box-sizing: border-box;
  padding: 5px 10px;
  user-select: none;
}

.tabulator-menu .tabulator-menu-item.tabulator-menu-item-disabled {
  opacity: 0.5;
}

@media (hover: hover) and (pointer: fine) {
  .tabulator-menu
    .tabulator-menu-item:not(.tabulator-menu-item-disabled):hover {
    cursor: pointer;
    background: #efefef;
  }
}

.tabulator-menu .tabulator-menu-item.tabulator-menu-item-submenu {
  padding-right: 25px;
}

.tabulator-menu .tabulator-menu-item.tabulator-menu-item-submenu::after {
  display: inline-block;
  position: absolute;
  top: calc(5px + 0.4em);
  right: 10px;
  height: 7px;
  width: 7px;
  content: "";
  border-width: 1px 1px 0 0;
  border-style: solid;
  border-color: #ddd;
  vertical-align: top;
  transform: rotate(45deg);
}

.tabulator-menu .tabulator-menu-separator {
  border-top: 1px solid #ddd;
}

.tabulator-edit-list {
  max-height: 200px;
  font-size: 14px;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
}

.tabulator-edit-list .tabulator-edit-list-item {
  padding: 4px;
  color: #333;
  outline: none;
}

.tabulator-edit-list .tabulator-edit-list-item.active {
  color: #fff;
  background: #1d68cd;
}

.tabulator-edit-list .tabulator-edit-list-item.active.focused {
  outline: 1px solid rgba(255, 255, 255, 0.5);
}

.tabulator-edit-list .tabulator-edit-list-item.focused {
  outline: 1px solid #1d68cd;
}

@media (hover: hover) and (pointer: fine) {
  .tabulator-edit-list .tabulator-edit-list-item:hover {
    cursor: pointer;
    color: #fff;
    background: #1d68cd;
  }
}

.tabulator-edit-list .tabulator-edit-list-placeholder {
  padding: 4px;
  color: #333;
  text-align: center;
}

.tabulator-edit-list .tabulator-edit-list-group {
  border-bottom: 1px solid #ddd;
  padding: 4px;
  padding-top: 6px;
  color: #333;
  font-weight: bold;
}

.tabulator-edit-list
  .tabulator-edit-list-item.tabulator-edit-list-group-level-2,
.tabulator-edit-list
  .tabulator-edit-list-group.tabulator-edit-list-group-level-2 {
  padding-left: 12px;
}

.tabulator-edit-list
  .tabulator-edit-list-item.tabulator-edit-list-group-level-3,
.tabulator-edit-list
  .tabulator-edit-list-group.tabulator-edit-list-group-level-3 {
  padding-left: 20px;
}

.tabulator-edit-list
  .tabulator-edit-list-item.tabulator-edit-list-group-level-4,
.tabulator-edit-list
  .tabulator-edit-list-group.tabulator-edit-list-group-level-4 {
  padding-left: 28px;
}

.tabulator-edit-list
  .tabulator-edit-list-item.tabulator-edit-list-group-level-5,
.tabulator-edit-list
  .tabulator-edit-list-group.tabulator-edit-list-group-level-5 {
  padding-left: 36px;
}

.tabulator.tabulator-ltr {
  direction: ltr;
}

.tabulator.tabulator-rtl {
  text-align: initial;
  direction: rtl;
}

.tabulator.tabulator-rtl .tabulator-header .tabulator-col {
  text-align: initial;
  border-left: 1px solid #ddd;
  border-right: initial;
}

.tabulator.tabulator-rtl
  .tabulator-header
  .tabulator-col.tabulator-col-group
  .tabulator-col-group-cols {
  margin-right: initial;
  margin-left: -1px;
}

.tabulator.tabulator-rtl
  .tabulator-header
  .tabulator-col.tabulator-sortable
  .tabulator-col-title {
  padding-right: 0;
  padding-left: 25px;
}

.tabulator.tabulator-rtl
  .tabulator-header
  .tabulator-col
  .tabulator-col-content
  .tabulator-col-sorter {
  left: 8px;
  right: initial;
}

.tabulator.tabulator-rtl
  .tabulator-tableholder
  .tabulator-range-overlay
  .tabulator-range.tabulator-range-active::after {
  content: "";
  position: absolute;
  left: -3px;
  right: initial;
  bottom: -3px;
  width: 6px;
  height: 6px;
  background-color: #2975dd;
  border-radius: 999px;
}

.tabulator.tabulator-rtl .tabulator-row .tabulator-cell {
  border-right: initial;
  border-left: 1px solid #ddd;
}

.tabulator.tabulator-rtl
  .tabulator-row
  .tabulator-cell
  .tabulator-data-tree-branch {
  margin-right: initial;
  margin-left: 5px;
  border-bottom-left-radius: initial;
  border-bottom-right-radius: 1px;
  border-left: initial;
  border-right: 2px solid #ddd;
}

.tabulator.tabulator-rtl
  .tabulator-row
  .tabulator-cell
  .tabulator-data-tree-control {
  margin-right: initial;
  margin-left: 5px;
}

.tabulator.tabulator-rtl
  .tabulator-row
  .tabulator-cell.tabulator-frozen.tabulator-frozen-left {
  border-left: 2px solid #ddd;
}

.tabulator.tabulator-rtl
  .tabulator-row
  .tabulator-cell.tabulator-frozen.tabulator-frozen-right {
  border-right: 2px solid #ddd;
}

.tabulator.tabulator-rtl
  .tabulator-row
  .tabulator-col-resize-handle:last-of-type {
  width: 3px;
  margin-left: 0;
  margin-right: -3px;
}

.tabulator.tabulator-rtl .tabulator-footer .tabulator-calcs-holder {
  text-align: initial;
}

.tabulator-print-fullscreen {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 10000;
}

body.tabulator-print-fullscreen-hide > *:not(.tabulator-print-fullscreen) {
  display: none !important;
}

.tabulator-print-table {
  border-collapse: collapse;
}

.tabulator-print-table .tabulator-data-tree-branch {
  display: inline-block;
  vertical-align: middle;
  height: 9px;
  width: 7px;
  margin-top: -9px;
  margin-right: 5px;
  border-bottom-left-radius: 1px;
  border-left: 2px solid #ddd;
  border-bottom: 2px solid #ddd;
}

.tabulator-print-table .tabulator-print-table-group {
  box-sizing: border-box;
  border-bottom: 1px solid #999;
  border-right: 1px solid #ddd;
  border-top: 1px solid #999;
  padding: 5px;
  padding-left: 10px;
  background: #ccc;
  font-weight: bold;
  min-width: 100%;
}

@media (hover: hover) and (pointer: fine) {
  .tabulator-print-table .tabulator-print-table-group:hover {
    cursor: pointer;
    background-color: rgba(0, 0, 0, 0.1);
  }
}

.tabulator-print-table
  .tabulator-print-table-group.tabulator-group-visible
  .tabulator-arrow {
  margin-right: 10px;
  border-left: 6px solid transparent;
  border-right: 6px solid transparent;
  border-top: 6px solid #666;
  border-bottom: 0;
}

.tabulator-print-table .tabulator-print-table-group.tabulator-group-level-1 td {
  padding-left: 30px !important;
}

.tabulator-print-table .tabulator-print-table-group.tabulator-group-level-2 td {
  padding-left: 50px !important;
}

.tabulator-print-table .tabulator-print-table-group.tabulator-group-level-3 td {
  padding-left: 70px !important;
}

.tabulator-print-table .tabulator-print-table-group.tabulator-group-level-4 td {
  padding-left: 90px !important;
}

.tabulator-print-table .tabulator-print-table-group.tabulator-group-level-5 td {
  padding-left: 110px !important;
}

.tabulator-print-table .tabulator-print-table-group .tabulator-group-toggle {
  display: inline-block;
}

.tabulator-print-table .tabulator-print-table-group .tabulator-arrow {
  display: inline-block;
  width: 0;
  height: 0;
  margin-right: 16px;
  border-top: 6px solid transparent;
  border-bottom: 6px solid transparent;
  border-right: 0;
  border-left: 6px solid #666;
  vertical-align: middle;
}

.tabulator-print-table .tabulator-print-table-group span {
  margin-left: 10px;
  color: #d00;
}

.tabulator-print-table .tabulator-data-tree-control {
  display: inline-flex;
  justify-content: center;
  align-items: center;
  vertical-align: middle;
  height: 11px;
  width: 11px;
  margin-right: 5px;
  border: 1px solid #333;
  border-radius: 2px;
  background: rgba(0, 0, 0, 0.1);
  overflow: hidden;
}

@media (hover: hover) and (pointer: fine) {
  .tabulator-print-table .tabulator-data-tree-control:hover {
    cursor: pointer;
    background: rgba(0, 0, 0, 0.2);
  }
}

.tabulator-print-table
  .tabulator-data-tree-control
  .tabulator-data-tree-control-collapse {
  display: inline-block;
  position: relative;
  height: 7px;
  width: 1px;
  background: transparent;
}

.tabulator-print-table
  .tabulator-data-tree-control
  .tabulator-data-tree-control-collapse:after {
  position: absolute;
  content: "";
  left: -3px;
  top: 3px;
  height: 1px;
  width: 7px;
  background: #333;
}

.tabulator-print-table
  .tabulator-data-tree-control
  .tabulator-data-tree-control-expand {
  display: inline-block;
  position: relative;
  height: 7px;
  width: 1px;
  background: #333;
}

.tabulator-print-table
  .tabulator-data-tree-control
  .tabulator-data-tree-control-expand:after {
  position: absolute;
  content: "";
  left: -3px;
  top: 3px;
  height: 1px;
  width: 7px;
  background: #333;
}

.tabulator {
  width: 100%;
  margin: 1em 0em;
  border: 1px solid rgba(34, 36, 38, 0.15);
  box-shadow: none;
  border-radius: 0.28571rem;
  color: rgba(0, 0, 0, 0.87);
  /* Red */
  /* Orange */
  /* Yellow */
  /* Olive */
  /* Green */
  /* Teal */
  /* Blue */
  /* Violet */
  /* Purple */
  /* Pink */
  /* Brown */
  /* Grey */
  /* Black */
}

.tabulator .tabulator-header {
  border-right: none;
  border-bottom: 1px solid rgba(34, 36, 38, 0.1);
  background-color: #f9fafb;
  box-shadow: none;
  color: rgba(0, 0, 0, 0.87);
  font-style: none;
  font-weight: bold;
  text-transform: none;
}

.tabulator .tabulator-header .tabulator-col {
  border-right: none;
  background-color: #f9fafb;
}

.tabulator .tabulator-header .tabulator-col .tabulator-col-content {
  padding: 0.92857em 0.78571em;
}

.tabulator .tabulator-tableholder .tabulator-table {
  background-color: transparent;
}

.tabulator
  .tabulator-tableholder
  .tabulator-table
  .tabulator-row.tabulator-calcs {
  background: #f2f2f2 !important;
}

.tabulator
  .tabulator-tableholder
  .tabulator-table
  .tabulator-row.tabulator-calcs.tabulator-calcs-top {
  border-bottom: 2px solid #ddd;
}

.tabulator
  .tabulator-tableholder
  .tabulator-table
  .tabulator-row.tabulator-calcs.tabulator-calcs-bottom {
  border-top: 2px solid #ddd;
}

.tabulator .tabulator-footer {
  padding: 0.78571em 0.78571em;
  border-top: 1px solid rgba(34, 36, 38, 0.15);
  box-shadow: none;
  background: #f9fafb;
  text-align: right;
  color: rgba(0, 0, 0, 0.87);
  font-style: normal;
  font-weight: normal;
  text-transform: none;
}

.tabulator .tabulator-footer .tabulator-calcs-holder {
  margin: -0.78571em -0.78571em 0.78571em -0.78571em;
  background: white !important;
}

.tabulator .tabulator-footer .tabulator-calcs-holder .tabulator-row {
  background: white !important;
}

.tabulator .tabulator-footer .tabulator-calcs-holder:only-child {
  margin-bottom: -0.78571em;
  border-bottom: none;
}

.tabulator .tabulator-footer .tabulator-spreadsheet-tabs {
  margin-top: calc(-0.78571em - 5px);
}

.tabulator
  .tabulator-footer
  .tabulator-spreadsheet-tabs
  .tabulator-spreadsheet-tab.tabulator-spreadsheet-tab-active {
  color: #d00;
}

.tabulator .tabulator-tableholder .tabulator-table .tabulator-row.positive,
.tabulator
  .tabulator-tableholder
  .tabulator-table
  .tabulator-row
  .tabulator-cell.positive {
  box-shadow: 0px 0px 0px #a3c293 inset;
  background: #fcfff5 !important;
  color: #21ba45 !important;
}

@media (hover: hover) and (pointer: fine) {
  .tabulator
    .tabulator-tableholder
    .tabulator-table
    .tabulator-row.positive:hover,
  .tabulator
    .tabulator-tableholder
    .tabulator-table
    .tabulator-row
    .tabulator-cell.positive:hover {
    background: #f7ffe6 !important;
    color: #13ae38 !important;
  }
}

.tabulator .tabulator-tableholder .tabulator-table .tabulator-row.negative,
.tabulator
  .tabulator-tableholder
  .tabulator-table
  .tabulator-row
  .tabulator-cell.negative {
  box-shadow: 0px 0px 0px #e0b4b4 inset;
  background: #fff6f6 !important;
  color: #db2828 !important;
}

@media (hover: hover) and (pointer: fine) {
  .tabulator
    .tabulator-tableholder
    .tabulator-table
    .tabulator-row.negative:hover,
  .tabulator
    .tabulator-tableholder
    .tabulator-table
    .tabulator-row
    .tabulator-cell.negative:hover {
    background: #ffe7e7 !important;
    color: #d41616 !important;
  }
}

.tabulator .tabulator-tableholder .tabulator-table .tabulator-row.error,
.tabulator
  .tabulator-tableholder
  .tabulator-table
  .tabulator-row
  .tabulator-cell.error {
  box-shadow: 0px 0px 0px #e0b4b4 inset;
  background: #fff6f6 !important;
  color: #db2828 !important;
}

@media (hover: hover) and (pointer: fine) {
  .tabulator .tabulator-tableholder .tabulator-table .tabulator-row.error:hover,
  .tabulator
    .tabulator-tableholder
    .tabulator-table
    .tabulator-row
    .tabulator-cell.error:hover {
    background: #ffe7e7 !important;
    color: #d12323 !important;
  }
}

.tabulator .tabulator-tableholder .tabulator-table .tabulator-row.warning,
.tabulator
  .tabulator-tableholder
  .tabulator-table
  .tabulator-row
  .tabulator-cell.warning {
  box-shadow: 0px 0px 0px #c9ba9b inset;
  background: #fffaf3 !important;
  color: #f2c037 !important;
}

@media (hover: hover) and (pointer: fine) {
  .tabulator
    .tabulator-tableholder
    .tabulator-table
    .tabulator-row.warning:hover,
  .tabulator
    .tabulator-tableholder
    .tabulator-table
    .tabulator-row
    .tabulator-cell.warning:hover {
    background: #fff4e4 !important;
    color: #f1bb29 !important;
  }
}

.tabulator .tabulator-tableholder .tabulator-table .tabulator-row.active,
.tabulator
  .tabulator-tableholder
  .tabulator-table
  .tabulator-row
  .tabulator-cell.active {
  box-shadow: 0px 0px 0px rgba(0, 0, 0, 0.87) inset;
  background: #e0e0e0 !important;
  color: rgba(0, 0, 0, 0.87) !important;
}

@media (hover: hover) and (pointer: fine) {
  .tabulator
    .tabulator-tableholder
    .tabulator-table
    .tabulator-row.active:hover,
  .tabulator
    .tabulator-tableholder
    .tabulator-table
    .tabulator-row
    .tabulator-cell.active:hover {
    background: #f7ffe6 !important;
    color: #13ae38 !important;
  }
}

.tabulator .tabulator-tableholder .tabulator-table .tabulator-row.active,
.tabulator
  .tabulator-tableholder
  .tabulator-table
  .tabulator-row
  .tabulator-cell.active {
  pointer-events: none;
  color: rgba(0, 0, 0, 0.2);
}

@media (hover: hover) and (pointer: fine) {
  .tabulator
    .tabulator-tableholder
    .tabulator-table
    .tabulator-row.disabled:hover {
    pointer-events: none;
    color: rgba(0, 0, 0, 0.2);
  }
}

.tabulator.inverted {
  background: #333333;
  color: rgba(255, 255, 255, 0.9);
  border: none;
}

.tabulator.inverted .tabulator-header {
  background-color: rgba(0, 0, 0, 0.15);
  border-color: rgba(255, 255, 255, 0.1) !important;
  color: rgba(255, 255, 255, 0.9);
}

.tabulator.inverted .tabulator-header .tabulator-col {
  border-color: rgba(255, 255, 255, 0.1) !important;
}

.tabulator.inverted .tabulator-tableholder .tabulator-table .tabulator-row {
  color: rgba(255, 255, 255, 0.9);
  border: none;
}

.tabulator.inverted
  .tabulator-tableholder
  .tabulator-table
  .tabulator-row
  .tabulator-cell {
  border-color: rgba(255, 255, 255, 0.1) !important;
}

.tabulator.inverted .tabulator-footer {
  background: #ffffff;
}

.tabulator.striped .tabulator-row:nth-child(even) {
  background-color: #f2f2f2;
}

.tabulator.celled {
  border: 1px solid rgba(34, 36, 38, 0.15);
}

.tabulator.celled .tabulator-header .tabulator-col {
  border-right: 1px solid rgba(34, 36, 38, 0.1);
}

.tabulator.celled
  .tabulator-tableholder
  .tabulator-table
  .tabulator-row
  .tabulator-cell {
  border-right: 1px solid rgba(34, 36, 38, 0.1);
}

.tabulator[class*="single line"]
  .tabulator-tableholder
  .tabulator-table
  .tabulator-row
  .tabulator-cell {
  border-right: none;
}

.tabulator.red {
  border-top: 0.2em solid #db2828;
}

.tabulator.inverted.red {
  background-color: #db2828 !important;
  color: #ffffff !important;
}

.tabulator.orange {
  border-top: 0.2em solid #f2711c;
}

.tabulator.inverted.orange {
  background-color: #f2711c !important;
  color: #ffffff !important;
}

.tabulator.yellow {
  border-top: 0.2em solid #fbbd08;
}

.tabulator.inverted.yellow {
  background-color: #fbbd08 !important;
  color: #ffffff !important;
}

.tabulator.olive {
  border-top: 0.2em solid #b5cc18;
}

.tabulator.inverted.olive {
  background-color: #b5cc18 !important;
  color: #ffffff !important;
}

.tabulator.green {
  border-top: 0.2em solid #21ba45;
}

.tabulator.inverted.green {
  background-color: #21ba45 !important;
  color: #ffffff !important;
}

.tabulator.teal {
  border-top: 0.2em solid #00b5ad;
}

.tabulator.inverted.teal {
  background-color: #00b5ad !important;
  color: #ffffff !important;
}

.tabulator.blue {
  border-top: 0.2em solid #2185d0;
}

.tabulator.inverted.blue {
  background-color: #2185d0 !important;
  color: #ffffff !important;
}

.tabulator.violet {
  border-top: 0.2em solid #6435c9;
}

.tabulator.inverted.violet {
  background-color: #6435c9 !important;
  color: #ffffff !important;
}

.tabulator.purple {
  border-top: 0.2em solid #a333c8;
}

.tabulator.inverted.purple {
  background-color: #a333c8 !important;
  color: #ffffff !important;
}

.tabulator.pink {
  border-top: 0.2em solid #e03997;
}

.tabulator.inverted.pink {
  background-color: #e03997 !important;
  color: #ffffff !important;
}

.tabulator.brown {
  border-top: 0.2em solid #a5673f;
}

.tabulator.inverted.brown {
  background-color: #a5673f !important;
  color: #ffffff !important;
}

.tabulator.grey {
  border-top: 0.2em solid #767676;
}

.tabulator.inverted.grey {
  background-color: #767676 !important;
  color: #ffffff !important;
}

.tabulator.black {
  border-top: 0.2em solid #1b1c1d;
}

.tabulator.inverted.black {
  background-color: #1b1c1d !important;
  color: #ffffff !important;
}

.tabulator.padded .tabulator-header .tabulator-col .tabulator-col-content {
  padding: 1em 1em;
}

.tabulator.padded
  .tabulator-header
  .tabulator-col
  .tabulator-col-content
  .tabulator-arrow {
  top: 20px;
}

.tabulator.padded
  .tabulator-tableholder
  .tabulator-table
  .tabulator-row
  .tabulator-cell {
  padding: 1em 1em;
}

.tabulator.padded.very .tabulator-header .tabulator-col .tabulator-col-content {
  padding: 1.5em 1.5em;
}

.tabulator.padded.very
  .tabulator-header
  .tabulator-col
  .tabulator-col-content
  .tabulator-arrow {
  top: 26px;
}

.tabulator.padded.very
  .tabulator-tableholder
  .tabulator-table
  .tabulator-row
  .tabulator-cell {
  padding: 1.5em 1.5em;
}

.tabulator.compact .tabulator-header .tabulator-col .tabulator-col-content {
  padding: 0.5em 0.7em;
}

.tabulator.compact
  .tabulator-header
  .tabulator-col
  .tabulator-col-content
  .tabulator-arrow {
  top: 12px;
}

.tabulator.compact
  .tabulator-tableholder
  .tabulator-table
  .tabulator-row
  .tabulator-cell {
  padding: 0.5em 0.7em;
}

.tabulator.compact.very
  .tabulator-header
  .tabulator-col
  .tabulator-col-content {
  padding: 0.4em 0.6em;
}

.tabulator.compact.very
  .tabulator-header
  .tabulator-col
  .tabulator-col-content
  .tabulator-arrow {
  top: 10px;
}

.tabulator.compact.very
  .tabulator-tableholder
  .tabulator-table
  .tabulator-row
  .tabulator-cell {
  padding: 0.4em 0.6em;
}

.tabulator-row {
  border-bottom: 1px solid rgba(34, 36, 38, 0.1);
}

.tabulator-row.tabulator-row-even {
  background-color: #fff;
}

@media (hover: hover) and (pointer: fine) {
  .tabulator-row.tabulator-selectable:hover {
    box-shadow: 0px 0px 0px rgba(0, 0, 0, 0.87) inset;
    background: #e0e0e0 !important;
    color: rgba(0, 0, 0, 0.87) !important;
  }
}

.tabulator-row.tabulator-selected {
  background-color: #9abcea !important;
}

@media (hover: hover) and (pointer: fine) {
  .tabulator-row.tabulator-selected:hover {
    background-color: #769bcc !important;
    cursor: pointer;
  }
}

.tabulator-row.tabulator-moving {
  pointer-events: none !important;
}

.tabulator-row .tabulator-cell {
  padding: 0.78571em 0.78571em;
  border-right: none;
  vertical-align: middle;
}

.tabulator-row .tabulator-cell:last-of-type {
  border-right: none;
}

.tabulator-row .tabulator-cell.tabulator-row-header {
  border-bottom: none;
}

.tabulator-row .tabulator-cell .tabulator-responsive-collapse-toggle {
  color: #fff;
}

.tabulator-row.tabulator-group {
  background: #fafafa;
}

.tabulator-row.tabulator-group span {
  color: #666;
}

.tabulator-menu {
  background: #ffffff;
}

@media (hover: hover) and (pointer: fine) {
  .tabulator-menu
    .tabulator-menu-item:not(.tabulator-menu-item-disabled):hover {
    background: #f9fafb;
  }
}

.tabulator-edit-select-list {
  background: #ffffff;
}

.tabulator-edit-select-list .tabulator-edit-select-list-item.active {
  color: #ffffff;
}

.tabulator-edit-select-list .tabulator-edit-select-list-item.active.focused {
  outline: 1px solid rgba(255, 255, 255, 0.5);
}

@media (hover: hover) and (pointer: fine) {
  .tabulator-edit-select-list .tabulator-edit-select-list-item:hover {
    color: #ffffff;
  }
}

.tabulator-edit-select-list .tabulator-edit-select-list-notice {
  color: inherit;
}

.tabulator-print-table .tabulator-print-table-group {
  background: #fafafa;
}

.tabulator-print-table .tabulator-print-table-group span {
  color: #666;
}

/*# sourceMappingURL=tabulator_semanticui.css.map */
</style>
