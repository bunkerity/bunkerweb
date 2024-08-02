<script setup>
import { reactive } from "vue";
import Alert from "@components/Widget/Alert.vue";
import { feedbackIndex } from "@utils/tabindex.js";
import { useBannerStore } from "@store/global.js";
import { onBeforeMount } from "vue";
/**
 *  @name Dashboard/Feedback.vue
 *  @description This component will display server feedbacks from the user.
 * This component is working with flash messages under the hood.
 * This will display an ephemeral on the bottom right of the page and a sidebar with all the feedbacks.
 */

const feedback = reactive({
  data: [],
});

// Handle feedback history panel
const dropdown = reactive({
  isOpen: false,
});

// Use to update position when banner is visible or not
const bannerStore = useBannerStore();

onBeforeMount(() => {
  const dataAtt = "data-server-flash";
  const dataEl = document.querySelector(`[${dataAtt}]`);
  const data =
    dataEl && !dataEl.getAttribute(dataAtt).includes(dataAtt)
      ? JSON.parse(dataEl.getAttribute(dataAtt))
      : [];
  feedback.data = data;
});
</script>

<template>
  <Alert
    v-for="(item, id) in feedback.data"
    :title="feedback.data[id].title"
    :message="feedback.data[id].message"
    :delayToClose="5000"
    :type="feedback.data[id].type"
    :tabId="feedbackIndex"
    :isFixed="true"
  />

  <!-- float button-->
  <div
    :class="[bannerStore.bannerClass]"
    class="feedback-float-btn-container group group-hover"
  >
    <button
      :tabindex="feedbackIndex"
      aria-controls="feedback-sidebar"
      :aria-expanded="dropdown.isOpen ? 'true' : 'false'"
      @click="dropdown.isOpen = dropdown.isOpen ? false : true"
      class="feedback-float-btn"
      :aria-labelledby="`feedback-sidebar-toggle-btn-text`"
    >
      <span class="sr-only" id="feedback-sidebar-toggle-btn-text">
        {{ $t("dashboard_feedback_toggle_sidebar") }}
      </span>
      <svg
        aria-hidden="true"
        role="img"
        class="feedback-float-btn-svg"
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 448 512"
      >
        <path
          d="M224 0c-17.7 0-32 14.3-32 32V51.2C119 66 64 130.6 64 208v18.8c0 47-17.3 92.4-48.5 127.6l-7.4 8.3c-8.4 9.4-10.4 22.9-5.3 34.4S19.4 416 32 416H416c12.6 0 24-7.4 29.2-18.9s3.1-25-5.3-34.4l-7.4-8.3C401.3 319.2 384 273.9 384 226.8V208c0-77.4-55-142-128-156.8V32c0-17.7-14.3-32-32-32zm45.3 493.3c12-12 18.7-28.3 18.7-45.3H224 160c0 17 6.7 33.3 18.7 45.3s28.3 18.7 45.3 18.7s33.3-6.7 45.3-18.7z"
        />
      </svg>
    </button>
    <div class="feedback-float-btn-text-container">
      <p class="feedback-float-btn-text">
        {{ feedback.data.length }}
      </p>
    </div>
  </div>
  <!-- end float button -->

  <!-- right sidebar -->
  <aside
    id="feedback-sidebar"
    :aria-hidden="dropdown.isOpen ? 'false' : 'true'"
    :class="[dropdown.isOpen ? 'active' : 'inactive', 'feedback-sidebar']"
  >
    <!-- close btn-->
    <button
      :tabindex="dropdown.isOpen ? feedbackIndex : '-1'"
      aria-controls="feedback-sidebar"
      :aria-expanded="dropdown.isOpen ? 'true' : 'false'"
      class="feedback-header-close-btn"
      @click="dropdown.isOpen = false"
      :aria-labelledby="`feedback-sidebar-close-btn-text`"
    >
      <span class="sr-only" id="feedback-sidebar-close-btn-text">
        {{ $t("dashboard_feedback_close_sidebar") }}
      </span>
      <svg
        aria-hidden="true"
        role="img"
        @click="dropdown.isOpen = false"
        class="feedback-header-close-btn-svg"
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 320 512"
      >
        <path
          d="M310.6 150.6c12.5-12.5 12.5-32.8 0-45.3s-32.8-12.5-45.3 0L160 210.7 54.6 105.4c-12.5-12.5-32.8-12.5-45.3 0s-12.5 32.8 0 45.3L114.7 256 9.4 361.4c-12.5 12.5-12.5 32.8 0 45.3s32.8 12.5 45.3 0L160 301.3 265.4 406.6c12.5 12.5 32.8 12.5 45.3 0s12.5-32.8 0-45.3L205.3 256 310.6 150.6z"
        />
      </svg>
    </button>
    <!-- close btn-->

    <!-- header -->
    <div class="feedback-header">
      <div class="float-left">
        <h5 class="feedback-header-title">
          {{ $t("dashboard_feedback_title") }}
        </h5>
        <p class="feedback-header-subtitle">
          {{ $t("dashboard_feedback_subtitle") }}
        </p>
      </div>
    </div>
    <!-- end header -->

    <Alert
      v-for="(item, id) in feedback.data"
      :type="item.type"
      :id="item.id"
      :title="item.title"
      :message="item.message"
      :tabId="dropdown.isOpen ? feedbackIndex : '-1'"
    />
  </aside>
  <!-- end right sidebar -->
</template>
