<script setup>
import { reactive, ref, watch, defineProps, onMounted } from "vue";
import { contentIndex } from "@utils/tabindex.js";
import { v4 as uuidv4 } from "uuid";
import Icons from "@components/Widget/Icons.vue";
import { set } from "@vueuse/core";

/**
  @name Widget/Popover.vue
  @description This component is a standard popover.
  @example
  {
    text: "This is a popover text",
    iconName: "info",
    iconColor: "info",
  }
  @param {string} text - Content of the button. Can be a translation key or by default raw text.
  @param {string} iconName - Name in lowercase of icons store on /Icons. If falsy value, no icon displayed.
  @param {string} iconColor - Color of the icon between tailwind colors
  @param {string} [tag="button"] - By default it is a button tag, but we can use other tag like div in case of popover on another button
  @param {string} [popoverClass=""] - Additional class for the popover container
  @param {string|number} [tabId=contentIndex] - The tabindex of the field, by default it is the contentIndex
*/

const props = defineProps({
  text: {
    type: String,
    required: false,
  },
  iconName: {
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
    default: "div",
  },
  popoverClass: {
    type: String,
    required: false,
    default: "",
  },
  tabId: {
    type: String,
    required: false,
    default: contentIndex,
  },
});

// Determine popover need to be display
const popover = reactive({
  isOpen: false,
  isHover: false,
  id: uuidv4(),
});

const popoverContainer = ref();
const popoverBtn = ref();

function showPopover() {
  popover.isHover = true;

  // Position popover relative to btn
  const popoverBtnRect = popoverBtn.value.getBoundingClientRect();
  const popoverContainerRect = popoverContainer.value.getBoundingClientRect();

  popoverContainer.value.style.right = `${
    window.innerWidth - popoverBtnRect.left - popoverBtnRect.width
  }px`;

  // We need to take care of parent padding and margin that will affect dropdown position but aren't calculate in rect
  const parents = [popoverBtn.value.parentElement];
  let isParent = popoverBtn.value.parentElement ? true : false;
  while (isParent) {
    parents.push(parents[parents.length - 1].parentElement);
    isParent = parents[parents.length - 1].parentElement ? true : false;
  }

  let noRectParentHeight = 0;
  for (let i = 0; i < parents.length; i++) {
    try {
      noRectParentHeight += +window
        .getComputedStyle(parents[i], null)
        .getPropertyValue("padding-top")
        .replace("px", "");
    } catch (e) {}

    try {
      noRectParentHeight += +window
        .getComputedStyle(parents[i], null)
        .getPropertyValue("margin-top")
        .replace("px", "");
    } catch (e) {}
  }

  popoverContainer.value.style.top = `${
    window.scrollY +
    popoverBtnRect.top -
    noRectParentHeight -
    popoverBtnRect.height * 2 -
    80
  }px`;

  // Show popover
  setTimeout(() => {
    popover.isOpen = popover.isHover ? true : false;
  }, 450);
}

function hidePopover() {
  popover.isHover = false;
  popover.isOpen = false;
}

// Close select dropdown when clicked outside element
watch(popover, () => {
  if (popover.isOpen) {
    window.addEventListener("scroll", hidePopover, true);
  } else {
    window.removeEventListener("scroll", hidePopover, true);
  }
});

onMounted(() => {
  // Close select dropdown when clicked outside element
  window.addEventListener("click", (e) => {
    if (
      popover.isOpen &&
      !popoverContainer.value.contains(e.target) &&
      !popoverBtn.value.contains(e.target)
    ) {
      hidePopover();
    }
  });
});

onMounted(() => {
  // random num between 0 and 100 with floats
  const randomNum = Math.random() * 10;
  setTimeout(() => {
    popover.id = uuidv4();
  }, randomNum);
});
</script>

<template>
  <component
    ref="popoverBtn"
    :tabindex="props.tabId"
    :aria-controls="`${popover.id}-popover-text`"
    :aria-expanded="popover.isOpen ? 'true' : 'false'"
    :aria-labelledby="`${popover.id}-popover-text`"
    :is="props.tag"
    role="button"
    @click.prevent
    @focusin="showPopover()"
    @focusout="hidePopover()"
    @pointerover="showPopover()"
    @pointerleave="hidePopover()"
    :class="['popover-btn', props.popoverClass]"
  >
    <Icons
      :iconClass="'popover-svg'"
      :iconName="props.iconName"
      :iconColor="props.iconColor"
    />
  </component>
  <div
    ref="popoverContainer"
    :id="`${popover.id}-popover-container`"
    role="status"
    :aria-hidden="popover.isOpen ? 'false' : 'true'"
    :class="[
      'popover-container',
      props.iconColor,
      popover.isOpen ? 'open' : 'close',
    ]"
    :aria-description="$t('dashboard_popover_detail_desc')"
  >
    <p :id="`${popover.id}-popover-text`" class="popover-text">
      {{ $t(props.text, props.text) }}
    </p>
  </div>
</template>
