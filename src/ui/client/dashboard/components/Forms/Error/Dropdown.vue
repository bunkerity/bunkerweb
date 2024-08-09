<script setup>
/**
 *  @name Forms/Error/Dropdown.vue
 *  @description This component is used to display a feedback message on a dropdown field.
 * It is used with /Forms/Field components.
 *  @example
 *  {
 *    isValid: false,
 *    isValue: false,
 *  }
 *  @param {boolean} [isValid=false] - Check if the field is valid
 *  @param {boolean} [isValue=false] - Check if the field has a value, display a different message if the field is empty or not
 *  @param {boolean} [isValueTaken=false] - Check if input is already taken. Use with list input.
 *  @param {string} [errorClass=""] - Additional class
 */

const props = defineProps({
  isValid: {
    type: Boolean,
    required: false,
  },
  isValue: {
    type: Boolean,
    required: false,
  },
  isValueTaken: {
    type: Boolean,
    required: false,
    default: false,
  },
  errorClass: {
    type: String,
    required: false,
    default: "",
  },
});
</script>

<template>
  <div
    :aria-hidden="props.isValid ? 'true' : 'false'"
    :class="[
      props.isValid ? 'hidden' : '',
      'select-dropdown-btn last first',
      props.errorClass,
    ]"
    role="alert"
  >
    <p class="input-error-dropdown-msg">
      {{
        props.isValid
          ? $t("inp_input_valid")
          : props.isNoMatch
            ? $t("inp_input_no_match")
            : props.isValueTaken
              ? $t("inp_input_error_taken")
              : !props.isValue
                ? $t("inp_input_error_required")
                : $t("inp_input_error")
      }}
    </p>
  </div>
</template>
