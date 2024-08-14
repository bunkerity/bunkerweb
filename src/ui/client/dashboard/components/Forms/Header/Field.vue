<script setup>
import { defineProps, onMounted, ref } from "vue";
import PopoverGroup from "@components/Widget/PopoverGroup.vue";

/**
 *  @name Forms/Header/Field.vue
 *  @description This component is used with field in order to link a label to field type.
 *  We can add popover to display more information.
 *  Always use with field component.
 *  @example
 *  {
 *    label: 'Test',
 *    version : "0.1.0",
 *    name: 'test-input',
 *    required: true,
 *    popovers : [
 *      {
 *        text: "This is a popover text",
 *        iconName: "info",
 *      },
 *    ],
 *  }
 *  @param {String} label - The label of the field. Can be a translation key or by default raw text.
 *  @param {String} id - The id of the field. This is used to link the label to the field.
 *  @param {String} name - The name of the field. Case no label, this is the fallback. Can be a translation key or by default raw text.
 *  @param {Array} [popovers=[]] - List of popovers to display more information
 *  @param {Boolean} [required=false]
 *  @param {Boolean} [hideLabel=false]
 *  @param {String} [headerClass=""]
 *  @param {String} [fieldSize="normal"] - Size between "normal" or "sm" inherit from field
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
  fieldSize: {
    type: String,
    required: false,
    default: "normal",
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
      props.fieldSize,
    ]"
    data-is="header-field"
  >
    <div>
      <label
        ref="labelEl"
        :class="[
          'input-header-label',
          props.label ? '' : 'sr-only',
          props.fieldSize,
        ]"
        :for="props.id"
      >
        {{
          props.label
            ? $t(props.label, $t("dashboard_placeholder", props.label))
            : $t(props.name, $t("dashboard_placeholder", props.name))
        }}
      </label>
      <span v-if="props.required" class="input-header-required-sign">*</span>
    </div>
    <div v-if="props.popovers.length">
      <PopoverGroup :popovers="props.popovers"></PopoverGroup>
    </div>
  </div>
</template>
