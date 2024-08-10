<!-- <script setup>
import { ref, reactive, onMounted } from "vue";
import Icons from "@components/Widget/Icons.vue";
import { resolveComponent } from "vue";
import { TabulatorFull as Tabulator } from "tabulator-tables"; //import Tabulator library

function addModules() {
  Tabulator.extendModule("format", "formatters", {
    icons: function (cell, formatterParams) {
      console.log(cell);
      console.log(formatterParams);
      const values = cell.getValue();
      console.log(values);
      return values;
      // return resolveComponent(Icons, {
      //   iconName: values?.iconName,
      //   iconClass: values?.iconClass,
      //   color: values?.color,
      // });
    },
  });
}

const tableEl = ref(null); //reference to your table element

const table = reactive({
  instance: null,
  columns: [
    { title: "Name", field: "name", width: 150 },
    { title: "Age", field: "age", hozAlign: "left", formatter: "progress" },
    { title: "Favourite Color", field: "col" },
    {
      title: "Date Of Birth",
      field: "dob",
      sorter: "date",
      hozAlign: "center",
    },
  ],
  data: [{ id: 1, name: "Oli Bob", age: "12", col: "red", dob: "" }],
});

onMounted(() => {
  addModules();
  //instantiate Tabulator when element is mounted
  table.instance = new Tabulator(tableEl.value, {
    data: table.data, //link data to table
    reactiveData: true, //enable data reactivity
    columns: table.columns, //define table columns
  });
});
</script>

<template>
  <link
    href="https://unpkg.com/tabulator-tables/dist/css/tabulator.min.css"
    rel="stylesheet"
  />

  <div ref="tableEl"></div>
</template> -->

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
  <link
    href="https://unpkg.com/tabulator-tables/dist/css/tabulator.min.css"
    rel="stylesheet"
  />
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
