<script setup>
import {
  computed,
  ref,
  reactive,
  onBeforeMount,
  onMounted,
  onUnmounted,
  watch,
} from "vue";
import Modal from "@components/Widget/Modal.vue";
import { contentIndex } from "@utils/tabindex.js";
import Container from "@components/Widget/Container.vue";
import Icons from "@components/Widget/Icons.vue";
import { useUUID } from "@utils/global.js";
import { useDisplayStore } from "@store/global.js";

/**
 *  @name Widget/Button.vue
 *  @description This component is a standard button.
 *  @example
 *  {
 *    id: "open-modal-btn",
 *    text: "Open modal",
 *    disabled: false,
 *    hideText: true,
 *    color: "green",
 *    size: "normal",
 *    iconName: "modal",
 *    attrs: { data-toggle: "modal", "data-target": "#modal"},
 *  }
 *  @param {string} [id=uuidv4()] - Unique id of the button
 *  @param {string} text - Content of the button. Can be a translation key or by default raw text.
 *  @param {array} [display=[]] - Case display, we will update the display store with the given array. Useful when we want to use button as tabs.
 *  @param {string} [type="button"] - Can be of type button || submit
 *  @param {boolean} [disabled=false]
 *  @param {boolean} [hideText=false] - Hide text to only display icon
 *  @param {string} [color="primary"]
 *  @param {string} [iconColor=""] - Color we want to apply to the icon. If falsy value, default icon color is applied.
 *  @param {string} [size="normal"] - Can be of size sm || normal || lg || xl or tab
 *  @param {string} [iconName=""] - Name in lowercase of icons store on /Icons. If falsy value, no icon displayed.
 *  @param {Object} [attrs={}] - List of attributes to add to the button. Some attributes will conduct to additional script
 *  @param {Object|boolean} [modal=false] - We can link the button to a Modal component. We need to pass the widgets inside the modal. Button click will open the modal.
 *  @param {string|number} [tabId=contentIndex] - The tabindex of the field, by default it is the contentIndex
 *  @param {string} [containerClass=""] - Additional class to the container
 */

const props = defineProps({
  id: {
    type: String,
    required: false,
    default: "",
  },
  // valid || delete || info
  text: {
    type: String,
    required: true,
    default: "",
  },
  emitValue: {
    type: String,
    required: false,
    default: "",
  },
  type: {
    type: String,
    required: false,
    default: "button",
  },
  disabled: {
    type: Boolean,
    required: false,
    default: false,
  },
  // case we want only icon but we need to add accessibility data
  hideText: {
    type: Boolean,
    required: false,
    default: false,
  },
  color: {
    type: String,
    required: false,
    default: "primary",
  },
  // sm || normal || lg || xl
  size: {
    type: String,
    required: false,
    default: "normal",
  },
  // Store on components/Icons/Button
  // Check import ones
  iconName: {
    type: String,
    required: false,
    default: "",
  },
  // Defined on input.css
  iconColor: {
    type: String,
    required: false,
    default: "",
  },
  attrs: {
    type: Object,
    required: false,
    default: {},
  },
  modal: {
    type: [Object, Boolean],
    required: false,
    default: false,
  },
  display: {
    type: Array,
    required: false,
    default: [],
  },
  containerClass: {
    type: String,
    required: false,
    default: "",
  },
  tabId: {
    type: [String, Number],
    required: false,
    default: contentIndex,
  },
});

const displayStore = useDisplayStore();

const btn = reactive({
  id: "",
  openModal: false,
  modalId: props.modal ? `${props.id}-modal` : "",
  class:
    props.color === "transparent"
      ? `${props.size}`
      : `btn ${props.color} ${props.size}`,
  isActive: false,
});

const btnEl = ref();

/**
 *  @name handleClick
 *  @description Wrap all the logic to handle the click event on the button.
 *  This will prevent submit if not a submit button, open a modal if one is attached and update the display store if needed.
 *  @param {event} e - Event object
 *  @returns {void}
 */
function handleClick(e) {
  if (e.target.getAttribute("type") !== "submit") e.preventDefault();
  if (typeof props.modal === "object") {
    btn.openModal = true;
  }
  if (props.display.length) {
    console.log("update", btn.isActive);
    displayStore.setDisplay(props.display[0], props.display[1]);
  }
}

// Add a11y attributs and update when needed in case the button is related to a display group
if (props.display.length) {
  watch(displayStore.display, (val) => {
    const isCurrent = displayStore.isCurrentDisplay(
      props.display[0],
      props.display[1]
    );
    btnEl.value.setAttribute("aria-controls", btn.modalId);
    btnEl.value.setAttribute("aria-expanded", isCurrent ? "true" : "false");
    btn.isActive = isCurrent ? true : false;
  });
}

// watch openModal to add accessibility data
watch(
  () => btn.openModal,
  (value) => {
    if (typeof props.modal === "object") {
      btnEl.value.setAttribute("aria-expanded", value ? "true" : "false");
    }
  }
);

onBeforeMount(() => {
  btn.id = useUUID(props.id);
  // Case modal, add accessibility data
});

onMounted(() => {
  // Case modal, add accessibility data
  if (typeof props.modal === "object") {
    btnEl.value.setAttribute("aria-controls", btn.modalId);
    btnEl.value.setAttribute(
      "aria-expanded",
      props.openModal ? "true" : "false"
    );
  }

  if (btnEl.value?.closest("[data-is='tabs']")) {
    btnEl.value.setAttribute("role", "tab");
  }
});
</script>

<template>
  <Container data-is="button" :containerClass="`${props.containerClass}`">
    <button
      data-is="button"
      :type="props.type"
      ref="btnEl"
      :id="btn.id"
      @click="
        (e) => {
          handleClick(e);
        }
      "
      v-bind="props.attrs || {}"
      :tabindex="props.tabId"
      :class="[
        btn.class,
        btn.isActive ? 'active' : '',
        props.iconName && !props.hideText ? 'icon' : 'no-icon',
      ]"
      :disabled="props.disabled || false"
      :aria-labelledby="`text-${btn.id}`"
    >
      <span
        :class="[
          props.hideText ? 'sr-only' : '',
          props.iconName && !props.hideText ? 'mr-2' : '',
          'pointer-events-none',
        ]"
        :id="`text-${btn.id}`"
        >{{ $t(props.text, $t("dashboard_placeholder", props.text)) }}
      </span>
      <Icons
        v-if="props.iconName"
        :iconName="props.iconName"
        :color="props.iconColor"
        :disabled="props.disabled || false"
      />
    </button>

    <Modal
      :id="`${btn.id}-modal`"
      v-if="btn.openModal"
      :widgets="props.modal.widgets"
      :isOpen="btn.openModal"
      @close="btn.openModal = false"
    />
  </Container>
</template>
