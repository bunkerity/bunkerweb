<script setup>
// Containers
import Grid from "@components/Widget/Grid.vue";
import GridLayout from "@components/Widget/GridLayout.vue";
import PluginBox from "@components/Widget/PluginBox.vue";
import Title from "@components/Widget/Title.vue";

/**
  @name Builder/pLugin.vue
  @description This component is lightweight builder containing only the necessary components to create the plugins page.
  @example
  [
  {
    type: "card",
    containerColumns: { pc: 12, tablet: 12, mobile: 12 },
    widgets: [
    {
    type: "Title",
    data : {
      title: "dashboard_plugins",
      type: "card"
    },
    },
      {
        type: "PluginBox",
        data:   {
            name: "Plugin name",
            flexClass : "justify-center",
            columns: { pc: 4, tablet: 6, mobile: 12 },
            containerClass: "mb-4",
            popovers: [
              {
                text: "This is a popover text",
                iconName: "info",
                iconColor: "info",
              },
              {
                text: "This is a popover text",
                iconName: "info",
                iconColor: "info",
              },
            ],
          },
      },
    ],
  },
];
  @param {array} builder - Array of containers and widgets
*/

const props = defineProps({
  builder: {
    type: Array,
    required: true,
  },
});
</script>

<template>
  <!-- top level grid (layout) -->
  <GridLayout
    v-for="(container, index) in props.builder"
    :key="index"
    :gridLayoutClass="container.containerClass"
    :type="container.type"
    :title="container.title"
    :link="container.link"
    :columns="container.containerColumns"
  >
    <!-- widget grid -->
    <Grid>
      <!-- widget element -->
      <template v-for="(widget, index) in container.widgets" :key="index">
        <Title v-if="widget.type === 'Title'" v-bind="widget.data" />
        <PluginBox v-if="widget.type === 'PluginBox'" v-bind="widget.data" />
      </template>
    </Grid>
  </GridLayout>
</template>
