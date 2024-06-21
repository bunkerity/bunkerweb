<script setup>
import { reactive, ref, watch, defineProps, onMounted } from "vue";
import { contentIndex } from "@utils/tabindex.js";
import { useUUID } from "@utils/global.js";
import Icons from "@components/Widget/Icons.vue";

/**
  @name Widget/Popover.vue
  @description This component is a standard popover.
  @example
  {
    text: "This is a popover text",
    href: "#",
    iconName: "info",
    iconColor: "info",
    attrs: { "data-popover": "test" },
  }
  @param {string} text - Content of the popover. Can be a translation key or by default raw text.
  @param {string} [href="#"] - Link of the anchor. By default it is a # link.
  @param {string} iconName - Name in lowercase of icons store on /Icons. If falsy value, no icon displayed.
  @param {string} iconColor - Color of the icon between tailwind colors
  @param {object} [attrs={}] - List of attributs to add to the text.
  @param {string} [tag="a"] - By default it is a anchor tag, but we can use other tag like div in case of popover on another anchor
  @param {string} [popoverClass=""] - Additional class for the popover container
  @param {string} [svgSize="base"] - Determine svg size between sm, md, base and lg.
  @param {string|number} [tabId=contentIndex] - The tabindex of the field, by default it is the contentIndex
*/

const props = defineProps({
  text: {
    type: String,
    required: false,
  },
  href: {
    type: String,
    required: false,
    default: "#",
  },
  iconName: {
    type: String,
    required: false,
  },
  iconColor: {
    type: String,
    required: false,
  },
  // Sometimes we can't have an anchor tag
  tag: {
    type: String,
    required: false,
    default: "a",
  },
  popoverClass: {
    type: String,
    required: false,
    default: "",
  },
  svgSize: {
    type: String,
    required: false,
    default: "base",
  },
  tabId: {
    type: String,
    required: false,
    default: contentIndex,
  },
});

// Determine popover need to be display
const popover = reactive({
  id: "",
  isOpen: false,
  isHover: false,
});

const popoverContainer = ref();
const popoverBtn = ref();

function showPopover() {
  popover.isHover = true;

  // Position popover relative to btn
  const popoverBtnRect = popoverBtn.value.getBoundingClientRect();

  popoverContainer.value.style.right = `${
    window.innerWidth - popoverBtnRect.left - popoverBtnRect.width / 1.5
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
    popoverBtnRect.height * 1.5 -
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
  popover.id = useUUID();
  // Remove href if tag is not an anchor
  if (props.tag !== "a") {
    popoverBtn.value.removeAttribute("href");
  }

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
</script>

<template>
  <component
    v-bind="props.attrs"
    ref="popoverBtn"
    :tabindex="props.tabId"
    :aria-controls="`${popover.id}-popover-text`"
    :aria-expanded="popover.isOpen ? 'true' : 'false'"
    :aria-labelledby="`${popover.id}-popover-text`"
    :is="props.tag"
    href="#"
    @click.prevent
    @focusin="showPopover()"
    @focusout="hidePopover()"
    @pointerover="showPopover()"
    @pointerleave="hidePopover()"
    :class="['popover-btn', props.popoverClass]"
  >
    <Icons
      :iconClass="`popover-svg ${props.svgSize}`"
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
