<script setup>
import Icons from "@/components/Widget/Icons.vue";
/** 
  @name Icon/Stat.vue
  @description This component is a icon used with stats.
  This can be used alone in case we don't need a complete stat widget.
  In case you have a title, subtitle, stat and icon to display, you can directly use Stat widget.
    @example
  {
    iconName: "crown",
    iconColor: "info",
    iconClass: "text-sm"
  }
  @param {string} iconName - The icon name of the stat. Can be a translation key or by default raw text.
  @param {string} [iconColor="info"] - The color of the icon between error, success, warning, info
  @param {string} [iconClass=""] - Additional class, useful when component is used directly on a grid system.
*/

const props = defineProps({
  iconName: {
    type: String,
    required: false,
    default: "",
  },
  iconColor: {
    type: String,
    required: false,
    default: "",
  },
  iconClass: {
    type: String,
    required: false,
    default: "",
  },
});
</script>

<template>
  <div
    v-if="props.iconName"
    role="img"
    aria-label="version"
    :class="['stat-svg-container', props.iconColor, props.iconClass]"
  >
    <Icons
      :iconName="props.iconName"
      :iconClass="'stat-svg'"
      :iconColor="'white'"
    />
  </div>
</template>
