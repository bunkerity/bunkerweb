<script setup>
import {
  reactive,
  ref,
  watch,
  defineProps,
  onMounted,
  onBeforeMount,
} from "vue";
import { contentIndex } from "@utils/tabindex.js";
import { useUUID } from "@utils/global.js";
import Icons from "@components/Widget/Icons.vue";

/**
 *  @name Widget/Popover.vue
 *  @description This component is a standard popover.
 *  @example
 *  {
 *    text: "This is a popover text",
 *    href: "#",
 *    iconName: "info",
 *    attrs: { "data-popover": "test" },
 *  }
 *  @param {String} text - Content of the popover. Can be a translation key or by default raw text.
 *  @param {String} [href="#"] - Link of the anchor. By default it is a # link.
 *  @param {String} color - Color of the icon between tailwind colors
 *  @param {Object} [attrs={}] - List of attributs to add to the text.
 *  @param {String} [tag="a"] - By default it is a anchor tag, but we can use other tag like div in case of popover on another anchor
 *  @param {String} [iconClass="icon-default"]
 *  @param {String|Number} [tabId=contentIndex] - The tabindex of the field, by default it is the contentIndex
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
  color: {
    type: String,
    required: false,
  },
  // Sometimes we can't have an anchor tag
  tag: {
    type: String,
    required: false,
    default: "a",
  },
  iconClass: {
    type: String,
    required: false,
    default: "icon-default",
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
  color: "",
});

const popoverContainer = ref();
const popoverBtn = ref();

/**
 *  @name showPopover
 *  @description Show the popover and set the position of the popover relative to the container.
 *  @returns {Void}
 */
function showPopover() {
  popover.isHover = true;

  // Position popover relative to btn
  const popoverBtnRect = popoverBtn.value.getBoundingClientRect();
  popoverContainer.value.style.right = `${
    window.innerWidth - popoverBtnRect.left - popoverBtnRect.width / 1.5
  }px`;

  // Show popover
  setTimeout(() => {
    popover.isOpen = popover.isHover ? true : false;
  }, 450);
}

/**
 *  @name hidePopover
 *  @description Hide the popover.
 *  @returns {Void}
 */
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

onBeforeMount(() => {
  popover.id = useUUID();
});

onMounted(() => {
  // Set props color or the default icon color
  popover.color =
    props.color || popoverBtn.value.querySelector("[data-svg]")
      ? popoverBtn.value.querySelector("[data-svg]").getAttribute("data-color")
      : "info";

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
    :class="['popover-btn']"
  >
    <Icons :iconName="props.iconName" />
  </component>
  <div
    ref="popoverContainer"
    :id="`${popover.id}-popover-container`"
    role="status"
    :aria-hidden="popover.isOpen ? 'false' : 'true'"
    :class="[
      'popover-container bg-el',
      popover.color,
      popover.isOpen ? 'open' : 'close',
    ]"
    :aria-description="$t('dashboard_popover_detail_desc')"
  >
    <p :id="`${popover.id}-popover-text`" class="popover-text">
      {{ $t(props.text, $t("dashboard_placeholder", props.text)) }}
    </p>
  </div>
</template>
