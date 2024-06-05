<script setup>
import { computed, ref, watch, onBeforeMount, onMounted } from "vue";
import { contentIndex } from "@utils/tabindex.js";
import { useEventStore } from "@store/event.js";
import Container from "@components/Widget/Container.vue";
import Icons from "@components/Widget/Icons.vue";

/** 
  @name Widget/Button.vue
  @description This component is a standard button.
  You can link this button to the event store on click with eventAttr.
  This will allow you to share a value with other components, for example switching form on a click.
  The eventAttr object must contain the store name and the value to send on click at least.
  It can also contain the target id element and the expanded value, this will add additionnal accessibility attributs to the button.
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
    eventAttr: {"store" : "modal", "value" : "open", "target" : "modal_id", "valueExpanded" : "open"},7
  }
  @param {string} id
  @param {string} text - Content of the button. Can be a translation key or by default raw text.
  @param {string} [type="button"] - Can be of type button || submit
  @param {boolean} [disabled=false]
  @param {boolean} [hideText=false] - Hide text to only display icon
  @param {string} [color="primary"] 
  @param {string} [size="normal"] - Can be of size sm || normal || lg || xl
  @param {string} [iconName=""] - Name in lowercase of icons store on /Icons. If falsy value, no icon displayed.
  @param {string} [iconColor=""]
  @param {object} [eventAttr={}] - Store event on click {"store" : <store_name>, "default" : <default_value>,  "value" : <value_stored_on_click>, "target"<optional> : <target_id_element>, "valueExpanded" : "expanded_value"}
  @param {string|number} [tabId=contentIndex] - The tabindex of the field, by default it is the contentIndex
*/

const eventStore = useEventStore();

const props = defineProps({
  id: {
    type: String,
    required: true,
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
  // {"store" : <store_name>, "default" : <default_value>,  "value" : <value_stored_on_click>, "target"<optional> : <target_id_element>, "valueExpanded" : "expanded_value"}
  // type will add additionnal accessibility attributs to the button
  // for example, if button open a modal : {"store" : "modal", "default" : "close", "value" : "open", "target" : "modal_id", "valueExpanded" : "open"}
  eventAttr: {
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
  updateData();
});

watch(eventStore, () => {
  updateData();
});

function updateData(isClick = false) {
  const isStore = props.eventAttr?.store ? true : false;
  const isValue = props.eventAttr?.value ? true : false;
  const isDefault = props.eventAttr?.default ? true : false;
  if (!isStore || !isValue || !isDefault) return;

  isClick
    ? eventStore.updateEvent(props.eventAttr.store, props.eventAttr.value)
    : eventStore.addEvent(props.eventAttr.store, props.eventAttr.default);

  try {
    const expanded = props.eventAttr?.valueExpanded
      ? props.eventAttr.valueExpanded ===
        eventStore.getEvent(props.eventAttr.store)
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
    const controls = props.eventAttr?.target ? props.eventAttr.target : false;
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
