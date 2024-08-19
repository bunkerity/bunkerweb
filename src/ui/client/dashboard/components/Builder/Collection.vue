<script setup>
// Containers
import Alert from "@components/Widget/Alert.vue";
import Button from "@components/Widget/Button.vue";
import ButtonGroup from "@components/Widget/ButtonGroup.vue";
import Cell from "@components/Widget/Cell.vue";
import Container from "@components/Widget/Container.vue";
import Filter from "@components/Widget/Filter.vue";
import Grid from "@components/Widget/Grid.vue";
import GridLayout from "@components/Widget/GridLayout.vue";
import Icons from "@components/Widget/Icons.vue";
import Modal from "@components/Widget/Modal.vue";
import Popover from "@components/Widget/Popover.vue";
import PopoverGroup from "@components/Widget/PopoverGroup.vue";
import Stat from "@components/Widget/Stat.vue";
import Status from "@components/Widget/Status.vue";
import Subtitle from "@components/Widget/Subtitle.vue";
import Table from "@components/Widget/Table.vue";
import Tabulator from "@components/Widget/Tabulator.vue";
import Text from "@components/Widget/Text.vue";
import Title from "@components/Widget/Title.vue";
import Regular from "@components/Form/Regular.vue";
import Advanced from "@components/Form/Advanced.vue";
import Raw from "@components/Form/Raw.vue";
import Easy from "@components/Form/Easy.vue";
import Fields from "@components/Form/Fields.vue";
import Pairs from "@components/List/Pairs.vue";
import Details from "@components/List/Details.vue";
import Templates from "@components/Form/Templates.vue";
import Unmatch from "@components/Message/Unmatch.vue";
import { useEqualStr } from "@utils/global.js";

/**
 * @name Builder/Bans.vue
 * @description This component is lightweight builder containing only the necessary components to create the bans page.
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

        <Alert v-if="useEqualStr(widget.type, 'Alert')" v-bind="widget.data" />
        <Cell v-if="useEqualStr(widget.type, 'Cell')" v-bind="widget.data" />
        <Container
          v-if="useEqualStr(widget.type, 'Container')"
          v-bind="widget.data"
        />
        <Filter
          v-if="useEqualStr(widget.type, 'Filter')"
          v-bind="widget.data"
        />
        <Icons v-if="useEqualStr(widget.type, 'Icons')" v-bind="widget.data" />
        <Modal v-if="useEqualStr(widget.type, 'Modal')" v-bind="widget.data" />
        <Popover
          v-if="useEqualStr(widget.type, 'Popover')"
          v-bind="widget.data"
        />

        <PopoverGroup
          v-if="useEqualStr(widget.type, 'PopoverGroup')"
          v-bind="widget.data"
        />
        <Stat v-if="useEqualStr(widget.type, 'Stat')" v-bind="widget.data" />
        <Status
          v-if="useEqualStr(widget.type, 'Status')"
          v-bind="widget.data"
        />
        <Table v-if="useEqualStr(widget.type, 'Table')" v-bind="widget.data" />
        <Text v-if="useEqualStr(widget.type, 'Text')" v-bind="widget.data" />
        <Advanced
          v-if="useEqualStr(widget.type, 'Advanced')"
          v-bind="widget.data"
        />
        <Raw v-if="useEqualStr(widget.type, 'Raw')" v-bind="widget.data" />
        <Easy v-if="useEqualStr(widget.type, 'Easy')" v-bind="widget.data" />
        <Fields
          v-if="useEqualStr(widget.type, 'Fields')"
          v-bind="widget.data"
        />
        <Pairs v-if="useEqualStr(widget.type, 'Pairs')" v-bind="widget.data" />
        <Details
          v-if="useEqualStr(widget.type, 'Details')"
          v-bind="widget.data"
        />
        <Templates
          v-if="useEqualStr(widget.type, 'Templates')"
          v-bind="widget.data"
        />
      </template>
    </Grid>
  </GridLayout>
</template>
