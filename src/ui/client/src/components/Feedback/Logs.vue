<script setup>
import { defineProps } from "vue";

const props = defineProps({
  id: {
    type: [Number, String],
    required: true,
  },
  status: {
    type: String,
    required: true,
  },
  title: {
    type: String,
    required: true,
  },
  method: {
    type: [Number, String],
    required: true,
  },
  apiMethod: {
    type: [Number, String],
    required: true,
  },
  description: {
    type: String,
    required: true,
  },
  date: {
    type: [Number, String, Date],
    required: true,
  },
});
</script>

<template>
  <div
    role="alert"
    :aria-description="$t('dashboard_feedback_logs_desc')"
    :class="[
      props.status !== 'success' && props.status !== 'error'
        ? 'default'
        : props.status,
    ]"
    class="feedback-log-container"
  >
    <div class="feedback-log-header">
      <h5 class="feedback-log-title">
        {{ `${props.title}` }}
      </h5>
    </div>
    <p class="feedback-log-desc">{{ props.description }}</p>
    <p class="feedback-log-meta">
      {{ props.method === `unknown` ? `` : `${props.method.toUpperCase()} |` }}
      {{ props.apiMethod }}
    </p>
    <p class="feedback-log-date">{{ props.date }}</p>
  </div>
</template>
