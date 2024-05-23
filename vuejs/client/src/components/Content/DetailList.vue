<script setup>
import { computed, defineProps } from "vue";
/** 
  @name Content/DetailList.vue
  @description This component is used to display key value information in a list.
    @example
  {
    details : [{key: "Total Users", value: "100"}],
    itemColumns: {pc: 12, tablet: 12, mobile: 12}
  }
  @param {array} details - The list of key value information. The key and value can be a translation key or a raw text.
  @param {object} [itemColumns={pc: 12, tablet: 12, mobile: 12}] - Determine the  position of the items in the grid system.
*/

const props = defineProps({
  details: {
    type: Array,
    required: true,
  },
  itemColumns: {
    type: Object,
    required: false,
    default: { pc: 12, tablet: 12, mobile: 12 },
  },
});

const gridClass = computed(() => {
  return props.itemColumns
    ? `col-span-${props.itemColumns.mobile} md:col-span-${props.itemColumns.tablet} lg:col-span-${props.itemColumns.pc}`
    : "";
});
</script>
<template>
  <ul v-if="props.details" :class="['content-detail-list-container']">
    <li
      v-for="item in props.details"
      :class="['content-detail-list-item', gridClass]"
    >
      <span class="content-detail-list-title">
        {{ $t(item["key"], item["key"]) }}
      </span>
      <span class="content-detail-list-subtitle">
        {{ $t(item["value"], item["value"]) }}
      </span>
    </li>
  </ul>
</template>
