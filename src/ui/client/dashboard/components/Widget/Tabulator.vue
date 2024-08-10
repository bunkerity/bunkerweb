<script setup>
import { ref, reactive, onMounted, Teleport, computed, onUnmounted } from "vue";
import Icons from "@components/Widget/Icons.vue";
import Text from "@components/Widget/Text.vue";
import Fields from "@components/Form/Fields.vue";
import Button from "@components/Widget/Button.vue";
import ButtonGroup from "@components/Widget/ButtonGroup.vue";
import { TabulatorFull as Tabulator } from "tabulator-tables"; //import Tabulator library
import { useEqualStr } from "@utils/global.js";
import {
  addColumnsSorter,
  addColumnsWidth,
  a18yTable,
} from "@utils/tabulator.js";

// TODO : ADD JSDOC COMPONENT

const customComponents = ["Icons", "Text", "Fields", "Button", "ButtonGroup"];

const props = defineProps({
  columns: {
    type: Array,
    required: true,
    default: [],
  },
  items: {
    type: Array,
    required: false,
    default: [],
  },
  rowHeight: {
    type: Number,
    required: false,
    default: 0,
  },
  colMinWidth: {
    type: Number,
    required: false,
    default: 100,
  },
  colMaxWidth: {
    type: Number,
    required: false,
    default: 0,
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
  items: props.items,
  customComponents: [],
  options: computed(() => {
    const opts = {
      data: table.items, //link data to table
      reactiveData: true, //enable data reactivity
      autoResize: true, // prevent auto resizing of table
      resizableRows: true, // this option takes a boolean value (default = false)
      layout: "fitDataFill",
    };

    if (props.rowHeight) opts.rowHeight = props.rowHeight;

    // columns formatting
    let columns = JSON.parse(JSON.stringify(table.columns));
    columns = formatColumns(columns);
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
 *  @name formatColumns
 *  @description This will add some key to columns that can be passed from props like minWidth or maxWidth.
 *  Case key already exists, this will override it.
 *  @param {array} columns -  The columns are the list of columns that we want to check.
 *  @returns {array} - Return the columns with the custom sort added.
 */
function formatColumns(columns) {
  for (let i = 0; i < columns.length; i++) {
    const column = columns[i];
    addColumnsSorter(column);
    addColumnsWidth(column, props.colMinWidth, props.colMaxWidth);
  }
  return columns;
}

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

onMounted(() => {
  addComponentsFormats();
  table.instance = new Tabulator(tableEl.value, table.options);
  table.instance.on("tableBuilt", () => {
    table.instance.redraw();
    a18yTable(table.instance);
  });
});

onUnmounted(() => {
  table.instance.destroy();
  table.instance = null;
});
</script>

<template>
  <div data-is="table" ref="tableEl"></div>
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
