<script setup>
import { reactive, defineProps, onMounted, ref } from "vue";

const props = defineProps({
  name: {
    type: String,
    required: true,
  },
  required: {
    type: Boolean,
    required: false,
    default: false,
  },
  value: {
    type: String,
    required: false,
    default: "",
  },
  disabled: {
    type: Boolean,
    required: false,
    default: false,
  },
});

const checkboxEl = ref(null);

const checkbox = reactive({
  value: props.value,
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
      v-if="props.required"
      class="font-bold text-red-500 absolute right-[5px] top-[-20px]"
      >*
    </span>
    <input
      ref="checkboxEl"
      tabindex="1"
      @keyup.enter="$emit('inp', updateValue())"
      @click="$emit('inp', updateValue())"
      :id="props.name"
      :name="props.name"
      :disabled="props.disabled || false"
      :checked="checkbox.value === 'yes' ? true : false"
      :class="[
        'checkbox',
        checkbox.value === 'yes' ? 'check' : '',
        checkbox.isValid ? 'valid' : 'invalid',
      ]"
      type="checkbox"
      :value="checkbox.value"
      :required="props.required || false"
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
      :class="[checkbox.isValid ? 'invisible' : 'visible']"
      class="text-red-500 text-[0.8rem] font-semibold mb-0 mt-0.5"
    >
      {{
        checkbox.isValid
          ? $t("inp_input_valid")
          : $t("inp_input_error_required")
      }}
    </p>
  </div>
</template>
