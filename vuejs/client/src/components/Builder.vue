<script setup>
import { reactive, onBeforeMount } from "vue";
import Checkbox from "@components/Forms/Field/Checkbox.vue";
import Select from "@components/Forms/Field/Select.vue";
import Input from "@components/Forms/Field/Input.vue";
import GridLayout from "@components/Widget/GridLayout.vue";
import Grid from "@components/Widget/Grid.vue";

/* 
  COMPONENT DESCRIPTION
  *
  *
  This Builder component is used to create complete pages content with multiple components.
  This is an abstract component that will be used to create any kind of page content.
  You need to determine each container and each widget inside it.
  *
  *
  PROPS ARGUMENTS
  *
  *
  builder : array,
  *
  *
  PROPS EXAMPLE
  *
  *
  [{
        "type": "card",  // this can be a "card", "modal", "table"... etc
        "containerClass": "", // tailwind css grid class (items-start, ...)
        "containerColumns" : {"pc": 12, "tablet": 12, "mobile": 12},
        "title" : "My awesome card", // container title
        // Each widget need a name (here type) and associated data
        // We need to send specific data for each widget type
        widgets: [
                {
                        type : "Checkbox", 
                        data : {containerClass : "", columns : {"pc": 6, "tablet": 12, "mobile": 12}, id:"test-check", value: "yes", label: "Checkbox", name: "checkbox", required: true, version: "v1.0.0", hideLabel: false, headerClass: "text-red-500" }
                }, {    
                        type : "Select",   
                        data : {containerClass : "", columns : {"pc": 6, "tablet": 12, "mobile": 12}, id: 'test-select', value: 'yes', values: ['yes', 'no'], name: 'test-select', disabled: false, required: true, label: 'Test select', tabId: '1',}
                }
        ]
        },
  ]
  *
  *
*/

const props = defineProps({
    builder : {
        type: Array,
        required: true,
    },
})
</script>

<template>
<div class="grid grid-cols-12">
        <!-- top level grid (layout) -->
        <GridLayout v-for="(container, index) in props.builder" :key="index"
            :gridLayoutClass="container.containerClass"
            :type="container.type"
            :title="container.title"
            :columns="container.containerColumns">
                <!-- widget grid -->
                <Grid>
                        <!-- widget element -->
                        <template v-for="(widget, index) in container.widgets" :key="index">
                                <Checkbox v-if="widget.type === 'Checkbox'" v-bind="widget.data"></Checkbox>
                                <Select v-if="widget.type === 'Select'" v-bind="widget.data"></Select>
                                <Input v-if="widget.type === 'Input'" v-bind="widget.data"></Input>
                        </template>
                </Grid>
        </GridLayout>
</div>
</template>
