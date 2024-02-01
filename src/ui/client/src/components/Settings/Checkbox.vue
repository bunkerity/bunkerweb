<script setup>
import { reactive, defineProps, onMounted, ref } from "vue";
import { contentIndex } from "@utils/tabindex.js";

const props = defineProps({
  // id && value && method
  settings: {
    type: Object,
    required: true,
  },
  inpClass: {
    type: String,
    required: false,
  },
  tabId: {
    type: [String, Number],
    required: false,
  },
});

const checkboxEl = ref(null);

const checkbox = reactive({
  value: props.settings.value,
  isValid: false,
});

const emits = defineEmits(["inp"]);

function updateValue() {
  checkbox.value = checkbox.value === "yes" ? "no" : "yes";
  checkbox.isValid = checkboxEl.value.checkValidity();
  return checkbox.value;
}

onMounted(() => {
  checkbox.isValid = checkboxEl.value.checkValidity();
});
</script>

<template>
  <div class="relative z-10 flex flex-col items-start">
    <span
      v-if="props.settings.required"
      class="font-bold text-red-500 absolute right-[5px] top-[-20px]"
      >*
    </span>
    <input
      ref="checkboxEl"
      :tabindex="props.tabId || contentIndex"
      @keyup.enter="$emit('inp', updateValue())"
      @click="$emit('inp', updateValue())"
      :id="props.settings.id"
      :name="props.settings.id"
      :disabled="props.settings.disabled || false"
      :checked="checkbox.value === 'yes' ? true : false"
      :class="[
        'checkbox',
        checkbox.value === 'yes' ? 'check' : '',
        checkbox.isValid ? 'valid' : 'invalid',
        props.inpClass,
      ]"
      type="checkbox"
      :value="checkbox.value"
      :required="props.settings.required || false"
    />

    <svg
      role="img"
      aria-hidden="true"
      v-show="checkbox.value === 'yes'"
      class="checkbox-svg"
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 512 512"
    >
      <path
        class="pointer-events-none"
        d="M470.6 105.4c12.5 12.5 12.5 32.8 0 45.3l-256 256c-12.5 12.5-32.8 12.5-45.3 0l-128-128c-12.5-12.5-12.5-32.8 0-45.3s32.8-12.5 45.3 0L192 338.7 425.4 105.4c12.5-12.5 32.8-12.5 45.3 0z"
      ></path>
    </svg>
    <p
      :aria-hidden="checkbox.isValid ? 'true' : 'false'"
      role="alert"
      :class="[checkbox.isValid ? 'hidden' : '']"
      class="input-error-msg"
    >
      {{
        checkbox.isValid
          ? $t("inp_input_valid")
          : $t("inp_input_error_required")
      }}
    </p>
  </div>
</template>
