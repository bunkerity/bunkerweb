<script setup>
import { ref, reactive, onMounted, Teleport, computed, onUnmounted } from "vue";
import Icons from "@components/Widget/Icons.vue";
import Text from "@components/Widget/Text.vue";
import Fields from "@components/Form/Fields.vue";
import Button from "@components/Widget/Button.vue";
import ButtonGroup from "@components/Widget/ButtonGroup.vue";
import Container from "@components/Widget/Container.vue";
import { TabulatorFull as Tabulator } from "tabulator-tables"; //import Tabulator library
import { useEqualStr } from "@utils/global.js";
import {
  addColumnsSorter,
  addColumnsWidth,
  a11yTable,
  applyTableFilter,
  overrideDefaultFilters,
} from "@utils/tabulator.js";
import { useTableStore } from "@store/global.js";

const tableStore = useTableStore();

// TODO : ADD JSDOC COMPONENT

const customComponents = ["Icons", "Text", "Fields", "Button", "ButtonGroup"];

const props = defineProps({
  id: {
    type: String,
    required: true,
    default: "table-component",
  },
  isStriped: {
    type: Boolean,
    required: false,
    default: true,
  },
  filters: {
    type: Array,
    required: false,
    default: [],
  },
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
    default: 150,
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
  filters: {},
  columns: props.columns,
  items: props.items,
  customComponents: [],
  options: computed(() => {
    const opts = {
      data: table.items, //link data to table
      reactiveData: true, //enable data reactivity
      autoResize: true, // prevent auto resizing of table
      resizableRows: true, // this option takes a boolean value (default = false)
      layout: "fitColumns",
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
 *  @name extendTabulator
 *  @description Wrapper that will do some extend or override  on the Tabulator instance:
 *  1 - Add custom components to a list in order to render them and teleport them when formatting the cell.
 *  2 - Add custom formatters for each custom components in order to force Tabulator to render empty string.
 *  3 - Override default filters to add custom filters for each custom components (because  we need to access a specific key in the props object).
 *  We are using the Tabular.extendModule() that allow use to do this.
 *  @returns {void}
 */
function extendTabulator() {
  const formatOpts = {};
  for (let i = 0; i < customComponents.length; i++) {
    const module = customComponents[i];
    formatOpts[module.toLowerCase()] = function (cell, formatterParams) {
      addCustomComponent(module, cell.getValue(), cell.getElement());
      return "";
    };
  }
  Tabulator.extendModule("format", "formatters", formatOpts);
  Tabulator.extendModule("filter", "filters", overrideDefaultFilters());
}

/**
 *  @name filterTable
 *  @description We can't directly send the current filter input to filter the table because the Tabulator will filter everything at once.
 *  So we need to get the value and store on the table.filters dict to merge all filters and apply them at once.
 *  We will use the applyTableFilter() to apply the filters. Additionnal checks (like empty value) are done on the applyTableFilter() function.
 *  @param {object} tableInstance -  The tableInstance is the current table instance.
 *  @param {object} filter -  the filter dict is here the setting filter data
 *  @param {string} value -  the value is the current value return by the filter input.
 *  @returns {void}
 */
function filterTable(filter, value = "") {
  // Merge all filters
  table.filters[filter.setting.id] = { ...filter, value: value };
  applyTableFilter(table.instance, table.filters);
}

onMounted(() => {
  extendTabulator();
  table.instance = new Tabulator(tableEl.value, table.options);
  table.instance.on("tableBuilt", () => {
    table.instance.redraw();
    a11yTable(table.instance);
    // Add table instance to store in order to use it in other components
    tableStore.setTable(props.id, table.instance);
  });
});

onUnmounted(() => {
  table.instance.destroy();
  table.instance = null;
});
</script>

<template>
  <Container :containerClass="'layout-settings'">
    <template v-for="filter in props.filters">
      <Fields
        :setting="filter.setting"
        @inp="(value) => filterTable(filter, value)"
      />
    </template>
  </Container>
  <div
    :class="[props.isStriped ? 'striped' : '']"
    data-is="table"
    ref="tableEl"
  ></div>
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
