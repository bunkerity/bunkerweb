<script setup>
import { onMounted, reactive, ref } from "vue";

const props = defineProps({
  name: {
    type: String,
    required: true,
  },
  placeholder: {
    type: String,
    required: true,
  },
  pattern: {
    type: String,
    required: false,
    default: "(.*?)",
  },
  type: {
    type: String,
    required: true,
    default: "text",
  },
  required: {
    type: Boolean,
    required: false,
    default: false,
  },
  maxlength: {
    type: [Number, String, Boolean],
    required: false,
    default: false,
  },
  minlength: {
    type: [Number, String, Boolean],
    required: false,
    default: false,
  },
  value: {
    type: String,
    required: false,
    default: "",
  },
});

const inputEl = ref(null);

// Avoid mutating a prop directly since the value will be overwritten
const inp = reactive({
  value: props.value,
  isValid: false,
});

const inpEl = ref(null);
onMounted(() => {
  inp.isValid = inputEl.value.checkValidity();

  if (props.maxlength) inpEl.value.setAttribute("maxlength", props.maxlength);
  if (props.minlength) inpEl.value.setAttribute("minlength", props.minlength);
});
</script>

<template>
  <div class="relative flex flex-col items-start">
    <span
      v-if="props.required"
      class="font-bold text-red-500 absolute right-[5px] top-[-20px]"
      >*
    </span>
    <input
      tabindex="1"
      ref="inputEl"
      v-model="inp.value"
      @input="
        () => {
          inp.isValid = inputEl.checkValidity();
          $emit('inp', inp.value);
        }
      "
      :id="props.name"
      :class="['input-regular', inp.isValid ? 'valid' : 'invalid']"
      :required="props.required || false"
      :disabled="props.disabled || false"
      :placeholder="props.placeholder || ''"
      :pattern="props.pattern"
      :name="props.name"
      :value="inp.value"
      :type="props.type"
    />
    <p
      :aria-hidden="inp.isValid ? 'true' : 'false'"
      role="alert"
      :class="[inp.isValid ? 'invisible' : 'visible']"
      class="text-red-500 text-[0.8rem] font-semibold mb-0"
    >
      {{
        inp.isValid
          ? $t("inp_input_valid")
          : !inp.value
            ? $t("inp_input_error_required")
            : $t("inp_input_error_format")
      }}
    </p>
  </div>
</template>
