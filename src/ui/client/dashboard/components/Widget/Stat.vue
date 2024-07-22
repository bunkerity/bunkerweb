<script setup>
import Container from "@components/Widget/Container.vue";
import Title from "@components/Widget/Title.vue";
import Subtitle from "@components/Widget/Subtitle.vue";
import Text from "@components/Widget/Text.vue";
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
    link: "/users",
    subtitleColor: "info",
  }
  @param {string} title - The title of the stat. Can be a translation key or by default raw text.
  @param {string|number} value - The value of the stat
  @param {string} [subtitle=""] - The subtitle of the stat. Can be a translation key or by default raw text.
  @param {string} [iconName=""] - A top-right icon to display between icon available in Icons/Stat. Case falsy value, no icon displayed. The icon name is the name of the file without the extension on lowercase.
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
  color: {
    type: String,
    required: false,
    default: "",
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
  <Container data-is="stat" :columns="{ pc: 12, tablet: 12, mobile: 12 }">
    <!-- text -->
    <div
      :class="[
        'stat-content-container',
        props.iconName ? 'is-icon' : 'no-icon',
      ]"
    >
      <Title :tag="'h3'" :title="props.title" />
      <Text :text="props.stat" />
      <Subtitle
        v-if="props.subtitle"
        :subtitle="props.subtitle"
        :color="props.subtitleColor"
      />
    </div>
    <Icons v-if="props.iconName" :iconName="props.iconName" :isStick="true" />
  </Container>
</template>
