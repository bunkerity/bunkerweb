<script setup>
import { reactive, computed, ref, onMounted, watch } from "vue";
import Text from "@components/Widget/Text.vue";
import Icons from "@components/Widget/Icons.vue";
import Fields from "@components/Form/Fields.vue";
import Button from "@components/Widget/Button.vue";
import ButtonGroup from "@components/Widget/ButtonGroup.vue";

/**
  @name Builder/Cell.vue
  @description This component includes all elements that can be shown in a table cell.
  @example
   { type : "button",
     data : {
       id: "open-modal-btn",
       text: "Open modal",
       disabled: false,
       hideText: true,
       color: "green",
       size: "normal",
       iconName: "modal",
       attrs: { data-toggle: "modal", "data-target": "#modal"},
     }
  }
  @param {string} type - The type of the cell. This needs to be a Vue component.
  @param {object} data - The data to display in the cell. This needs to be the props of the Vue component.
*/

const props = defineProps({
  type: {
    type: String,
    required: true,
  },
  data: {
    type: Object,
    required: true,
  },
});

const cell = reactive({
  name: computed(() => props.type.toLowerCase()),
});
</script>

<template>
  <Text v-if="cell.name === 'text'" v-bind="props.data" />
  <Icons v-if="cell.name === 'icons'" v-bind="props.data" />
  <Fields v-if="cell.name === 'fields'" v-bind="props.data" />
  <Button v-if="cell.name === 'button'" v-bind="props.data" />
  <ButtonGroup v-if="cell.name === 'buttongroup'" v-bind="props.data" />
</template>
