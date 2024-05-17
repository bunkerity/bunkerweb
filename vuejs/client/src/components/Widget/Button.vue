<script setup>
import { computed, ref, watch, onBeforeMount, onMounted } from 'vue';
import { contentIndex } from "@utils/tabindex.js";
import { useEventStore } from "@store/event.js";
import Container from "@components/Widget/Container.vue";
import IconAdd from "@components/Icons/Button/Add.vue";


/*
  COMPONENT DESCRIPTION
  *
  *
  This button component is a standard button.
  We can link this button to a store on click with eventAttr.

  Stores allow to share a value with other components, for example switching form on a click.
  We need to determine the store name and the value to send on click.
  *
  *
  PROPS ARGUMENTS
  *
  *
    id: string,
    text: string,
    type: string<"button"|"submit">,
    disabled: boolean,
    hideText: boolean,
    color: string,
    size: string<"sm"|"normal"|"lg"|"xl">,
    iconName: string,
    iconColor: string,
    eventAttr: object,
    tabId: string || number,
  *
  *
  PROPS EXAMPLE
  *
  *
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
  *
  *
*/

const eventStore = useEventStore();

const props = defineProps({
    id : {
        type: String,
        required: true,
    },
  // valid || delete || info
  text : {
    type: String,
    required: true
  },
  type : {
    type: String,
    required: false,
    default : "button"
  },
  disabled : {
    type: Boolean,
    required: false,
    default : false
  },
  // case we want only icon but we need to add accessibility data
  hideText : {
    type: Boolean,
    required: false,
    default : false
  },
  color: {
    type: String,
    required: false,
    default : "primary"
  },
  // sm || normal || lg || xl
  size: {
    type: String,
    required: false,
    default : "normal"
  },
  // Store on components/Icons/Button
  // Check import ones
  iconName : {
    type: String,
    required: false,
    default : "",
  },
  // Defined on input.css
  iconColor : {
    type: String,
    required: false,
    default : ""
  },
  // {"store" : <store_name>, "default" : <default_value>,  "value" : <value_stored_on_click>, "target"<optional> : <target_id_element>, "valueExpanded" : "expanded_value"}
  // type will add additionnal accessibility attributs to the button
  // for example, if button open a modal : {"store" : "modal", "value" : "open", "target" : "modal_id", "valueExpanded" : "open"}
  eventAttr: {
    type: Object,
    required: false,
    default : {}
  },
  tabId : {
    type: [String, Number],
    required: false,
    default : ""
  }
});

const btnEl = ref();

const buttonClass = computed(() => {
    return `btn btn-${props.color} btn-${props.size}`
})

onMounted(() => {
    updateData();
})

watch(eventStore,() => {
    updateData();
})

function updateData(isClick = false) {
    const isStore = props.eventAttr?.store ? true : false;
    const isValue = props.eventAttr?.value ? true : false;
    const isDefault = props.eventAttr?.default ? true : false;

    if(!isStore || !isValue || !isDefault) return;

    isClick ? eventStore.updateEvent(props.eventAttr.store, props.eventAttr.value) : eventStore.addEvent(props.eventAttr.store, props.eventAttr.default);

    try {
    const expanded = props.eventAttr?.valueExpanded ? props.eventAttr.valueExpanded === eventStore.getEvent(props.eventAttr.store) ? 'true' : 'false'  : false;
        if(expanded) {
            btnEl.value.setAttribute('aria-expanded', expanded);
        }

        if(!expanded) {
            btnEl.value.removeAttribute('aria-expanded');
        }
    }catch(e) {
    }

    try {
    const controls = props.eventAttr?.target ? props.eventAttr.target : false;
        if(controls) {
            btnEl.value.setAttribute('aria-controls', controls);
        }

        if(!controls) {
            btnEl.value.removeAttribute('aria-controls');
        }
    }catch(e) {

    }
}
</script>

<template>
<Container :containerClass="`w-full m-2 ${props.containerClass}`" :columns="props.columns">
  <button :type="props.type" ref="btnEl" @click="updateData(true)" :id="props.id"
  :tabindex="props.tabId || contentIndex"
  :class="[buttonClass]"
  :disabled="props.disabled || false"
  :aria-describedby="`${props.id}-text`"
  >
    <span :class="[props.hideText ? 'sr-only' : '', 
    props.iconName ? 'mr-2' : ''
    ]" :id="`${props.id}-text`">{{ props.text }}</span>
    <IconAdd v-if="props.iconName === 'add'" :iconName="props.iconName" :iconColor="props.iconColor" />
  </button>
</Container>
</template>
