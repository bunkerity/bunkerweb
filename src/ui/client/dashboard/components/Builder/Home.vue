<script setup>
// Containers
import Grid from "@components/Widget/Grid.vue";
import GridLayout from "@components/Widget/GridLayout.vue";
import Stat from "@components/Widget/Stat.vue";
import { useEqualStr } from "@utils/global.js";

/**
 * @name Builder/Home.vue
 * @description This component is lightweight builder containing only the necessary components to create the home page.
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
        <Stat v-if="useEqualStr(widget.type, 'Stat')" v-bind="widget.data" />
      </template>
    </Grid>
  </GridLayout>
</template>
