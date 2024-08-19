<script setup>
// Containers
import Grid from "@components/Widget/Grid.vue";
import GridLayout from "@components/Widget/GridLayout.vue";
import Title from "@components/Widget/Title.vue";
import Fields from "@components/Form/Fields.vue";
import Unmatch from "@components/Message/Unmatch.vue";
import { useEqualStr } from "@utils/global.js";

/**
 * @name Builder/Logs.vue
 * @description This component is lightweight builder containing only the necessary components to create the logs page.
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
        <Unmatch
          v-if="useEqualStr(widget.type, 'Unmatch')"
          v-bind="widget.data"
        />

        <Title v-if="useEqualStr(widget.type, 'Title')" v-bind="widget.data" />
        <Fields
          v-if="useEqualStr(widget.type, 'Fields')"
          v-bind="widget.data"
        />
      </template>
    </Grid>
  </GridLayout>
</template>
