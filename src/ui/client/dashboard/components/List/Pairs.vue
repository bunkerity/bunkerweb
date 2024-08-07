<script setup>
import { computed, defineProps } from "vue";
/**
 *  @name List/Pairs.vue
 *  @description This component is used to display key value information in a list.
 *  @example
 *  {
 *    pairs : [
 *              { key: "Total Users", value: "100" }
 *            ],
 *    columns: { pc: 12, tablet: 12, mobile: 12 }
 *  }
 *  @param {array} pairs - The list of key value information. The key and value can be a translation key or a raw text.
 *  @param {object} [columns={"pc": "12", "tablet": "12", "mobile": "12"}] - Determine the  position of the items in the grid system.
 */

const props = defineProps({
  pairs: {
    type: Array,
    required: true,
  },
  columns: {
    type: Object,
    required: false,
    default: { pc: 12, tablet: 12, mobile: 12 },
  },
});

const gridClass = computed(() => {
  return `col-span-${props.columns.mobile} md:col-span-${props.columns.tablet} lg:col-span-${props.columns.pc}`;
});
</script>
<template>
  <ul data-is="list-pairs" v-if="props.pairs" :class="['list-pairs-container']">
    <li v-for="item in props.pairs" :class="['list-pairs-item', gridClass]">
      <span class="list-pairs-title">
        {{ $t(item["key"], $t("dashboard_placeholder", item["key"])) }}
      </span>
      <span class="list-pairs-subtitle">
        {{ $t(item["value"], $t("dashboard_placeholder", item["value"])) }}
      </span>
    </li>
  </ul>
</template>
