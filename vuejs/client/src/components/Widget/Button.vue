<script setup>
import { computed, ref, watch, onBeforeMount, onMounted } from "vue";
import { contentIndex } from "@utils/tabindex.js";
import Container from "@components/Widget/Container.vue";
import Icons from "@components/Widget/Icons.vue";
import { v4 as uuidv4 } from "uuid";

/** 
  @name Widget/Button.vue
  @description This component is a standard button.
  You can link this button to the event store with the clickAttr object.
  This will allow you to share a value with other components, for example switching form on a click.
  The prop attrs is an object that can contain multiple attributes to add to the button.
  @example
  {
    id: "open-modal-btn",
    text: "Open modal",
    disabled: false,
    hideText: true,
    color: "green",
    size: "normal",
    iconName: "modal",
    iconColor: "white",
    attrs: [
      { key: "modal", defaultValue: "close", clickValue: "open", targetId: "modal_id", valueExpanded: "open" },
    ],
  }
  @param {string} [id=uuid()] - Unique id of the button
  @param {string} text - Content of the button. Can be a translation key or by default raw text.
  @param {string} [type="button"] - Can be of type button || submit
  @param {boolean} [disabled=false]
  @param {boolean} [hideText=false] - Hide text to only display icon
  @param {string} [color="primary"] 
  @param {string} [size="normal"] - Can be of size sm || normal || lg || xl
  @param {string} [iconName=""] - Name in lowercase of icons store on /Icons. If falsy value, no icon displayed.
  @param {string} [iconColor=""]
  @param {Object} [attrs={}] - List of attributs to add to the button. Some attributs will conduct to additionnal script
  @param {string|number} [tabId=contentIndex] - The tabindex of the field, by default it is the contentIndex
*/

const props = defineProps({
  id: {
    type: String,
    required: false,
    default: uuidv4(),
  },
  // valid || delete || info
  text: {
    type: String,
    required: true,
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

const btnEl = ref();

const buttonClass = computed(() => {
  return `btn ${props.color} ${props.size}`;
});

onMounted(() => {
  setAttrs();
});

function setAttrs() {
  for (const [key, value] of Object.entries(props.attrs)) {
    btnEl.value.setAttribute(key, value);
  }
}
</script>

<template>
  <Container
    :containerClass="`${props.containerClass}`"
    :columns="props.columns"
  >
    <button
      :type="props.type"
      ref="btnEl"
      :id="props.id"
      @click.prevent=""
      :tabindex="props.tabId"
      :class="[buttonClass]"
      :disabled="props.disabled || false"
      :aria-describedby="`text-${props.id}`"
    >
      <span
        :class="[
          props.hideText ? 'sr-only' : '',
          props.iconName ? 'mr-2' : '',
          'pointer-events-none',
        ]"
        :id="`text-${props.id}`"
        >{{ $t(props.text, props.text) }}</span
      >
      <Icons
        v-if="props.iconName"
        :iconName="props.iconName"
        :iconClass="'btn-svg'"
        :iconColor="props.iconColor"
      />
    </button>
  </Container>
</template>
