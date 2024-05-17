<script setup>

/*
  COMPONENT DESCRIPTION
  *
  *
  This error field component is used to show a feedback message to the user when the field is invalid.
  *
  *
  PROPS ARGUMENTS
  *
  *
  isValid: boolean,
  isValue: boolean,
  *
  *
  PROPS EXAMPLE
  *
  *
  isValid: false,
  isValue: false,
  *
  *
*/

const props = defineProps({
    isValid: {
        type: Boolean,
        required: false,
    },
    isValue : {
        type: Boolean,
        required: false,
    }
})
</script>

<template>
        <p
      :aria-hidden="props.isValid ? 'true' : 'false'"
      role="alert"
      :class="[props.isValid ? 'hidden' : '']"
      class="input-error-msg"
    >
    {{
        props.isValid
          ? $t("inp_input_valid")
          : !props.isValue
            ? $t("inp_input_error_required")
            : $t("inp_input_error")
      }}
    </p>
</template>