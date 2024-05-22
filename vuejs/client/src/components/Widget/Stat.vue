<script setup>
import TitleStat from "@components/Title/Stat.vue";
import ContentStat from "@components/Content/Stat.vue";
import SubtitleStat from "@components/Subtitle/Stat.vue";
import IconStat from "@components/Icon/Stat.vue";

/** 
  @name Widget/Stat.vue
  @description This component is wrapper of all stat components.
  This component has no grid system and will always get the full width of the parent.
  This component is mainly use inside a blank card.
  @example
  {
    title: "Total Users",
    value: 100,
    subtitle : "Last 30 days",
    iconName: "user",
    iconColor: "sky",
    link: "/users",
    subtitleColor: "info",
  }
  @param {string} title - The title of the stat. Can be a translation key or by default raw text.
  @param {string|number} value - The value of the stat
  @param {string} [subtitle=""] - The subtitle of the stat. Can be a translation key or by default raw text.
  @param {string} [iconName=""] - A top-right icon to display between icon available in Icons/Stat. Case falsy value, no icon displayed. The icon name is the name of the file without the extension on lowercase.
  @param {string} [iconColor="sky"] - The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink, lime, rose, fuchsia, violet, lightBlue, warmGray, trueGray, coolGray, blueGray, white, black)
  @param {string} [subtitleColor="info"] - The color of the subtitle between error, success, warning, info
  @param {string} [statClass=""] - Additional class
*/

const props = defineProps({
  title: {
    type: String,
    required: true,
  },
  value: {
    type: [String, Number],
    required: true,
  },
  subtitle: {
    type: String,
    required: false,
    default: "",
  },
  iconName: {
    type: String,
    required: false,
    default: "",
  },
  iconColor: {
    type: String,
    required: false,
    default: "sky",
  },
  subtitleColor: {
    type: String,
    required: false,
    default: "info",
  },
  statClass: {
    type: String,
    required: false,
    default: "",
  },
});
</script>
<template>
  <div :class="['stat-container', props.statClass]">
    <!-- text -->
    <div
      :class="[
        'stat-content-container',
        props.iconName ? 'is-icon' : 'no-icon',
      ]"
    >
      <TitleStat :title="props.title" />
      <ContentStat :value="props.value" />
      <SubtitleStat
        v-if="props.subtitle"
        :subtitle="props.subtitle"
        :subtitleColor="props.subtitleColor"
      />
    </div>
    <IconStat
      v-if="props.iconName"
      :iconName="props.iconName"
      :iconColor="props.iconColor"
    />
  </div>
</template>
