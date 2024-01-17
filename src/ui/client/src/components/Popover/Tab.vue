<script setup>
import { ref, reactive, onMounted, defineProps } from "vue";
import { contentIndex } from "@utils/tabindex.js";

const props = defineProps({
  // Sometimes we can't have a button tag (like popover on another btn)
  tag: {
    type: String,
    required: false,
    default: "button",
  },
});

// Determine popover need to be display
const popover = reactive({
  isOpen: false,
  isHover: false,
  x: "",
  y: "",
});

// Different style for desktop and mobile
const tab = reactive({
  isMobile: false,
});

const popoverIcon = ref();

onMounted(() => {
  // When component is created but before is insert on DOM
  // Check window width to determine we need to display mobile or desktop tab design
  tab.isMobile = window.innerWidth >= 768 ? false : true;
  window.addEventListener("resize", () => {
    tab.isMobile = window.innerWidth >= 768 ? false : true;
  });
});

function showPopover() {
  popover.isHover = true;
  if (tab.isMobile) {
    popover.x = `${
      popoverIcon.value.getBoundingClientRect().left + window.scrollX + 25
    }px`;
    popover.y = `${popoverIcon.value.getBoundingClientRect().top - 150}px`;
  }
  setTimeout(() => {
    popover.isOpen = popover.isHover ? true : false;
  }, 450);
}

function hidePopover() {
  popover.isHover = false;
  popover.isOpen = false;
}
</script>

<template>
  <div
    :class="[
      tab.isMobile ? 'absolute' : 'relative',
      popover.isOpen ? 'z-10' : '',
    ]"
  >
    <component
      :is="props.tag"
      :type="props.tag !== 'button' ? 'button' : false"
      @pointerover="showPopover()"
      @pointerleave="hidePopover()"
      class="cursor-pointer flex justify-start w-full"
      ref="popoverIcon"
      :tabindex="contentIndex"
    >
      <div role="img" aria-hidden="true" class="popover-background"></div>
      <svg
        role="img"
        aria-hidden="true"
        class="popover-tab-svg"
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 512 512"
      >
        <path
          d="M256 512c141.4 0 256-114.6 256-256S397.4 0 256 0S0 114.6 0 256S114.6 512 256 512zM216 336h24V272H216c-13.3 0-24-10.7-24-24s10.7-24 24-24h48c13.3 0 24 10.7 24 24v88h8c13.3 0 24 10.7 24 24s-10.7 24-24 24H216c-13.3 0-24-10.7-24-24s10.7-24 24-24zm40-144c-17.7 0-32-14.3-32-32s14.3-32 32-32s32 14.3 32 32s-14.3 32-32 32z"
        />
      </svg>
    </component>
    <div
      :style="{
        top: tab.isMobile ? popover.y : null,
        left: tab.isMobile ? popover.x : null,
      }"
      :aria-hidden="popover.isOpen ? 'false' : 'true'"
      v-show="popover.isOpen"
      :class="['popover-tab-container', tab.isMobile ? 'mobile' : 'desktop']"
    >
      <p class="popover-tab-text"><slot></slot></p>
    </div>
  </div>
</template>
