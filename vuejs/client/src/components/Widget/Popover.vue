<script setup>
import { reactive, onMounted, defineProps } from "vue";
import { contentIndex } from "@utils/tabindex.js";

const props = defineProps({
  content: {
    type: String,
    required: false,
  },
  icon : {
    type: String,
    required: false,
  },
  iconClass: {
    type: String,
    required: false,
  },
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
});

// Different style for desktop and mobile
const tab = reactive({
  isMobile: false,
  // format label to fit id
  id: props.content.trim().toLowerCase().replaceAll(" ", "-").substring(0, 15) + "popover",
});

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
  <component
    :tabindex="contentIndex"
    :aria-controls="`${tab.id}`"
    :aria-expanded="popover.isOpen ? 'true' : 'false'"
    :aria-describedby="`${tab.id}-text`"
    :is="props.tag"
    role="button"
    @focusin="showPopover()"
    @focusout="hidePopover()"
    @pointerover="showPopover()"
    @pointerleave="hidePopover()"
    class="cursor-pointer flex justify-start w-full"
  >
    <span :id="`${tab.id}-text`" class="sr-only">
      {{ $t("dashboard_popover_button_desc") }}
    </span>
    <svg
      role="img"
      aria-hidden="true"
      class="popover-settings-svg"
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 512 512"
    >
      <path
        d="M256 512c141.4 0 256-114.6 256-256S397.4 0 256 0S0 114.6 0 256S114.6 512 256 512zM216 336h24V272H216c-13.3 0-24-10.7-24-24s10.7-24 24-24h48c13.3 0 24 10.7 24 24v88h8c13.3 0 24 10.7 24 24s-10.7 24-24 24H216c-13.3 0-24-10.7-24-24s10.7-24 24-24zm40-144c-17.7 0-32-14.3-32-32s14.3-32 32-32s32 14.3 32 32s-14.3 32-32 32z"
      />
    </svg>
  </component>
  <div
    :id="`${tab.label}-popover-${tab.id}`"
    role="status"
    :aria-hidden="popover.isOpen ? 'false' : 'true'"
    v-show="popover.isOpen"
    :class="['popover-settings-container']"
    :aria-description="$t('dashboard_popover_detail_desc')"
  >
    <p :id="${tab.id}-text" class="popover-settings-text"><slot></slot></p>
  </div>
</template>