<script setup>
import { reactive, onBeforeMount } from "vue";
// Containers
import Grid from "@components/Widget/Grid.vue";
import GridLayout from "@components/Widget/GridLayout.vue";
// Title
import TitleCard from "@components/Title/Card.vue";
import TitleCardContent from "@components/Title/CardContent.vue";
import TitleStat from "@components/Title/Stat.vue";
// Subtitle
import SubtitleStat from "@components/Subtitle/Stat.vue";
// Content
import ContentStat from "@components/Content/Stat.vue";
import ContentDetailList from "@components/Content/DetailList.vue";
// Icon
import IconStat from "@components/Icon/Stat.vue";
import IconStatus from "@components/Icon/Status.vue";
// Form
import Checkbox from "@components/Forms/Field/Checkbox.vue";
import Select from "@components/Forms/Field/Select.vue";
import Input from "@components/Forms/Field/Input.vue";
import Datepicker from "@components/Forms/Field/Datepicker.vue";
// Widget
import Button from "@components/Widget/Button.vue";
import ButtonGroup from "@components/Widget/ButtonGroup.vue";
import Stat from "@components/Widget/Stat.vue";
import Instance from "@components/Widget/Instance.vue";

/**
  @name Builder.vue
  @description This component is a wrapper to create a complete page using containers and widgets.
  We have to define each container and each widget inside it.
  This is an abstract component that will be used to create any kind of page content (base dashboard elements like menu and news excluded)
  @example
  [
   {
        // this can be a "card", "modal", "table"... etc
        "type": "card",  

        // container custom key
        "title" : "My awesome card", 

        // additionnal tailwind css class
        "containerClass": "", 

        // We can define the top level grid system (GridLayout.vue)
        "containerColumns" : {"pc": 12, "tablet": 12, "mobile": 12},

        // Each widget need a name (here type) and associated data
        // We need to send specific data for each widget typ
        widgets: [
                {
                        type : "Checkbox", 
                        data : {containerClass : "", columns : {"pc": 6, "tablet": 12, "mobile": 12}, id:"test-check", value: "yes", label: "Checkbox", name: "checkbox", required: true, version: "v1.0.0", hideLabel: false, headerClass: "text-red-500" }
                }, {    
                        type : "Select",   
                        data : {containerClass : "", columns : {"pc": 6, "tablet": 12, "mobile": 12}, id: 'test-select', value: 'yes', values: ['yes', 'no'], name: 'test-select', disabled: false, required: true, label: 'Test select', tabId: '1',}
                }
        ]
   }
  ]
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
        <TitleCard v-if="widget.type === 'TitleCard'" v-bind="widget.data" />
        <TitleCardContent
          v-if="widget.type === 'TitleCardContent'"
          v-bind="widget.data"
        />
        <Checkbox v-if="widget.type === 'Checkbox'" v-bind="widget.data" />
        <Select v-if="widget.type === 'Select'" v-bind="widget.data" />
        <Input v-if="widget.type === 'Input'" v-bind="widget.data" />
        <Datepicker v-if="widget.type === 'Datepicker'" v-bind="widget.data" />
        <Button v-if="widget.type === 'Button'" v-bind="widget.data" />
        <Stat v-if="widget.type === 'Stat'" v-bind="widget.data" />
        <TitleStat v-if="widget.type === 'TitleStat'" v-bind="widget.data" />
        <SubtitleStat
          v-if="widget.type === 'SubtitleStat'"
          v-bind="widget.data"
        />
        <ContentStat
          v-if="widget.type === 'ContentStat'"
          v-bind="widget.data"
        />
        <IconStat v-if="widget.type === 'IconStat'" v-bind="widget.data" />
        <Instance v-if="widget.type === 'Instance'" v-bind="widget.data" />
        <IconStatus v-if="widget.type === 'IconStatus'" v-bind="widget.data" />
        <ContentDetailList
          v-if="widget.type === 'ContentDetailList'"
          v-bind="widget.data"
        />
        <ButtonGroup
          v-if="widget.type === 'ButtonGroup'"
          v-bind="widget.data"
        />
      </template>
    </Grid>
  </GridLayout>
</template>
