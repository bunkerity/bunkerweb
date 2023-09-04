<script setup>
import { reactive, watch, onMounted, defineProps } from "vue";

const props = defineProps({
  active: {
    type: String,
    required: true,
  },
});
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

// Close select dropdown when clicked outside element
watch(tabCtnr, () => {
  if (tabCtnr.isOpen) {
    document.querySelector("body").addEventListener("click", closeOutside);
  } else {
    document.querySelector("body").removeEventListener("click", closeOutside);
  }
});

// Close select when clicked outside logic
function closeOutside(e) {
  try {
    if (!e.target.closest("button").hasAttribute("data-select-tab-container")) {
      tabCtnr.isOpen = false;
    }
  } catch (err) {
    tabCtnr.isOpen = false;
  }
}
</script>

<template>
  <!-- desktop -->
  <div
    role="tablist"
    :class="[tabCtnr.isMobile ? 'mt-4' : '']"
    class="z-100 relative md:block col-span-12 h-full md:h-fit"
  >
    <button
      data-select-tab-container
      v-if="tabCtnr.isMobile"
      @click="toggleDrop()"
      class="select-btn"
    >
      <span class="select">{{ props.active }}</span>
      <!-- chevron -->
      <svg
        :class="[tabCtnr.isOpen ? '-rotate-180' : '']"
        class="select-btn-svg"
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
      v-if="(tabCtnr.isMobile && tabCtnr.isOpen) || !tabCtnr.isMobile"
      :class="[
        tabCtnr.isMobile
          ? 'mt-1 absolute max-h-[300px] w-full overflow-y-auto overflow-x-hidden'
          : 'relative flex flex-wrap',
      ]"
    >
      <slot></slot>
    </div>
  </div>
</template>
