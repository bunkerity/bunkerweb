<script setup>
// Containers
import Grid from "@components/Widget/Grid.vue";
import GridLayout from "@components/Widget/GridLayout.vue";
import DashboardLayout from "@components/Dashboard/Layout.vue";
import Tabulator from "@components/Widget/Tabulator.vue";
import { useEqualStr } from "@utils/global.js";
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
  { title: "Icon", field: "icon", formatter: "icons" },
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
          columns: columns,
          items: items,
        },
      },
    ],
  },
];
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
