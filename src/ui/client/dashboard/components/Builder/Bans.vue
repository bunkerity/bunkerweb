<script setup>
// Containers
import Grid from "@components/Widget/Grid.vue";
import GridLayout from "@components/Widget/GridLayout.vue";
import Tabulator from "@components/Widget/Tabulator.vue";
import Button from "@components/Widget/Button.vue";
import ButtonGroup from "@components/Widget/ButtonGroup.vue";
import Regular from "@components/Form/Regular.vue";
import Title from "@components/Widget/Title.vue";
import Subtitle from "@components/Widget/Subtitle.vue";
import Unmatch from "@components/Message/Unmatch.vue";
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
 *                { type: "Unmatch",
 *                  data: { text: "bans_not_found" }
 *               },
 *    ],
 *   },
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
        <Unmatch
          v-if="useEqualStr(widget.type, 'Unmatch')"
          v-bind="widget.data"
        />
        <Tabulator
          v-if="useEqualStr(widget.type, 'Tabulator')"
          v-bind="widget.data"
        />
        <Button
          v-if="useEqualStr(widget.type, 'Button')"
          v-bind="widget.data"
        />
        <Regular
          v-if="useEqualStr(widget.type, 'Regular')"
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
