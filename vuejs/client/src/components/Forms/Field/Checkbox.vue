<script setup>
import { reactive, defineProps, onMounted, ref } from "vue";
import { contentIndex } from "@utils/tabindex.js";
import Container from "@components/Widget/Container.vue";
import Header from "@components/Forms/Header/Field.vue";

/*
  COMPONENT DESCRIPTION
  *
  *
  This checkbox component is used to create a complete checkbox (label, validator message).
  It is mainly use for checkbox setting form.  
  *
  *
  PROPS ARGUMENTS
  *
  *
  id: string,
  columns: object,
  value: string,
  disabled: boolean,
  required: boolean,
  label: string,
  name: string,
  version: string,
  hideLabel: boolean,
  required: boolean,
  containerClass: string,
  headerClass: string,
  inpClass: string,
  tabId: string || number,
  *
  *
  PROPS EXAMPLE
*/

const props = defineProps({
  // id && value && method
    id: {
        type: String,
        required: true,
    },
    columns: {
      type: [Object, Boolean],
      required: false,
      default : false
    },
    value: {
        type: String,
        required: true,
    },
    disabled: {
        type: Boolean,
        required: false,
    },
    required: {
        type: Boolean,
        required: false,
    },
    label: {
        type: String,
        required: true,
    },
    name: {
        type: String,
        required: true,
    },
    version: {
        type: String,
        required: false,
    },
    hideLabel: {
        type: Boolean,
        required: false,
    },
    containerClass : {
      type: String,
      required: false
    },
    headerClass: {
        type: String,
        required: false,
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
  <Container :containerClass="`w-full m-1 p-1 ${props.containerClass}`" :columns="props.columns">
  <Header :required="props.required" :name="props.name" :label="props.label" :hideLabel="props.hideLabel" :headerClass="props.headerClass" />

  <div class="relative z-10 flex flex-col items-start">
    <input
      ref="checkboxEl"
      :tabindex="props.tabId || contentIndex"
      @keyup.enter="$emit('inp', updateValue())"
      @click="$emit('inp', updateValue())"
      :id="props.id"
      :name="props.name"
      :disabled="props.disabled || false"
      :checked="checkbox.value === 'yes' ? true : false"
      :class="[
        'checkbox',
        checkbox.value === 'yes' ? 'check' : '',
        checkbox.isValid ? 'valid' : 'invalid',
        props.inpClass,
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
</Container>
</template>