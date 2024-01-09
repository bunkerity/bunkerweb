<script setup>
import { onMounted, reactive, ref } from "vue";

const props = defineProps({
  label: {
    type: String,
    required: true,
  },
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
  isInvalid: {
    type: Boolean,
    required: false,
    default: false,
  },
  invalidText: {
    type: String,
    required: false,
    default: "",
  },
});

// Avoid mutating a prop directly since the value will be overwritten
const inp = reactive({
  value: props.value,
});

const inpEl = ref(null);
onMounted(() => {
  if (props.maxlength) inpEl.value.setAttribute("maxlength", props.maxlength);
  if (props.minlength) inpEl.value.setAttribute("minlength", props.minlength);
});
</script>

<template>
  <label :for="props.name" class="logout-label">
    {{ props.label }}
  </label>
  <input
    ref="inpEl"
    v-model="inp.value"
    @input="(e) => $emit('inp', inp.value)"
    :type="props.type"
    :id="props.name"
    :name="props.name"
    class="logout-input"
    :class="[props.isInvalid ? `invalid` : '']"
    :placeholder="props.placeholder"
    :pattern="props.pattern"
    :required="props.required"
    :value="inp.value"
  />
  <strong
    :aria-hidden="props.isInvalid ? 'false' : 'true'"
    :class="[props.isInvalid && props.invalidText ? 'block' : 'hidden']"
    class="font-normal text-sm text-red-500"
    >{{ props.invalidText }}
  </strong>
</template>
