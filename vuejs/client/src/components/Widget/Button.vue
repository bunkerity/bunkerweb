<script setup>
import { computed, ref, watch, onBeforeMount, onMounted } from "vue";
import { contentIndex } from "@utils/tabindex.js";
import { useEventStore } from "@store/event.js";
import Container from "@components/Widget/Container.vue";
import Icons from "@components/Widget/Icons.vue";
import { v4 as uuidv4 } from "uuid";

/** 
  @name Widget/Button.vue
  @description This component is a standard button.
  You can link this button to the event store with the clickAttr object.
  This will allow you to share a value with other components, for example switching form on a click.
  The clickAttr object must contain at least the key, defaultValue and value to work with the event store.
  It can also contain the targetId element in case the button is linked to another element, like a modal or a sidebar.
  We can specify a valueExpanded value, we will check the current value in the store and the valueExpanded, this will update the aria-expanded attribute of the button.
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
    clickAttr: {"key" : "modal-config", "defaultValue" : "close", "clickValue" : "open", "targetId" : "modal_id", "valueExpanded" : "open"},
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
  @param {object} [clickAttr={}] - Click event manage with event store {"key" : <key_name>, "defaultValue" : <defaultValue = "set this value to store if not done">,  "clickValue" : <value_set_on_click>, "targetId"<optional> : <targetId_element="id of element link to the button event">, "valueExpanded<optional>" : <expanded_value="check current value in store and this value to determine a expanded true or false">}
  @param {array} [staticAttr=[]] - Static attributes that can be useful to do some check with script (for example {"data-attr" : "value"} will add data-attr="value" to the button)
  @param {string|number} [tabId=contentIndex] - The tabindex of the field, by default it is the contentIndex
*/

const eventStore = useEventStore();

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
  // Example of button opening a modal : {"key" : "modal", "defaultValue" : "close", "clickValue" : "open", "targetId" : "modal_id", "valueExpanded" : "open"}
  clickAttr: {
    type: Object,
    required: false,
    default: {},
  },
  staticAttr: {
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
  setStaticAttr();
  updateData();
});

watch(eventStore, () => {
  updateData();
});

function setStaticAttr() {
  for (const [key, value] of Object.entries(props.staticAttr)) {
    btnEl.value.setAttribute(key, value);
  }
}

function updateData(isClick = false) {
  const isKey = props.clickAttr?.key ? true : false;
  const isValue = props.clickAttr?.clickValue ? true : false;
  const isDefault = props.clickAttr?.defaultValue ? true : false;
  if (!isKey || !isValue || !isDefault) return;

  isClick
    ? eventStore.updateEvent(props.clickAttr.key, props.clickAttr.clickValue)
    : eventStore.addEvent(props.clickAttr.key, props.clickAttr.defaultValue);

  try {
    const expanded = props.clickAttr?.valueExpanded
      ? props.clickAttr.valueExpanded ===
        eventStore.getEvent(props.clickAttr.key)
        ? "true"
        : "false"
      : false;
    if (expanded) {
      btnEl.value.setAttribute("aria-expanded", expanded);
    }

    if (!expanded) {
      btnEl.value.removeAttribute("aria-expanded");
    }
  } catch (e) {}

  try {
    const controls = props.clickAttr?.targetId
      ? props.clickAttr.targetId
      : false;
    if (controls) {
      btnEl.value.setAttribute("aria-controls", controls);
    }

    if (!controls) {
      btnEl.value.removeAttribute("aria-controls");
    }
  } catch (e) {}
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
      @click="updateData(true)"
      :id="props.id"
      :tabindex="props.tabId"
      :class="[buttonClass]"
      :disabled="props.disabled || false"
      :aria-describedby="`text-${props.id}`"
    >
      <span
        :class="[props.hideText ? 'sr-only' : '', props.iconName ? 'mr-2' : '']"
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
