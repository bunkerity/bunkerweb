<script setup>
/** 
  @name Content/Stat.vue
  @description This component is used with stats to display the stat value.
  This can be used alone in case we don't need a complete stat widget.
  In case you have a title, subtitle, stat and icon to display, you can directly use Stat widget.
    @example
  {
    stat: "100",
    statClass: "text-3xl"
  }
  @param {string} stat - The stat value. Can be a translation key or by default raw text.
  @param {string} [statClass=""] - Additional class, useful when component is used directly on a grid system
*/

const props = defineProps({
  stat: {
    type: [String, Number],
    required: true,
  },
  statClass: {
    type: String,
    required: false,
    default: "",
  },
});
</script>

<template>
  <h5 :class="['content-stat', props.statClass]">
    {{ $t(props.stat, props.stat) }}
  </h5>
</template>
