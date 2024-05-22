<script setup>
/** 
  @name Stat/Subtitle.vue
  @description This component is a subtitle used with stats.
  This can be used alone in case we don't need a complete stat widget.
  In case you have a title, subtitle, stat and icon to display, you can directly use Stat widget.
    @example
  {
    subtitle: "Last 30 days",
    subtitleColor: "info",
    subtitleClass: "text-sm"
  }
  @param {string} subtitle - The subtitle of the stat. Can be a translation key or by default raw text.
  @param {string} [subtitleColor="info"] - The color of the subtitle between error, success, warning, info
  @param {string} [subtitleClass=""] - Additional class, useful when component is used directly on a grid system
*/

const props = defineProps({
  subtitle: {
    type: String,
    required: true,
  },
  subtitleColor: {
    type: String,
    required: false,
    default: "info",
  },
  subtitleClass: {
    type: String,
    required: false,
    default: "",
  },
});
</script>

<template>
  <p
    v-if="props.subtitle"
    :class="['stat-subtitle', props.subtitleColor, props.subtitleClass]"
  >
    {{ $t(props.subtitle, props.subtitle) }}
  </p>
</template>
