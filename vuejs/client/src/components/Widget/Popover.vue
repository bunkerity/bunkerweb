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
  @name Widget/Popover.vue
  @description This component is a standard popover.
  @example
  {
    text: "This is a popover text",
    href: "#",
    iconName: "info",
    attrs: { "data-popover": "test" },
  }
  @param {string} text - Content of the popover. Can be a translation key or by default raw text.
  @param {string} [href="#"] - Link of the anchor. By default it is a # link.
  @param {string} color - Color of the icon between tailwind colors
  @param {object} [attrs={}] - List of attributs to add to the text.
  @param {string} [tag="a"] - By default it is a anchor tag, but we can use other tag like div in case of popover on another anchor
  @param {string} [iconClass="icon-default"]
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

function showPopover() {
  popover.isHover = true;

  // Position popover relative to btn
  const popoverBtnRect = popoverBtn.value.getBoundingClientRect();
  popoverContainer.value.style.right = `${
    window.innerWidth - popoverBtnRect.left - popoverBtnRect.width / 1.5
  }px`;

  // We need to take care of parent padding and margin that will affect dropdown position but aren't calculate in rect
  const parents = [];
  const firstParent = popoverBtn.value.parentElement;
  const firstParentY = firstParent.getBoundingClientRect().y || 0;
  let isParent = popoverBtn.value.parentElement ? true : false;
  if (isParent) parents.push(firstParent);

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
    firstParentY +
    window.scrollY -
    noRectParentHeight -
    popoverBtnRect.height -
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
