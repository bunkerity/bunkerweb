<script setup>
import { ref, reactive, onMounted, Teleport, computed, onUnmounted } from "vue";
import Icons from "@components/Widget/Icons.vue";
import Text from "@components/Widget/Text.vue";
import Fields from "@components/Form/Fields.vue";
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

/**
 *  @name Widget/Tabulator.vue
 *  @description This component allow to display a table using the Tabulator library with utils and custom components around to work with (like filters).
 *  Because we can't instantiate Vue component inside the Tabulator cell, I choose to send default component props to the cell and teleport the component inside the cell.
 *  The created instance is store in the tableStore using the id as key in order to use it in other components.
 *  UI : I created a formatter for each custom component that will return an empty string.
 *  Sorting : because we aren't working with primitives but props object, each columns that have a custom component will have a custom sorter to avoid sorting error.
 *  Filtering : I created isomorphic filters that will get the right data to check for each custom component object.
 *  To apply a filter, we need to render a field that will be link to the filterTable() function.
 *  A11y :I created a11yTable(), with sortable header tab index.
 *  @example
 *     filter =  [{
 *             "type": "like", // isomorphic filter type
 *             "fields": ["ip"], // fields to filter
 *             // setting is a regular Fields props object
 *             "setting": {
 *                 "id": "input-search-ip",
 *                 "name": "input-search-ip",
 *                 "label": "bans_search_ip",  # keep it (a18n)
 *                 "value": "",
 *                 "inpType": "input",
 *                 "columns": {"pc": 3, "tablet": 4, "mobile": 12},
 *             },
 *     }];
 * @param {String} id - Unique id of the table
 * @param {Boolean} [isStriped=true] - Add striped class to the table
 * @param {Array} [filters=[]] - List of filters to display
 * @param {Array} columns - List of columns to display
 * @param {Array} items - List of items to display
 * @param {Array} [actionsButtons=[]] - Buttons group props to render buttons that will be after filters and before the table stick left.
 * @param {String} [layout="fitDataTable"] - Layout of the table. "fitDataTable" useful with wide columns, "fitColumns" useful with narrow columns.
 * @param {Number} [rowHeight= 0] - Case value is 0, this will be ignored.
 * @param {Number} [colMinWidth=150] - Minimum width for each col of  a row
 * @param {Number} [colMaxWidth=0] - Maximum width for each col of  a row. Case value is 0, this will be ignored.
 * @param {Boolean} [isPagination=true] - Add pagination to the table
 * @param {Number} [itemsBeforePagination=10] - Hide pagination unless number is reach.
 * @param {Number} [paginationSize=10] - Number of items per page
 * @param {Number} [paginationInitialPage=1] - Initial page
 * @param {Array} [paginationSizeSelector=[10, 25, 50, 100]] - Select number of items per page
 * @returns {Void}
 */
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
    required: true,
    default: [],
  },
  actionsButtons: {
    type: Object,
    required: false,
    default: [],
  },
  layout: {
    type: String,
    required: false,
    default: "fitDataTable",
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
  itemsBeforePagination: {
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
    default: [10, 25, 50, 100],
  },
});

const tableEl = ref(null); //reference to your table element

const table = reactive({
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
      resizableColumnFit: true, //maintain the fit of columns when resizing
      layout: props.layout,
      placeholder: "No Data Available", //display message to user on empty table
    };

    if (props.rowHeight) opts.rowHeight = props.rowHeight;

    // columns formatting
    let columns = JSON.parse(JSON.stringify(table.columns));
    columns = formatColumns(columns);
    opts.columns = columns;

    opts.pagination = props.isPagination;
    opts.paginationSize = props.paginationSize;
    opts.paginationInitialPage = props.paginationInitialPage;
    opts.paginationButtonCount = 2;
    opts.paginationSizeSelector = props.paginationSizeSelector.concat([true]);
    opts.paginationCounter = "rows";

    return opts;
  }),
});

/**
 *  @name formatColumns
 *  @description This will add some key to columns that can be passed from props like minWidth or maxWidth.
 *  Case key already exists, this will override it.
 *  @param {Array} columns -  The columns are the list of columns that we want to check.
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
 *  @param {String} type -  The type is the name of the component.
 *  @param {Object} values - The values are the props that we want to pass to the component.
 *  @param {HTMLElement} elDOM - The elDOM is the element where we want to teleport the component.
 *  @returns {Void}
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
 *  @returns {Void}
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
 *  @param {Object} tableInstance -  The tableInstance is the current table instance.
 *  @param {Object} filter -  the filter dict is here the setting filter data
 *  @param {String} value -  the value is the current value return by the filter input.
 *  @returns {Void}
 */
function filterTable(filter, value = "") {
  // Merge all filters
  table.filters[filter.setting.id] = { ...filter, value: value };
  applyTableFilter(table.instance, table.filters);
}

/**
 *  @name togglePagination
 *  @description We can't directly show or hide pagination without creating instance, so we will handle it externally.
 *  We will listen to table data, and check the number of items after a change and we will hide or show the pagination.
 *  @returns {Void}
 */
function togglePagination() {
  if (!props.isPagination || !props.itemsBeforePagination) return;

  function toggle(currItems, itemsToShow) {
    const isPagination = currItems.length >= itemsToShow ? true : false;

    const footer = tableEl.value.querySelector(".tabulator-footer");
    isPagination
      ? footer.classList.remove("hidden")
      : footer.classList.add("hidden");
  }

  toggle(props.items, props.itemsBeforePagination);

  table.instance.on("dataChanged", (data) => {
    toggle(data, props.itemsBeforePagination);
  });
}

onMounted(() => {
  extendTabulator();
  table.instance = new Tabulator(tableEl.value, table.options);
  table.instance.on("tableBuilt", () => {
    togglePagination();

    a11yTable(table.instance);
    // Add table instance to store in order to use it in other components
    tableStore.setTable(props.id, table.instance);
    setTimeout(() => {
      table.instance.redraw();
    }, 100);
  });
});
</script>

<template>
  <div data-is="table" class="layout-table">
    <Container
      v-if="props.filters.length"
      :containerClass="'layout-settings-table'"
    >
      <template v-for="filter in props.filters">
        <Fields
          :setting="filter.setting"
          @inp="(value) => filterTable(filter, value)"
        />
      </template>
    </Container>
    <ButtonGroup
      v-if="props.actionsButtons.length"
      :buttons="props.actionsButtons"
    />
    <div
      :class="[props.isStriped ? 'striped' : '']"
      ref="tableEl"
      data-is="table-content"
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
        <Text
          v-if="useEqualStr(comp.type, 'Text')"
          v-bind="{ ...comp.values }"
        />
        <Fields
          v-if="useEqualStr(comp.type, 'Fields')"
          v-bind="{ ...comp.values }"
        />
        <ButtonGroup
          v-if="useEqualStr(comp.type, 'ButtonGroup')"
          v-bind="{ ...comp.values }"
        />
      </Teleport>
    </template>
  </div>
</template>
