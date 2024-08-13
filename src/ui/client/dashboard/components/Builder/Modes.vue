<script setup>
// Containers
import Grid from "@components/Widget/Grid.vue";
import GridLayout from "@components/Widget/GridLayout.vue";
import Title from "@components/Widget/Title.vue";
import Subtitle from "@components/Widget/Subtitle.vue";
import Templates from "@components/Form/Templates.vue";
import ButtonGroup from "@components/Widget/ButtonGroup.vue";
import { useEqualStr } from "@utils/global.js";

/**
 * @name Builder/Modes.vue
 * @description This component is lightweight builder containing only the necessary components to create a service mode page.
 * @example
 * [
 *     {
 *       type: "card",
 *       containerColumns: { pc: 12, tablet: 12, mobile: 12 },
 *       widgets: [
 *                 {
 *                   type: "Title",
 *                   data : {
 *                     title: "dashboard_global_config",
 *                     type: "card"
 *                   },
 *                 },
 *                 {
 *                   type: "Raw",
 *                   data: {
 *                     template: {},
 *                   },
 *                 },
 *       ],
 *     },
 * ];
 * @param {array} builder - Array of containers and widgets
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
    :maxWidthScreen="container.maxWidthScreen"
    :type="container.type"
    :title="container.title"
    :link="container.link"
    :columns="container.containerColumns"
    :id="container.id"
    :display="container.display"
  >
    <!-- widget grid -->
    <Grid>
      <!-- widget element -->
      <template v-for="(widget, index) in container.widgets" :key="index">
        <Title v-if="useEqualStr(widget.type, 'Title')" v-bind="widget.data" />
        <Subtitle
          v-if="useEqualStr(widget.type, 'Subtitle')"
          v-bind="widget.data"
        />
        <Templates
          v-if="useEqualStr(widget.type, 'Templates')"
          v-bind="widget.data"
        />
        <ButtonGroup
          v-if="useEqualStr(widget.type, 'ButtonGroup')"
          v-bind="widget.data"
        />
      </template>
    </Grid>
  </GridLayout>
</template>
