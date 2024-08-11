<script setup>
// Containers
import Grid from "@components/Widget/Grid.vue";
import GridLayout from "@components/Widget/GridLayout.vue";
import DashboardLayout from "@components/Dashboard/Layout.vue";
import Tabulator from "@components/Widget/Tabulator.vue";
import { useEqualStr } from "@utils/global.js";
import { useTableStore } from "@store/global.js";
import { onMounted } from "vue";

const tableStore = useTableStore();
/**
 * @name Builder/Bans.vue
 * @description This component is lightweight builder containing only the necessary components to create the bans page.
 * @example
 * [
 *   {
 *     type: "card",
 *     gridLayoutClass: "transparent",
 *     widgets: [
 *                { type: "MessageUnmatch",
 *                  data: { text: "bans_not_found" }
 *               },
 *    ],
 *   },
 * ];
 * @param {array} builder - Array of containers and widgets
 */

const columns = [
  { title: "Name", field: "text", formatter: "text" },
  {
    title: "Icon",
    field: "icon",
    formatter: "icons",
  },
];

// Because we are going to use built-in filters, we can't use the Filter component
// So we need this format in order to create under the hood fields that will be linked to the tabulator filter
// We need to pass on the setting key the same props as the Fields component. For example a "=" tabulator filter will be used with a select field, this one need "values" array to work.
// type : Choose between available tabulator built-in filters ("keywords", "like", "!=", ">", "<", ">=", "<=", "in", "regex", "!=")
const filters = [
  {
    type: "like",
    fields: ["text"],
    setting: {
      id: "test-input",
      name: "test-input",
      label: "Test input",
      value: "",
      inpType: "input",
      columns: { pc: 3, tablet: 4, mobile: 12 },
    },
  },
  {
    type: "=",
    fields: ["icon"],
    setting: {
      id: "test-select",
      name: "test-select",
      label: "Test select",
      value: "all",
      values: ["all", "box", "document"],
      setting: { inpType: "input" },
      inpType: "select",
      columns: { pc: 3, tablet: 4, mobile: 12 },
      onlyDown: true,
    },
  },
];

const items = [
  {
    id: 1,
    text: { text: "Oli bob" },
    icon: { iconName: "box", color: "amber" },
  },
  {
    id: 1,
    text: { text: "Oli bob" },
    icon: { iconName: "box", color: "amber" },
  },
  {
    id: 1,
    text: { text: "Oli bob" },
    icon: { iconName: "box", color: "amber" },
  },
  {
    id: 1,
    text: { text: "Oli bob" },
    icon: { iconName: "box", color: "amber" },
  },
  {
    id: 1,
    text: { text: "Oli bob" },
    icon: { iconName: "box", color: "amber" },
  },
  {
    id: 1,
    text: { text: "Oli bob" },
    icon: { iconName: "box", color: "amber" },
  },
  {
    id: 1,
    text: { text: "Oli bob" },
    icon: { iconName: "box", color: "amber" },
  },
  {
    id: 1,
    text: { text: "Oli bob" },
    icon: { iconName: "box", color: "amber" },
  },
  {
    id: 1,
    text: { text: "Oli bob" },
    icon: { iconName: "box", color: "amber" },
  },
  {
    id: 1,
    text: { text: "Oli bob" },
    icon: { iconName: "box", color: "amber" },
  },
  {
    id: 1,
    text: { text: "Oli bob" },
    icon: { iconName: "box", color: "amber" },
  },
  {
    id: 1,
    text: { text: "Oli bob" },
    icon: { iconName: "box", color: "amber" },
  },
  {
    id: 1,
    text: { text: "Oli bob" },
    icon: { iconName: "box", color: "amber" },
  },
];

const builder = [
  {
    type: "card",
    gridLayoutClass: "transparent",
    widgets: [
      {
        type: "Tabulator",
        data: {
          id: "table-test",
          columns: columns,
          items: items,
          filters: filters,
        },
      },
    ],
  },
];
// Interact with table instance from another component
// onMounted(() => {
//   setTimeout(() => {
//     const table = tableStore.getTableById("table-test");
//     console.log(table);
//     table.setFilter("text", "keywords", "fesfs");
//   }, 1000);
// });
</script>

<template>
  <DashboardLayout>
    <GridLayout
      v-for="(container, index) in builder"
      :key="index"
      :gridLayoutClass="container.containerClass"
      :type="container.type"
      :title="container.title"
      :link="container.link"
      :columns="container.containerColumns"
      :id="container.id"
    >
      <!-- widget grid -->
      <Grid>
        <!-- widget element -->
        <template v-for="(widget, index) in container.widgets" :key="index">
          <Tabulator
            v-if="useEqualStr(widget.type, 'Tabulator')"
            v-bind="widget.data"
          />
        </template>
      </Grid>
    </GridLayout>
  </DashboardLayout>
</template>
