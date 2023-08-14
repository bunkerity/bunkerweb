<script setup>
const props = defineProps({
  setting: {
    type: Object,
    required: true,
  },
});

const input = reactive({
  id: props.setting.id,
  type: props.setting.type,
  value: props.setting.value,
  placeholder: props.setting.placeholder || "",
  required: props.setting.required || false,
  disabled: props.setting.disabled || false,
  pattern: props.setting.pattern || "",
});
</script>

<template>
  <div class="relative flex items-center">
    <input
      :type="
        input.isPassword
          ? input.showInp
            ? input.type
            : 'password'
          : input.type
      "
      :id="input.id"
      class="input-regular"
      :required="input.id === 'SERVER_NAME' || input.required ? true : false"
      :disabled="input.disabled"
      :placeholder="input.placeholder"
      :pattern="input.pattern"
      :name="input.id"
      :value="input.value"
    />
  </div>
</template>
