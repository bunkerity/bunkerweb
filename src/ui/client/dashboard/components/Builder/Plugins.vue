<script setup>
// Containers
import Grid from "@components/Widget/Grid.vue";
import GridLayout from "@components/Widget/GridLayout.vue";
import ListDetails from "@components/List/Details.vue";
import Title from "@components/Widget/Title.vue";
import Subtitle from "@components/Widget/Subtitle.vue";
import Upload from "@components/Widget/Upload.vue";
import Text from "@components/Widget/Text.vue";
import Tabulator from "@components/Widget/Tabulator.vue";
import ButtonGroup from "@components/Widget/ButtonGroup.vue";
import { useEqualStr } from "@utils/global.js";

/**
 * @name Builder/PLugins.vue
 * @description This component is lightweight builder containing only the necessary components to create the plugins page.
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
        <Upload
          v-if="useEqualStr(widget.type, 'Upload')"
          v-bind="widget.data"
        />
        <Subtitle
          v-if="useEqualStr(widget.type, 'Subtitle')"
          v-bind="widget.data"
        />
        <Tabulator
          v-if="useEqualStr(widget.type, 'Tabulator')"
          v-bind="widget.data"
        />
        <ListDetails
          v-if="useEqualStr(widget.type, 'ListDetails')"
          v-bind="widget.data"
        />
        <Text v-if="useEqualStr(widget.type, 'Text')" v-bind="widget.data" />
        <ButtonGroup
          v-if="useEqualStr(widget.type, 'ButtonGroup')"
          v-bind="widget.data"
        />
      </template>
    </Grid>
  </GridLayout>
</template>
