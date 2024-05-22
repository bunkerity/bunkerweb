<script setup>
/** 
  @name Title/Stat.vue
  @description This component is a title used with stats.
  This can be used alone in case we don't need a complete stat widget.
  In case you have a title, subtitle, stat and icon to display, you can directly use Stat widget.
    @example
  {
    title: "Total Users",
    titleClass: "text-lg"
  }
    @param {string} title - The title of the stat. Can be a translation key or by default raw text.
    @param {string} [titleClass=""] - Additional class, useful when component is used directly on a grid system
*/

const props = defineProps({
  title: {
    type: String,
    required: true,
  },
  titleClass: {
    type: String,
    required: false,
    default: "",
  },
});
</script>

<template>
  <p :class="['stat-title', props.titleClass]">
    {{ $t(props.title, props.title) }}
  </p>
</template>
