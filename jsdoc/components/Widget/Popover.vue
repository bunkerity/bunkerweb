<script setup>
import { reactive, onMounted, defineProps } from "vue";
import { contentIndex } from "@utils/tabindex.js";

const props = defineProps({
  id: {
    type: String,
    required: true,
  },
  content: {
    type: String,
    required: false,
  },
  icon : {
    type: String,
    required: false,
  },
  iconColor: {
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
    :aria-controls="`${props.id}-popover-text`"
    :aria-expanded="popover.isOpen ? 'true' : 'false'"
    :aria-describedby="`${props.id}-popover-text`"
    :is="props.tag"
    role="button"
    @focusin="showPopover()"
    @focusout="hidePopover()"
    @pointerover="showPopover()"
    @pointerleave="hidePopover()"
    class="cursor-pointer flex justify-start w-full"
  >
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
    :id="`${props.id}-popover-container`"
    role="status"
    :aria-hidden="popover.isOpen ? 'false' : 'true'"
    v-show="popover.isOpen"
    :class="['popover-settings-container']"
    :aria-description="$t('dashboard_popover_detail_desc')"
  >
    <p :id="`${props.id}-popover-text`" class="popover-settings-text"><slot></slot></p>
  </div>
</template>