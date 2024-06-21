<script setup>
import { computed, ref, reactive, onMounted } from "vue";
import { contentIndex } from "@utils/tabindex.js";
import Container from "@components/Widget/Container.vue";
import Icons from "@components/Widget/Icons.vue";
import { useUUID } from "@utils/global.js";

/** 
  @name Widget/Button.vue
  @description This component is a standard button.
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
    attrs: { data-toggle: "modal", "data-target": "#modal"},
    
  }
  @param {string} [id=uuidv4()] - Unique id of the button
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
    default: "",
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
  iconClass: {
    type: String,
    required: false,
    default: "sm",
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

const btn = reactive({
  id: "",
});

const btnEl = ref();

const buttonClass = computed(() => {
  // transparent useful when we only want to display icon without background or shadow style
  if (props.color === "transparent") return `${props.size}`;
  return `btn ${props.color} ${props.size}`;
});

onMounted(() => {
  btn.id = useUUID(props.id);
});
</script>

<template>
  <Container
    :containerClass="`${props.containerClass}`"
    :columns="props.columns"
  >
    <button
      :type="props.type"
      ref="btnEl"
      :id="btn.id"
      @click="
        (e) => {
          if (e.target.getAttribute('type') !== 'submit') e.preventDefault();
        }
      "
      v-bind="props.attrs || {}"
      :tabindex="props.tabId"
      :class="[buttonClass]"
      :disabled="props.disabled || false"
      :aria-labelledby="`text-${btn.id}`"
    >
      <span
        :class="[
          props.hideText ? 'sr-only' : '',
          props.iconName ? 'mr-2' : '',
          'pointer-events-none',
        ]"
        :id="`text-${btn.id}`"
        >{{ $t(props.text, props.text) }}
      </span>
      <Icons
        v-if="props.iconName"
        :iconName="props.iconName"
        :iconClass="`${props.iconClass} pointer-events-none`"
        :iconColor="props.iconColor"
      />
    </button>
  </Container>
</template>
