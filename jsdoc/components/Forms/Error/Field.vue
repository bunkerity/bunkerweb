<script setup>

/** 
  @name Forms/Error/Field.vue
  @description This component is used to display a feedback message to user when a field is invalid.
  It is used with /Forms/Field components.
  @example
  {
    isValid: false,
    isValue: false,
  }
  @param {boolean} [isValid=false] - Check if the field is valid
  @param {boolean} [isValue=false] - Check if the field has a value, display a different message if the field is empty or not
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