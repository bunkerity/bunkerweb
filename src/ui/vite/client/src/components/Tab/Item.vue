<script setup>
import PopoverTab from "@components/Popover/Tab.vue";
import { reactive, onMounted, defineProps } from "vue";

const props = defineProps({
  // Current clicked tab on a group
  active: {
    type: String,
    required: true,
  },
  // Name to identify tab and compare with other tabs
  name: {
    type: String,
    required: true,
  },
  // For popover
  desc: {
    type: String,
    required: true,
  },
  // Additionnal styles
  first: {
    type: Boolean,
    required: false,
  },
  last: {
    type: Boolean,
    required: false,
  },
});

// Different style for desktop and mobile
const tab = reactive({
  isMobile: false,
});

onMounted(() => {
  // When component is created but before is insert on DOM
  // Check window width to determine we need to display mobile or desktop tab design
  tab.isMobile = window.innerWidth >= 768 ? false : true;
  window.addEventListener("resize", () => {
    tab.isMobile = window.innerWidth >= 768 ? false : true;
  });
});
</script>

<template>
  <div
    role="tab"
    :class="[
      tab.isMobile ? 'plugin-tab-mobile-btn' : 'plugin-tab-btn',
      props.active === props.name ? 'active' : '',
      props.first ? 'first' : '',
      props.last ? 'last' : '',
    ]"
    :aria-current="props.active === props.name ? 'true' : 'false'"
  >
    <span class="w-full flex justify-between items-center">
      <span
        :class="[tab.isMobile ? 'plugin-tab-mobile-name' : 'plugin-tab-name']"
        >{{ props.name }}</span
      >
      <PopoverTab tag="div"> {{ props.desc }}</PopoverTab>
    </span>
  </div>
</template>
