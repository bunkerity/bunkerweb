<script setup>
import { onMounted, reactive, computed } from "vue";
import { useRefreshStore } from "@store/global.js";

const refreshStore = useRefreshStore();

const refresh = reactive({
  isOn: false,
});

function refreshBtn() {
  if (refresh.isOn) return;
  // Set on for animation and update a count that
  // need to be watch to refresh data on pages
  refresh.isOn = true;
  refreshStore.refresh();
  setTimeout(() => {
    refresh.isOn = false;
  }, 2000);
}
</script>

<template>
  <!-- float button-->
  <button @click="refreshBtn()" class="refresh-float-btn">
    <span class="sr-only">{{ $t("dashboard.header.buttons.refresh") }}</span>
    <svg
      :class="[refresh.isOn ? 'btn-spin' : '']"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      stroke-width="1.5"
      stroke="currentColor"
      class="stroke-sky-500 h-7 w-7 pointer-events-none"
    >
      <path
        stroke-linecap="round"
        stroke-linejoin="round"
        d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99"
      />
    </svg>
  </button>
  <!-- end float button-->
</template>

<style>
.btn-spin {
  animation: 2s spin linear infinite;
}

@keyframes spin {
  0% {
    transform: rotate(0deg);
  }

  100% {
    transform: rotate(360deg);
  }
}
</style>
