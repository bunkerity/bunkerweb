<script setup>
import { reactive, onMounted, defineProps } from "vue";
import { v4 as uuidv4 } from "uuid";

const props = defineProps({
  // Sometimes we can't have a button tag (like popover on another btn)
  tag: {
    type: String,
    required: false,
    default: "button",
  },
  label: {
    type: String,
    required: false,
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
  label: props.label.trim().toLowerCase().replaceAll(" ", "-").substring(0, 15),
  id: uuidv4(),
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
    :aria-controls="`${tab.label}-popover-${tab.id}`"
    :is="props.tag"
    role="button"
    @pointerover="showPopover()"
    @pointerleave="hidePopover()"
    :aria-description="$t('dashboard_popover_button_desc')"
    class="cursor-pointer flex justify-start w-full"
  >
    <span class="sr-only"> {{ $t("dashboard_popover_button") }}</span>
    <div class="popover-background"></div>
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
    <p class="popover-settings-text"><slot></slot></p>
  </div>
</template>
