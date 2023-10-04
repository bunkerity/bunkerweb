<script setup>
const props = defineProps({
  settings: {
    type: Object,
    required: true,
  },
});

const input = reactive({
  id: props.settings.id,
  type: props.settings.type,
  value: props.settings.value,
  placeholder: props.settings.placeholder || "",
  required: props.settings.required || false,
  disabled: props.settings.disabled || false,
  pattern: props.settings.pattern || "",
});

const emits = defineEmits(["inp"]);

const inp = "";
</script>

<template>
  <div class="relative flex items-center">
    <input
      v-model="inp"
      @input="$emit('inp', inp)"
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
