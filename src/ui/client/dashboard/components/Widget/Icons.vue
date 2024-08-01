<script setup>
import { defineProps, reactive, onMounted, ref, computed } from "vue";
import { useEqualStr } from "@utils/global.js";
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
import Exclamation from "@components/Icons/Exclamation.vue";
import Close from "@components/Icons/Close.vue";
import Pen from "@components/Icons/Pen.vue";
import Document from "@components/Icons/Document.vue";
import Eye from "@components/Icons/Eye.vue";

/**
 *  @name Widget/Icons.vue
 *  @description This component is a wrapper that contains all the icons available in the application (Icons folder).
 *  This component is used to display the icon based on the icon name.
 *  This component is mainly use inside others widgets.
 *  @example
 *  {
 *    iconName: 'box',
 *    iconClass: 'base',
 *    color: 'amber',
 *  }
 *  @param {string} iconName - The name of the icon to display. The icon name is the name of the file without the extension on lowercase.
 *  @param {string} [iconClass="base"] - Class to apply to the icon. In case the icon is related to a widget, the widget will set the right class automatically.
 *  @param {string} [color=""] - The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker').
 *  @param {boolean} [isStick=false] - If true, the icon will be stick to the top right of the parent container.
 *  @param {boolean} [disabled=false] - If true, the icon will be disabled.
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
  disabled: {
    type: Boolean,
    required: false,
    default: false,
  },
});

const icon = reactive({
  color: props.color,
  iconClass: props.iconClass,
});

const iconEl = ref();

onMounted(() => {
  icon.iconClass =
    props.iconClass || iconEl.value.closest("[data-is]")
      ? `icon-${iconEl.value.closest("[data-is]").getAttribute("data-is")}`
      : "icon-default";
});
</script>
<template>
  <div ref="iconEl" :class="[props.isStick ? 'stick' : '', 'icon-container']">
    <Exclamation
      v-if="useEqualStr(props.iconName, 'exclamation')"
      v-bind="icon"
    />
    <Box v-if="useEqualStr(props.iconName, 'box')" v-bind="icon" />
    <Carton v-if="useEqualStr(props.iconName, 'carton')" v-bind="icon" />
    <Core v-if="useEqualStr(props.iconName, 'core')" v-bind="icon" />
    <External v-if="useEqualStr(props.iconName, 'external')" v-bind="icon" />
    <Search v-if="useEqualStr(props.iconName, 'search')" v-bind="icon" />
    <Trash v-if="useEqualStr(props.iconName, 'trash')" v-bind="icon" />
    <Lock v-if="useEqualStr(props.iconName, 'lock')" v-bind="icon" />
    <Crown v-if="useEqualStr(props.iconName, 'crown')" v-bind="icon" />
    <Discord v-if="useEqualStr(props.iconName, 'discord')" v-bind="icon" />
    <Disk v-if="useEqualStr(props.iconName, 'disk')" v-bind="icon" />
    <Disks v-if="useEqualStr(props.iconName, 'disks')" v-bind="icon" />
    <Globe v-if="useEqualStr(props.iconName, 'globe')" v-bind="icon" />
    <Info v-if="useEqualStr(props.iconName, 'info')" v-bind="icon" />
    <Flag v-if="useEqualStr(props.iconName, 'flag')" v-bind="icon" />
    <Gear v-if="useEqualStr(props.iconName, 'gear')" v-bind="icon" />
    <Github v-if="useEqualStr(props.iconName, 'github')" v-bind="icon" />
    <House v-if="useEqualStr(props.iconName, 'house')" v-bind="icon" />
    <List v-if="useEqualStr(props.iconName, 'list')" v-bind="icon" />
    <Key v-if="useEqualStr(props.iconName, 'key')" v-bind="icon" />
    <Linkedin v-if="useEqualStr(props.iconName, 'linkedin')" v-bind="icon" />
    <Plus v-if="useEqualStr(props.iconName, 'plus')" v-bind="icon" />
    <Puzzle v-if="useEqualStr(props.iconName, 'puzzle')" v-bind="icon" />
    <Settings v-if="useEqualStr(props.iconName, 'settings')" v-bind="icon" />
    <Task v-if="useEqualStr(props.iconName, 'task')" v-bind="icon" />
    <Trespass v-if="useEqualStr(props.iconName, 'trespass')" v-bind="icon" />
    <Check v-if="useEqualStr(props.iconName, 'check')" v-bind="icon" />
    <Cross v-if="useEqualStr(props.iconName, 'cross')" v-bind="icon" />
    <Twitter v-if="useEqualStr(props.iconName, 'twitter')" v-bind="icon" />
    <Wire v-if="useEqualStr(props.iconName, 'wire')" v-bind="icon" />
    <Funnel v-if="useEqualStr(props.iconName, 'funnel')" v-bind="icon" />
    <Redirect v-if="useEqualStr(props.iconName, 'redirect')" v-bind="icon" />
    <Close v-if="useEqualStr(props.iconName, 'close')" v-bind="icon" />
    <Pen v-if="useEqualStr(props.iconName, 'pen')" v-bind="icon" />
    <Document v-if="useEqualStr(props.iconName, 'document')" v-bind="icon" />
    <Eye v-if="useEqualStr(props.iconName, 'eye')" v-bind="icon" />
  </div>
</template>
