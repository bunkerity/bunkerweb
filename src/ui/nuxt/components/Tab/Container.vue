<script setup>
// Container with dropdown btn for mobile
// And style to handle tabs

const tabCtnr = reactive({
  isMobile: false,
  isOpen: false,
});

onMounted(() => {
  // On window context, check window.width to determine
  // If we need to display mobile or desktop style
  tabCtnr.isMobile = window.innerWidth >= 768 ? false : true;
  window.addEventListener("resize", () => {
    tabCtnr.isMobile = window.innerWidth >= 768 ? false : true;
  });
});

// For mobile with a dropdown btn
function toggleDrop() {
  tabCtnr.isOpen = tabCtnr.isOpen ? false : true;
}
</script>

<template>
  <!-- desktop -->
  <div role="tablist" class="relative md:block col-span-12 h-full md:h-fit">
    <button
      v-if="tabCtnr.isMobile"
      @click="toggleDrop()"
      class="settings-tabs-mobile-dropdown-btn"
    >
      <span class="settings-tabs-mobile-btn-text">tab dropdown</span>
      <!-- chevron -->
      <svg
        class="transition-transform h-4 w-4 fill-primary dark:fill-gray-300"
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 512 512"
      >
        <path
          d="M233.4 406.6c12.5 12.5 32.8 12.5 45.3 0l192-192c12.5-12.5 12.5-32.8 0-45.3s-32.8-12.5-45.3 0L256 338.7 86.6 169.4c-12.5-12.5-32.8-12.5-45.3 0s-12.5 32.8 0 45.3l192 192z"
        />
      </svg>
      <!-- end chevron -->
    </button>
    <div
      v-if="(tabCtnr.isMobile && !tabCtnr.isOpen) || !tabCtnr.isMobile"
      :class="[tabCtnr.isMobile ? 'absolute' : 'relative flex']"
    >
      <slot></slot>
    </div>
  </div>
</template>
