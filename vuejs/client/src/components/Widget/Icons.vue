<script setup>
import { defineProps, reactive, onMounted, ref } from "vue";
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
import Trash from "@components/Icons/Trash.vue";
import Lock from "@components/Icons/Lock.vue";
import Search from "@components/Icons/Search.vue";

/**
  @name Widget/Icons.vue
  @description This component is a wrapper that contains all the icons available in the application (Icons folder).
  This component is used to display the icon based on the icon name.
  This component is mainly use inside others widgets.
  @example
  {
    iconName: 'box',
    iconClass: 'base',
   color: 'amber',
  }
  @param {string} iconName - The name of the icon to display. The icon name is the name of the file without the extension on lowercase.
  @param {string} [iconClass="base"] - Class to apply to the icon. In case the icon is related to a widget, the widget will set the right class automatically.
  @param {string} [color=""] - The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker').
  @param {boolean} [isStick=false] - If true, the icon will be stick to the top right of the parent container.
  */

const props = defineProps({
  iconName: {
    type: String,
    required: true,
  },
  iconClass: {
    type: String,
    required: false,
    default: "",
  },
  color: {
    type: String,
    required: false,
    default: "",
  },
  isStick: {
    type: Boolean,
    required: false,
    default: false,
  },
});

const icon = reactive({
  color: props.color,
  class: props.iconClass,
});

const iconEl = ref();

onMounted(() => {
  icon.class =
    props.iconClass || iconEl.value.closest("[data-is]")
      ? `icon-${iconEl.value.closest("[data-is]").getAttribute("data-is")}`
      : "icon-default";
});
</script>
<template>
  <div ref="iconEl" :class="[props.isStick ? 'stick' : '', 'icon-container']">
    <Box
      v-if="props.iconName === 'box'"
      :iconClass="icon.class"
      :color="props.color"
    />
    <Carton
      v-if="props.iconName === 'carton'"
      :iconClass="icon.class"
      :color="props.color"
    />
    <Core
      v-if="props.iconName === 'core'"
      :iconClass="icon.class"
      :color="props.color"
    />
    <External
      v-if="props.iconName === 'external'"
      :iconClass="icon.class"
      :color="props.color"
    />
    <Search
      v-if="props.iconName === 'search'"
      :iconClass="icon.class"
      :color="props.color"
    />
    <Trash
      v-if="props.iconName === 'trash'"
      :iconClass="icon.class"
      :color="props.color"
    />
    <Lock
      v-if="props.iconName === 'lock'"
      :iconClass="icon.class"
      :color="props.color"
    />
    <Crown
      v-if="props.iconName === 'crown'"
      :iconClass="icon.class"
      :color="props.color"
    />
    <Discord
      v-if="props.iconName === 'discord'"
      :iconClass="icon.class"
      :color="props.color"
    />
    <Disk
      v-if="props.iconName === 'disk'"
      :iconClass="icon.class"
      :color="props.color"
    />
    <Disks
      v-if="props.iconName === 'disks'"
      :iconClass="icon.class"
      :color="props.color"
    />
    <Globe
      v-if="props.iconName === 'globe'"
      :iconClass="icon.class"
      :color="props.color"
    />
    <Info
      v-if="props.iconName === 'info'"
      :iconClass="icon.class"
      :color="props.color"
    />
    <Flag
      v-if="props.iconName === 'flag'"
      :iconClass="icon.class"
      :color="props.color"
    />
    <Gear
      v-if="props.iconName === 'gear'"
      :iconClass="icon.class"
      :color="props.color"
    />
    <Github
      v-if="props.iconName === 'github'"
      :iconClass="icon.class"
      :color="props.color"
    />
    <House
      v-if="props.iconName === 'house'"
      :iconClass="icon.class"
      :color="props.color"
    />
    <List
      v-if="props.iconName === 'list'"
      :iconClass="icon.class"
      :color="props.color"
    />
    <Key
      v-if="props.iconName === 'key'"
      :iconClass="icon.class"
      :color="props.color"
    />
    <Linkedin
      v-if="props.iconName === 'linkedin'"
      :iconClass="icon.class"
      :color="props.color"
    />
    <Plus
      v-if="props.iconName === 'plus'"
      :iconClass="icon.class"
      :color="props.color"
    />
    <Puzzle
      v-if="props.iconName === 'puzzle'"
      :iconClass="icon.class"
      :color="props.color"
    />
    <Settings
      v-if="props.iconName === 'settings'"
      :iconClass="icon.class"
      :color="props.color"
    />
    <Task
      v-if="props.iconName === 'task'"
      :iconClass="icon.class"
      :color="props.color"
    />
    <Trespass
      v-if="props.iconName === 'trespass'"
      :iconClass="icon.class"
      :color="props.color"
    />
    <Check
      v-if="props.iconName === 'check'"
      :iconClass="icon.class"
      :color="props.color"
    />
    <Cross
      v-if="props.iconName === 'cross'"
      :iconClass="icon.class"
      :color="props.color"
    />
    <Twitter
      v-if="props.iconName === 'twitter'"
      :iconClass="icon.class"
      :color="props.color"
    />
    <Wire
      v-if="props.iconName === 'wire'"
      :iconClass="icon.class"
      :color="props.color"
    />
    <Funnel
      v-if="props.iconName === 'funnel'"
      :iconClass="icon.class"
      :color="props.color"
    />
    <Redirect
      v-if="props.iconName === 'redirect'"
      :iconClass="icon.class"
      :color="props.color"
    />
  </div>
</template>
