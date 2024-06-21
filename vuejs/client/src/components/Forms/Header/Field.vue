<script setup>
import { defineProps, onMounted, ref } from "vue";
import PopoverGroup from "@components/Widget/PopoverGroup.vue";

/** 
  @name Forms/Header/Field.vue
  @description This component is used with field in order to link a label to field type.
  We can add popover to display more information.
  Always use with field component.
  @example
  {
    label: 'Test',
    version : "0.1.0",
    name: 'test-input',
    required: true,
    popovers : [
      {
        text: "This is a popover text",
        iconName: "info",
        iconColor: "info",
      },
    ],
  }
  @param {string} label - The label of the field. Can be a translation key or by default raw text.
  @param {string} id - The id of the field. This is used to link the label to the field.
  @param {string} name - The name of the field. Case no label, this is the fallback. Can be a translation key or by default raw text.
  @param {array} [popovers] - List of popovers to display more information
  @param {boolean} [required=false]
  @param {boolean} [hideLabel=false]
  @param {string} [headerClass=""]
*/

const props = defineProps({
  label: {
    type: String,
    required: true,
  },
  id: {
    type: String,
    required: true,
  },
  name: {
    type: String,
    required: true,
  },
  required: {
    type: Boolean,
    required: false,
    default: false,
  },
  popovers: {
    type: Array,
    required: false,
    default: [],
  },
  hideLabel: {
    type: Boolean,
    required: false,
  },
  headerClass: {
    type: String,
    required: false,
  },
});

const labelEl = ref(null);

onMounted(() => {
  // Check if label is child of a form
  if (!labelEl.value.closest("form")) labelEl.value.removeAttribute("for");
});
</script>

<template>
  <div
    :class="[
      'relative',
      props.hideLabel ? 'hidden' : '',
      props.headerClass,
      'input-header-container',
      props.popovers.length ? 'popover' : 'no-popover',
    ]"
    data-is="header-field"
  >
    <div>
      <label
        ref="labelEl"
        :class="[props.label ? '' : 'sr-only']"
        :for="props.id"
        class="input-header-label"
      >
        {{
          props.label
            ? $t(props.label, props.label)
            : $t(props.name, props.name)
        }}
      </label>
      <span v-if="props.required" class="input-header-required-sign">*</span>
    </div>
    <div v-if="props.popovers.length">
      <PopoverGroup :popovers="props.popovers"></PopoverGroup>
    </div>
  </div>
</template>
