<script setup>
import { onMounted, reactive, ref } from "vue";
import Text from "@components/Widget/Text.vue";

/** 
  @name Message/Unmatch.vue
  @description Display a default message "no match" with dedicated icon.
  The message text can be overriden by passing a text prop.
  @example
  {
    text: "dashboard_no_match",
  }
  @param {string} text - The text to display
  @param {string} [unmatchClass=""] - The class to apply to the message. If not provided, the class will be based on the parent component.
*/

const props = defineProps({
  text: {
    type: String,
    required: false,
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
  msg.class =
    props.unmatchClass || msgEl.value.closest("[data-is]")
      ? `msg-unmatch-${msgEl.value
          .closest("[data-is]")
          .getAttribute("data-is")}`
      : "msg-unmatch-base";
});
</script>

<template>
  <div class="msg-container" ref="msgEl">
    <div data-is="unmatch" :class="[msg.class]">
      <Text :icon="{ iconName: 'search' }" :text="msg.text" />
    </div>
  </div>
</template>
