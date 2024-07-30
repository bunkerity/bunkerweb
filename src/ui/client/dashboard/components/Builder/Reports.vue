<script setup>
// Containers
import Grid from "@components/Widget/Grid.vue";
import GridLayout from "@components/Widget/GridLayout.vue";
import Title from "@components/Widget/Title.vue";
import Subtitle from "@components/Widget/Subtitle.vue";
import Table from "@components/Widget/Table.vue";
import ListPairs from "@components/List/Pairs.vue";
import MessageUnmatch from "@components/Message/Unmatch.vue";
import { useEqualStr } from "@utils/global.js";

/**
  @name Builder/Reports.vue
  @description This component is lightweight builder containing only the necessary components to create the reports page.
  @example
[
  {
    type: "card",
    gridLayoutClass: "transparent",
    widgets: [{ type: "MessageUnmatch", data: { text: "reports_not_found" } }],
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
    :id="container.id"
  >
    <!-- widget grid -->
    <Grid>
      <!-- widget element -->
      <template v-for="(widget, index) in container.widgets" :key="index">
        <MessageUnmatch
          v-if="useEqualStr(widget.type, 'messageunmatch')"
          v-bind="widget.data"
        />
        <Title v-if="useEqualStr(widget.type, 'title')" v-bind="widget.data" />
        <Subtitle
          v-if="useEqualStr(widget.type, 'subtitle')"
          v-bind="widget.data"
        />
        <Table v-if="useEqualStr(widget.type, 'table')" v-bind="widget.data" />
        <ListPairs
          v-if="useEqualStr(widget.type, 'listpairs')"
          v-bind="widget.data"
        />
      </template>
    </Grid>
  </GridLayout>
</template>
