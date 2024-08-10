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
import { ref, reactive, onMounted, Teleport, computed } from "vue";
import Icons from "@components/Widget/Icons.vue";
import { TabulatorFull as Tabulator } from "tabulator-tables"; //import Tabulator library

const props = defineProps({
  isPagination: {
    type: Boolean,
    required: false,
    default: true,
  },
  paginationSize: {
    type: Number,
    required: false,
    default: 1,
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
  instance: null,
  columns: [
    { title: "Name", field: "name", width: 150 },
    { title: "Icon", field: "icon", formatter: "icons" },
  ],
  data: [
    { id: 1, name: "test", icon: { iconName: "box", color: "amber" } },
    {
      id: 2,
      name: "test",
      icon: { iconName: "document", color: "blue" },
    },
    { id: 3, name: "test", icon: { iconName: "box", color: "amber" } },
    { id: 4, name: "test", icon: { iconName: "document", color: "blue" } },
    { id: 5, name: "test", icon: { iconName: "box", color: "amber" } },
    { id: 6, name: "test", icon: { iconName: "document", color: "blue" } },
    { id: 7, name: "test", icon: { iconName: "box", color: "amber" } },
  ],
  customComponents: [],
  options: computed(() => {
    const opts = {
      data: table.data, //link data to table
      reactiveData: true, //enable data reactivity
      columns: table.columns, //define table columns
    };

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

function setCustomComponent(type, values, elDOM) {
  table.customComponents.push({
    type: type,
    values: values,
    elDOM: elDOM,
  });
}

function addModules() {
  Tabulator.extendModule("format", "formatters", {
    icons: function (cell, formatterParams) {
      setCustomComponent("Icons", cell.getValue(), cell.getElement());
      return "";
    },
  });
}

onMounted(() => {
  addModules();
  //instantiate Tabulator when element is mounted
  table.instance = new Tabulator(tableEl.value, table.options);
  table.instance.on("tableBuilt", () => {
    console.log("tableBuilt");
  });
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
    v-for="component in table.customComponents"
  >
    <Teleport :to="component.elDOM">
      <Icons
        v-if="component.type === 'Icons'"
        v-bind="{ ...component.values }"
      />
    </Teleport>
  </template>
</template>
