<script setup>
import Box from "@components/Icons/Box.vue";
import Carton from "@components/Icons/Carton.vue";
import Core from "@components/Icons/Core.vue";
import Crown  from "@components/Icons/Crown.vue";
import Discord  from "@components/Icons/Discord.vue";
import Disk  from "@components/Icons/Disk.vue";
import Flag  from "@components/Icons/Flag.vue";
import Gear  from "@components/Icons/Gear.vue";
import Github  from "@components/Icons/Github.vue";
import House  from "@components/Icons/House.vue";
import List  from "@components/Icons/List.vue";
import Key  from "@components/Icons/Key.vue";
import Linkedin  from "@components/Icons/Linkedin.vue";
import Plus  from "@components/Icons/Plus.vue";
import Puzzle  from "@components/Icons/Puzzle.vue";
import Settings  from "@components/Icons/Settings.vue";
import Task  from "@components/Icons/Task.vue";
import Trespass  from "@components/Icons/Trespass.vue";
import Twitter  from "@components/Icons/Twitter.vue";
import Wire  from "@components/Icons/Wire.vue";
import Funnel  from "@components/Icons/Funnel.vue";

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
  @param {string} [iconClass="default-svg"] - Class to apply to the icon. In case the icon is related to a widget, the widget will set the right class automatically.
  @param {string} [iconColor="info"] - The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker').
  */

const props = defineProps({
  iconName: {
    type: String,
    required: true,
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

</script>
<template>
    <Box v-if="props.iconName === 'box'" :iconClass="props.iconClass" :iconColor="props.iconColor" />
    <Carton v-if="props.iconName === 'carton'" :iconClass="props.iconClass" :iconColor="props.iconColor" />
    <Core v-if="props.iconName === 'core'" :iconClass="props.iconClass" :iconColor="props.iconColor" />
    <Crown v-if="props.iconName === 'crown'" :iconClass="props.iconClass" :iconColor="props.iconColor" />
    <Discord v-if="props.iconName === 'discord'" :iconClass="props.iconClass" :iconColor="props.iconColor" />
    <Disk v-if="props.iconName === 'disk'" :iconClass="props.iconClass" :iconColor="props.iconColor" />
    <Flag v-if="props.iconName === 'flag'" :iconClass="props.iconClass" :iconColor="props.iconColor" />
    <Gear v-if="props.iconName === 'gear'" :iconClass="props.iconClass" :iconColor="props.iconColor" />
    <Github v-if="props.iconName === 'github'" :iconClass="props.iconClass" :iconColor="props.iconColor" />
    <House v-if="props.iconName === 'house'" :iconClass="props.iconClass" :iconColor="props.iconColor" />
    <List v-if="props.iconName === 'list'" :iconClass="props.iconClass" :iconColor="props.iconColor" />
    <Key v-if="props.iconName === 'key'" :iconClass="props.iconClass" :iconColor="props.iconColor" />
    <Linkedin v-if="props.iconName === 'linkedin'" :iconClass="props.iconClass" :iconColor="props.iconColor" />
    <Plus v-if="props.iconName === 'plus'" :iconClass="props.iconClass" :iconColor="props.iconColor" />
    <Puzzle v-if="props.iconName === 'puzzle'" :iconClass="props.iconClass" :iconColor="props.iconColor" />
    <Settings v-if="props.iconName === 'settings'" :iconClass="props.iconClass" :iconColor="props.iconColor" />
    <Task v-if="props.iconName === 'task'" :iconClass="props.iconClass" :iconColor="props.iconColor" />
    <Trespass v-if="props.iconName === 'trespass'" :iconClass="props.iconClass" :iconColor="props.iconColor" />
    <Twitter v-if="props.iconName === 'twitter'" :iconClass="props.iconClass" :iconColor="props.iconColor" />
    <Wire v-if="props.iconName === 'wire'" :iconClass="props.iconClass" :iconColor="props.iconColor" />
    <Funnel v-if="props.iconName === 'funnel'" :iconClass="props.iconClass" :iconColor="props.iconColor" />
</template>