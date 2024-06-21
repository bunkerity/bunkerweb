<script setup>
import { defineProps, computed, reactive } from "vue";
import Flex from "@components/Widget/Flex.vue";
import Container from "@components/Widget/Container.vue";
import PopoverGroup from "@components/Widget/PopoverGroup.vue";
import Text from "@components/Widget/Text.vue";
import Filter from "@components/Widget/Filter.vue";
import Grid from "@components/Widget/Grid.vue";

/** 
  @name List/Details.vue
  @description This component is a list of items separate on two columns : one for the title, and other for a list of popovers related to the plugin (type, link...)
  @example
  {
  details : [{
    text: "name",
    disabled : false,
    attrs: {
      id: "id",
      value: "value",
    },
    popovers: [
      {
        text: "This is a popover text",
        iconName: "info",
        iconColor: "info",
      },
      {
        text: "This is a popover text",
        iconName: "info",
        iconColor: "info",
      },
    ],
}]
  @param {string} details  - List of details item that contains a text, disabled state, attrs and list of popovers. We can also add a disabled key to disable the item.
  @param {array} [filters=[]] - List of filters to apply on the list of items.
  @param {columns} [columns={pc: 4, tablet: 6, mobile: 12}] - Determine the position of the items in the grid system.
*/

const props = defineProps({
  details: {
    type: Array,
    required: true,
  },
  filters: {
    type: Array,
    required: false,
    default: [],
  },
  columns: {
    type: [Object, Boolean],
    required: false,
    default: { pc: 4, tablet: 6, mobile: 12 },
  },
});

const data = reactive({
  base: JSON.parse(JSON.stringify(props.details)),
  format: JSON.parse(JSON.stringify(props.details)),
});

const gridClass = computed(() => {
  return `col-span-${props.columns.mobile} md:col-span-${props.columns.tablet} lg:col-span-${props.columns.pc}`;
});

const unmatch = {
  text: "dashboard_no_match",
  textClass: "text-unmatch",
  icons: {
    iconName: "search",
    iconColor: "info",
  },
};
</script>

<template>
  <Grid>
    <Filter
      v-if="props.filters.length"
      @filter="(v) => (data.format = v)"
      :data="data.base"
      :filters="props.filters"
    />
    <div v-if="!data.format.length" class="layout-unmatch">
      <Text v-bind="unmatch" />
    </div>
    <ul v-if="data.format.length" :class="['list-details-container']">
      <li
        v-for="(item, id) in data.format"
        :class="[
          'list-details-item',
          gridClass,
          item.disabled ? 'disabled' : 'enabled',
        ]"
        v-bind="item.attrs || {}"
      >
        <Flex :flexClass="'justify-between items-center'">
          <Text :tag="'p'" :text="item.text" />
          <div>
            <PopoverGroup :popovers="item.popovers" />
          </div>
        </Flex>
      </li>
    </ul>
  </Grid>
</template>
