<script setup>
/** 
  @name Stat/Value.vue
  @description This component is a value used with stats.
  This can be used alone in case we don't need a complete stat widget.
  In case you have a title, subtitle, value and icon to display, you can directly use Stat widget.
    @example
  {
    value: "100",
    valueClass: "text-3xl"
  }
  @param {string} value - The value of the stat. Can be a translation key or by default raw text.
  @param {string} [valueClass=""] - Additional class, useful when component is used directly on a grid system
*/

const props = defineProps({
  value: {
    type: String,
    required: true,
  },
  valueClass: {
    type: String,
    required: false,
    default: "",
  },
});
</script>

<template>
  <h5 :class="['stat-value', props.valueClass]">
    {{ $t(props.value, props.value) }}
  </h5>
</template>
