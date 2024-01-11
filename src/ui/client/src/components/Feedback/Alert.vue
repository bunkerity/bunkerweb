<script setup>
import { defineProps, defineEmits } from "vue";

const props = defineProps({
  id: {
    type: [Number, String],
    required: true,
  },
  type: {
    type: String,
    required: true,
  },
  status: {
    type: [Number, String],
    required: true,
  },
  message: {
    type: String,
    required: true,
  },
});

const emits = defineEmits(["close"]);
</script>

<template>
  <div
    role="alert"
    :aria-description="$t('dashboard_feedback_alert_desc')"
    :class="[
      props.type !== 'success' && props.type !== 'error'
        ? 'default'
        : props.type,
    ]"
    class="feedback-alert-container"
  >
    <div class="feedback-alert-header">
      <h5 class="feedback-alert-title">
        {{ `${props.status} ${props.type}` }}
      </h5>
      <button
        @click="$emit('close', props.id)"
        data-close-flash-message
        type="button"
        class="feedback-alert-btn"
      >
        <svg
          class="feedback-alert-svg"
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 320 512"
        >
          <path
            d="M310.6 150.6c12.5-12.5 12.5-32.8 0-45.3s-32.8-12.5-45.3 0L160 210.7 54.6 105.4c-12.5-12.5-32.8-12.5-45.3 0s-12.5 32.8 0 45.3L114.7 256 9.4 361.4c-12.5 12.5-12.5 32.8 0 45.3s32.8 12.5 45.3 0L160 301.3 265.4 406.6c12.5 12.5 32.8 12.5 45.3 0s12.5-32.8 0-45.3L205.3 256 310.6 150.6z"
          ></path>
        </svg>
      </button>
    </div>
    <p class="feedback-alert-text">{{ props.message }}</p>
  </div>
</template>
