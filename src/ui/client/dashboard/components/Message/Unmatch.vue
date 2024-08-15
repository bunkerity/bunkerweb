<script setup>
import { onMounted, reactive, ref } from "vue";
import Icons from "@components/Widget/Icons.vue";
import Text from "@components/Widget/Text.vue";

/**
 *  @name Message/Unmatch.vue
 *  @description Display a default message "no match" with dedicated icon.
 *  The message text can be overridden by passing a text prop.
 *  @example
 *  {
 *    text: "dashboard_no_match",
 *  }
 *  @param {String} text - The text to display
 *  @param {String} [iconName="search"] - The icon to display
 *  @param {String} [iconColor=""] - The color of the icon
 *  @param {String} [unmatchClass=""] - The class to apply to the message. If not provided, the class will be based on the parent component.
 */

const props = defineProps({
  text: {
    type: String,
    required: false,
  },
  iconName: {
    type: String,
    required: false,
    default: "search",
  },
  iconColor: {
    type: String,
    required: false,
    default: "",
  },
  unmatchClass: {
    type: String,
    required: false,
    default: "",
  },
});

const msg = reactive({
  text: "dashboard_no_match",
  class: "",
});

const msgEl = ref(null);

onMounted(() => {
  msg.text = props.text || msg.text;
});
</script>

<template>
  <div data-is="unmatch" class="msg-container" ref="msgEl">
    <Icons v-bind="{ iconName: props.iconName, color: props.iconColor }" />
    <Text :text="msg.text" />
  </div>
</template>
