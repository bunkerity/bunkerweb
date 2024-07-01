<script setup>
import { defineProps, reactive, onMounted, onBeforeMount } from "vue";

import { useUUID } from "@utils/global.js";
/** 
  @name Forms/Error/Field.vue
  @description This component is an alert type to send feedback to the user.
  We can used it as a fixed alert or we can use it in a container as a list.
  @example
  {
    position : "fixed",
    type: "success",
    title: "Success",
    message: "Your action has been successfully completed",
    delayToClose: 5000,
  }
  @param {string} title - The title of the alert. Can be a translation key or by default raw text.
  @param {string} message - The message of the alert. Can be a translation key or by default raw text.
  @param {boolean} [canClose=true] - Determine if the alert can be closed by user (add a close button), by default it is closable
  @param {string} [id=`feedback-alert-${message.substring(0, 10)}`]
  @param {string} [isFixed=false] - Determine if the alert is fixed (visible bottom right of page) or relative (inside a container)
  @param {string} [type="info"] - The type of the alert, can be success, error, warning or info
  @param {number} [delayToClose=0] - The delay to auto close alert in ms, by default always visible
  @param {string} [tabId="-1"] - The tabindex of the alert
*/

const props = defineProps({
  isFixed: {
    type: Boolean,
    required: false,
    default: false,
  },
  type: {
    type: String,
    required: false,
    default: "info",
  },
  title: {
    type: [Number, String],
    required: true,
  },
  message: {
    type: String,
    required: true,
  },
  delayToClose: {
    type: Number,
    required: false,
    default: 0,
  },
  canClose: {
    type: Boolean,
    required: false,
    default: true,
  },
  tabId: {
    type: [String, Number],
    required: false,
    default: "-1",
  },
});

const alert = reactive({
  visible: true,
  id: "",
});

onBeforeMount(() => {
  alert.id = useUUID();
});

onMounted(() => {
  if (props.delayToClose > 0) {
    setTimeout(() => {
      alert.visible = false;
    }, props.delayToClose);
  }
});
</script>

<template>
  <div
    v-if="alert.visible"
    :class="['feedback-alert-container', props.isFixed ? 'is-fixed' : '']"
    :id="alert.id"
    :role="props.type === 'success' ? 'status' : 'alert'"
    :aria-description="$t('dashboard_feedback_alert_desc')"
  >
    <div :class="[props.type, 'feedback-alert-wrap bg-el']">
      <div class="feedback-alert-header">
        <h5 class="feedback-alert-title">
          {{ $t(props.title, $t("dashboard_placeholder", props.title)) }}
        </h5>
        <button
          :tabindex="props.tabId"
          @click="alert.visible = false"
          data-close-flash-message
          type="button"
          class="feedback-alert-btn"
          :aria-labelledby="`${alert.id}-close`"
        >
          <span class="sr-only" :id="`${alert.id}-close`">
            {{ $t("dashboard_feedback_alert_close") }}
          </span>
          <svg
            aria-hidden="true"
            role="img"
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
      <p class="feedback-alert-text">
        {{ $t(props.message, $t("dashboard_placeholder", props.message)) }}
      </p>
    </div>
  </div>
</template>
