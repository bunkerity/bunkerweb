<script setup>
import { onMounted, reactive } from "vue";
import TablistBase from "@components/Tablist/Base.vue";

// DATA
const logs = reactive({
  isActive: false,
  current: "ui",
  ui: [],
  core: [],
});
</script>

<template>
  <!-- float button-->
  <button
    :aria-checked="logs.isActive ? 'true' : 'false'"
    type="button"
    @click="logs.isActive = logs.isActive ? false : true"
    class="logs-float-btn"
  >
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="currentColor"
      class="fill-blue-500 h-6 w-6 scale-[1.2]"
    >
      <path
        fill-rule="evenodd"
        d="M5.625 1.5c-1.036 0-1.875.84-1.875 1.875v17.25c0 1.035.84 1.875 1.875 1.875h12.75c1.035 0 1.875-.84 1.875-1.875V12.75A3.75 3.75 0 0016.5 9h-1.875a1.875 1.875 0 01-1.875-1.875V5.25A3.75 3.75 0 009 1.5H5.625zM7.5 15a.75.75 0 01.75-.75h7.5a.75.75 0 010 1.5h-7.5A.75.75 0 017.5 15zm.75 2.25a.75.75 0 000 1.5H12a.75.75 0 000-1.5H8.25z"
        clip-rule="evenodd"
      />
      <path
        d="M12.971 1.816A5.23 5.23 0 0114.25 5.25v1.875c0 .207.168.375.375.375H16.5a5.23 5.23 0 013.434 1.279 9.768 9.768 0 00-6.963-6.963z"
      />
    </svg>
  </button>
  <!-- end float button-->

  <!-- right sidebar -->
  <aside
    :aria-expanded="logs.isActive ? 'true' : 'false'"
    :aria-hidden="logs.isActive ? 'false' : 'true'"
    :class="[logs.isActive ? '' : 'translate-x-[22.5rem]', 'news-sidebar']"
  >
    <!-- close btn-->
    <svg
      type="button"
      @click="logs.isActive = false"
      class="news-close-btn"
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 320 512"
    >
      <path
        d="M310.6 150.6c12.5-12.5 12.5-32.8 0-45.3s-32.8-12.5-45.3 0L160 210.7 54.6 105.4c-12.5-12.5-32.8-12.5-45.3 0s-12.5 32.8 0 45.3L114.7 256 9.4 361.4c-12.5 12.5-12.5 32.8 0 45.3s32.8 12.5 45.3 0L160 301.3 265.4 406.6c12.5 12.5 32.8 12.5 45.3 0s12.5-32.8 0-45.3L205.3 256 310.6 150.6z"
      />
    </svg>
    <!-- close btn-->

    <!-- header -->
    <div class="news-sidebar-header">
      <div class="float-left w-full">
        <h5 class="news-sidebar-title mb-4">LOGS</h5>
        <TablistBase
          @tab="(v) => (logs.current = v)"
          :current="logs.current"
          :items="[
            { text: 'UI', tag: 'ui' },
            { text: 'core', tag: 'core' },
          ]"
        />
      </div>
      <div v-if="logs.current === 'ui'"></div>
      <div v-if="logs.current === 'core'"></div>
    </div>
    <!-- end header -->
  </aside>
  <!-- end right sidebar -->
</template>
