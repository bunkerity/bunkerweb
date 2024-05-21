<script setup>
import { onMounted, ref } from 'vue';
import IconCrown from '@components/Icons/Stat/Crown.vue';
import IconFree from '@components/Icons/Stat/Free.vue';
import IconInstances from '@components/Icons/Stat/Instances.vue';
import IconPlugins from '@components/Icons/Stat/Plugins.vue';
import IconServices from '@components/Icons/Stat/Services.vue';
import IconVersion from '@components/Icons/Stat/Version.vue';

/** 
  @name Widget/Stat.vue
  @description This component is a basic stat element that can be used to display a title, a value and an icon.
  This component has no grid system and will always get the full width of the parent.
  This component is mainly use inside a blank card.
  @example
  {
    title: "Total Users",
    value: 100,
    subtitle : "Last 30 days",
    icon: "user",
    iconColor: "sky",
    link: "/users",
    subtitleColor: "info",
  }
  @param {string} title - The title of the stat. Can be a translation key or by default raw text.
  @param {string|number} value - The value of the stat
  @param {string} [subtitle=""] - The subtitle of the stat. Can be a translation key or by default raw text.
  @param {string} [icon=""] - A top-right icon to display between icon available in Icons/Stat. Case falsy value, no icon displayed. The icon name is the name of the file without the extension on lowercase.
  @param {string} [iconColor="sky"] - The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink, lime, rose, fuchsia, violet, lightBlue, warmGray, trueGray, coolGray, blueGray, white, black)
  @param {string} [link=""] - A link to redirect when the card is clicked. Case falsy value, element is a div, , else it is an anchor.
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
        default : ""
    },
    icon: {
        type: String,
        required: false,
        default : ""
    },
    iconColor: {
        type: String,
        required: false,
        default: "sky",
    },
    link: {
        type: String,
        required: false,
        default : ""
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

})

const statEl = ref();

onMounted(() => {
    if (props.link) {
        statEl.value.setAttribute('href', props.link);;
        statEl.value.setAttribute('rel', 'noopener')
    }

    if(props.link && props.link.startsWith('http')) {
        statEl.value.setAttribute('target', '_blank');
    }
})
</script>
<template>
    <component ref="statEl" :is="props.link ? 'a' : 'div'"
        :class="['stat-container', props.statClass]">
        <!-- text -->
        <div :class="['stat-content-container', props.icon ? 'is-icon' : 'no-icon']">
            <p class="stat-title">{{  $t(props.title, props.title) }}</p>
            <!-- version of user -->
            <h5 class="stat-value">{{  $t(props.value, props.value) }}</h5>
            <p v-if="props.subtitle" :class="['stat-subtitle', props.subtitleColor]">{{  $t(props.subtitle, props.subtitle) }}</p>
        </div>
        <!-- end text -->
        <!-- icon -->
        <div v-if="props.icon" role="img"
                aria-label="version"
                :class="['stat-svg-container', props.iconColor]">
            <IconCrown v-if="props.icon === 'crown'" />
            <IconFree v-else-if="props.icon === 'free'" />
            <IconInstances v-else-if="props.icon === 'instances'" />
            <IconPlugins v-else-if="props.icon === 'plugins'" />
            <IconServices v-else-if="props.icon === 'services'" />
            <IconVersion v-else-if="props.icon === 'version'" />
        </div>
        <!-- end icon -->
    </component>
</template>
 