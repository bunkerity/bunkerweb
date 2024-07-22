<script setup>
// Containers
import Grid from "@components/Widget/Grid.vue";
import GridLayout from "@components/Widget/GridLayout.vue";
import Instance from "@components/Widget/Instance.vue";

/**
  @name Builder/Setup.vue
  @description This component is lightweight builder containing only the necessary components to create the setup page.
  @example
  [

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
    :id="container.id"
  >
    <!-- widget grid -->
    <Grid>
      <!-- widget element -->
      <template v-for="(widget, index) in container.widgets" :key="index">
        <Instance v-if="widget.type === 'Instance'" v-bind="widget.data" />
      </template>
    </Grid>
  </GridLayout>
</template>
