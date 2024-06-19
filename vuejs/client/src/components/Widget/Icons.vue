<script setup>
import Box from "@components/Icons/Box.vue";
import Carton from "@components/Icons/Carton.vue";
import Core from "@components/Icons/Core.vue";
import Crown from "@components/Icons/Crown.vue";
import Discord from "@components/Icons/Discord.vue";
import Disk from "@components/Icons/Disk.vue";
import Flag from "@components/Icons/Flag.vue";
import Gear from "@components/Icons/Gear.vue";
import Github from "@components/Icons/Github.vue";
import House from "@components/Icons/House.vue";
import List from "@components/Icons/List.vue";
import Key from "@components/Icons/Key.vue";
import Linkedin from "@components/Icons/Linkedin.vue";
import Plus from "@components/Icons/Plus.vue";
import Puzzle from "@components/Icons/Puzzle.vue";
import Settings from "@components/Icons/Settings.vue";
import Task from "@components/Icons/Task.vue";
import Trespass from "@components/Icons/Trespass.vue";
import Check from "@components/Icons/Check.vue";
import Cross from "@components/Icons/Cross.vue";
import Twitter from "@components/Icons/Twitter.vue";
import Wire from "@components/Icons/Wire.vue";
import Funnel from "@components/Icons/Funnel.vue";
import Disks from "@components/Icons/Disks.vue";
import Globe from "@components/Icons/Globe.vue";
import Info from "@components/Icons/Info.vue";
import Redirect from "@components/Icons/Redirect.vue";
import External from "@components/Icons/External.vue";

import { computed } from "vue";

/** 
  @name Widget/Icons.vue
  @description This component is a wrapper that contains all the icons available in the application (Icons folder).
  This component is used to display the icon based on the icon name.
  This component is mainly use inside others widgets.
  @example
  {
    iconName: 'box',
    iconClass: 'stat-svg',
    iconColor: 'amber',
  }
  @param {string} iconName - The name of the icon to display. The icon name is the name of the file without the extension on lowercase.
  @param {string} [iconType="default"] - The type of the icon between default and stat. Default is used for regular icons, stat is used for icons inside a stat widget.
  @param {string} [iconClass="default-svg"] - Class to apply to the icon. In case the icon is related to a widget, the widget will set the right class automatically.
  @param {string} [iconColor="info"] - The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker').
  */

const props = defineProps({
  iconName: {
    type: String,
    required: true,
  },
  iconType: {
    type: String,
    required: false,
    default: "default",
  },
  iconClass: {
    type: String,
    required: false,
    default: "default-svg",
  },
  iconColor: {
    type: String,
    required: false,
    default: "info",
  },
});

const tag = computed(() => {
  if (props.iconType === "stat") return "div";
  return "template";
});

const containerClass = computed(() => {
  if (props.iconType === "stat") return "stat-svg-container";
  return "";
});

const iconColor = computed(() => {
  if (props.iconType === "stat") return "white";
  return props.iconColor;
});

const iconClass = computed(() => {
  if (props.iconType === "stat") return "stat-svg";
  return props.iconClass;
});
</script>
<template>
  <div :class="[containerClass, props.iconColor, props.iconClass]">
    <Box
      v-if="props.iconName === 'box'"
      :iconClass="iconClass"
      :iconColor="iconColor"
    />
    <Carton
      v-if="props.iconName === 'carton'"
      :iconClass="iconClass"
      :iconColor="iconColor"
    />
    <Core
      v-if="props.iconName === 'core'"
      :iconClass="iconClass"
      :iconColor="iconColor"
    />
    <External
      v-if="props.iconName === 'external'"
      :iconClass="iconClass"
      :iconColor="iconColor"
    />
    <Crown
      v-if="props.iconName === 'crown'"
      :iconClass="iconClass"
      :iconColor="iconColor"
    />
    <Discord
      v-if="props.iconName === 'discord'"
      :iconClass="iconClass"
      :iconColor="iconColor"
    />
    <Disk
      v-if="props.iconName === 'disk'"
      :iconClass="iconClass"
      :iconColor="iconColor"
    />
    <Disks
      v-if="props.iconName === 'disks'"
      :iconClass="iconClass"
      :iconColor="iconColor"
    />
    <Globe
      v-if="props.iconName === 'globe'"
      :iconClass="iconClass"
      :iconColor="iconColor"
    />
    <Info
      v-if="props.iconName === 'info'"
      :iconClass="iconClass"
      :iconColor="iconColor"
    />
    <Flag
      v-if="props.iconName === 'flag'"
      :iconClass="iconClass"
      :iconColor="iconColor"
    />
    <Gear
      v-if="props.iconName === 'gear'"
      :iconClass="iconClass"
      :iconColor="iconColor"
    />
    <Github
      v-if="props.iconName === 'github'"
      :iconClass="iconClass"
      :iconColor="iconColor"
    />
    <House
      v-if="props.iconName === 'house'"
      :iconClass="iconClass"
      :iconColor="iconColor"
    />
    <List
      v-if="props.iconName === 'list'"
      :iconClass="iconClass"
      :iconColor="iconColor"
    />
    <Key
      v-if="props.iconName === 'key'"
      :iconClass="iconClass"
      :iconColor="iconColor"
    />
    <Linkedin
      v-if="props.iconName === 'linkedin'"
      :iconClass="iconClass"
      :iconColor="iconColor"
    />
    <Plus
      v-if="props.iconName === 'plus'"
      :iconClass="iconClass"
      :iconColor="iconColor"
    />
    <Puzzle
      v-if="props.iconName === 'puzzle'"
      :iconClass="iconClass"
      :iconColor="iconColor"
    />
    <Settings
      v-if="props.iconName === 'settings'"
      :iconClass="iconClass"
      :iconColor="iconColor"
    />
    <Task
      v-if="props.iconName === 'task'"
      :iconClass="iconClass"
      :iconColor="iconColor"
    />
    <Trespass
      v-if="props.iconName === 'trespass'"
      :iconClass="iconClass"
      :iconColor="iconColor"
    />
    <Check
      v-if="props.iconName === 'check'"
      :iconClass="iconClass"
      :iconColor="iconColor"
    />
    <Cross
      v-if="props.iconName === 'cross'"
      :iconClass="iconClass"
      :iconColor="iconColor"
    />
    <Twitter
      v-if="props.iconName === 'twitter'"
      :iconClass="iconClass"
      :iconColor="iconColor"
    />
    <Wire
      v-if="props.iconName === 'wire'"
      :iconClass="iconClass"
      :iconColor="iconColor"
    />
    <Funnel
      v-if="props.iconName === 'funnel'"
      :iconClass="iconClass"
      :iconColor="iconColor"
    />
    <Redirect
      v-if="props.iconName === 'redirect'"
      :iconClass="iconClass"
      :iconColor="iconColor"
    />
  </div>
</template>
