<script setup>
import { reactive, defineProps, ref, onMounted, onBeforeMount } from "vue";
import { contentIndex } from "@utils/tabindex.js";
import Container from "@components/Widget/Container.vue";
import Header from "@components/Forms/Header/Field.vue";
import ErrorField from "@components/Forms/Error/Field.vue";
import { useUUID } from "@utils/global.js";

/**
 *  @name Forms/Field/Checkbox.vue
 *  @description This component is used to create a complete checkbox field input with error handling and label.
 *  We can also add popover to display more information.
 *  It is mainly use in forms.
 *  @example
 *  {
 *    columns : {"pc": 6, "tablet": 12, "mobile": 12},
 *    id:"test-check",
 *    value: "yes",
 *    label: "Checkbox",
 *    name: "checkbox",
 *    required: true,
 *    hideLabel: false,
 *    inpType: "checkbox",
 *    headerClass: "text-red-500"
 *    popovers : [
 *      {
 *        text: "This is a popover text",
 *        iconName: "info",
 *      },
 *    ]
 *  }
 *  @param {String} [id=uuidv4()] - Unique id
 *  @param {String} label - The label of the field. Can be a translation key or by default raw text.
 *  @param {String} name - The name of the field. Case no label, this is the fallback. Can be a translation key or by default raw text.
 *  @param {String} value
 *  @param {Object} [attrs={}] - Additional attributes to add to the field
 *  @param {Array} [popovers=[]] - List of popovers to display more information
 *  @param {String} [inpType="checkbox"]  - The type of the field, useful when we have multiple fields in the same container to display the right field
 *  @param {Boolean} [disabled=false]
 *  @param {Boolean} [required=false]
 *  @param {Object} [columns={"pc": "12", "tablet": "12", "mobile": "12"}] - Field has a grid system. This allow to get multiple field in the same row if needed.
 *  @param {Boolean} [hideLabel=false]
 *  @param {String} [containerClass=""]
 *  @param {String} [headerClass=""]
 *  @param {String} [inpClass=""]
 *  @param {String|Number} [tabId=contentIndex] - The tabindex of the field, by default it is the contentIndex
 */

const props = defineProps({
  // id && value && method
  id: {
    type: String,
    required: false,
    default: "",
  },
  columns: {
    type: [Object, Boolean],
    required: false,
    default: false,
  },
  value: {
    type: String,
    required: true,
  },
  popovers: {
    type: Array,
    required: false,
    default: [],
  },
  inpType: {
    type: String,
    required: false,
    default: "checkbox",
  },
  disabled: {
    type: Boolean,
    required: false,
    default: false,
  },
  required: {
    type: Boolean,
    required: false,
    default: false,
  },
  label: {
    type: String,
    required: true,
  },
  attrs: {
    type: Object,
    required: false,
    default: {},
  },
  name: {
    type: String,
    required: true,
  },
  hideLabel: {
    type: Boolean,
    required: false,
    default: false,
  },
  containerClass: {
    type: String,
    required: false,
    default: "",
  },
  headerClass: {
    type: String,
    required: false,
    default: "",
  },
  inpClass: {
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

const checkboxEl = ref(null);

const checkbox = reactive({
  id: "",
  value: props.value,
  isValid: true,
});

const emits = defineEmits(["inp"]);

/**
 *  @name updateValue
 *  @description This will convert the boolean checkbox value to a "yes" or "no" string value.
 *  We will check the validity of the checkbox too.
 *  @returns {string} - The new string value of the checkbox 'yes' or 'no'
 */
function updateValue() {
  checkbox.value = checkbox.value === "yes" ? "no" : "yes";
  checkbox.isValid = checkboxEl.value.checkValidity();
  return checkbox.value;
}

onBeforeMount(() => {
  checkbox.id = useUUID(props.id);
});

onMounted(() => {
  checkbox.isValid = checkboxEl.value.checkValidity();
});
</script>

<template>
  <Container
    :containerClass="`${props.containerClass}`"
    :columns="props.columns"
  >
    <Header
      :popovers="props.popovers"
      :required="props.required"
      :name="props.name"
      :label="props.label"
      :id="checkbox.id"
      :hideLabel="props.hideLabel"
      :headerClass="props.headerClass"
    />

    <div class="checkbox-container">
      <input
        v-bind="props.attrs"
        ref="checkboxEl"
        :tabindex="props.tabId"
        @keyup.enter="$emit('inp', updateValue())"
        @click="$emit('inp', updateValue())"
        :id="checkbox.id"
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
      <ErrorField
        :errorClass="'check'"
        :isValid="checkbox.isValid"
        :isValue="checkbox.isValid"
      />
    </div>
  </Container>
</template>
