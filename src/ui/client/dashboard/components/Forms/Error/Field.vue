<script setup>
/**
 *  @name Forms/Error/Field.vue
 *  @description This component is used to display a feedback message to user when a field is invalid.
 *  It is used with /Forms/Field components.
 *  @example
 *  {
 *    isValid: false,
 *    isValue: false,
 *  }
 *  @param {Boolean} [isValid=false] - Check if the field is valid
 *  @param {Boolean} [isValue=false] - Check if the field has a value, display a different message if the field is empty or not
 *  @param {Boolean} [isValueTaken=false] - Check if input is already taken. Use with list input.
 *  @param {String} [errorClass=""] - Additional class
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
  <p
    :aria-hidden="props.isValid ? 'true' : 'false'"
    role="alert"
    :class="[props.isValid ? 'valid' : '', 'input-error-msg', props.errorClass]"
  >
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
</template>
