<script setup>
import Container from "@components/Widget/Container.vue";
import Title from "@components/Widget/Title.vue";
import Subtitle from "@components/Widget/Subtitle.vue";
import ContentStat from "@components/Content/Stat.vue";
import Icons from "@components/Widget/Icons.vue";

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
  stat: {
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
  <Container :columns="{ pc: 12, tablet: 12, mobile: 12 }">
    <!-- text -->
    <div
      :class="[
        'stat-content-container',
        props.iconName ? 'is-icon' : 'no-icon',
      ]"
    >
      <Title type="stat" :title="props.title" />
      <ContentStat :stat="props.stat" />
      <Subtitle
        type="stat"
        v-if="props.subtitle"
        :subtitle="props.subtitle"
        :subtitleColor="props.subtitleColor"
      />
    </div>
    <Icons
      v-if="props.iconName"
      :iconName="props.iconName"
      :iconColor="props.iconColor"
      :iconType="'stat'"
    />
  </Container>
</template>
