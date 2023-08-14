<script setup>
const props = defineProps({
  // Current clicked tab on a group
  activeTabName: {
    type: String,
    required: true,
  },
  // Name to identify tab and compare with other tabs
  tabName: {
    type: String,
    required: true,
  },
  // For popover
  desc: {
    type: String,
    required: true,
  },
  // Additionnal styles
  first: {
    type: Boolean,
    required: false,
  },
  last: {
    type: Boolean,
    required: false,
  },
});

// Different style for desktop and mobile
const tab = reactive({
  isMobile: false,
});

onMounted(() => {
  // When component is created but before is insert on DOM
  // Check window width to determine we need to display mobile or desktop tab design
  tab.isMobile = window.innerWidth >= 768 ? false : true;
  window.addEventListener("resize", () => {
    tab.isMobile = window.innerWidth >= 768 ? false : true;
  });
});
</script>

<template>
  <div
    role="tab"
    :class="[
      tab.isMobile ? 'settings-tabs-mobile-btn' : 'settings-tabs-tab-btn',
      props.activeTabName === props.tabName ? 'active' : '',
      props.first ? 'first' : '',
      props.last ? 'last' : '',
    ]"
    :aria-current="props.activeTabName === props.tabName ? 'true' : 'false'"
  >
    <span class="w-full flex justify-between items-center">
      <span
        :class="[
          tab.isMobile ? 'settings-tabs-mobile-name' : 'settings-tabs-name',
        ]"
        >{{ props.tabName }}</span
      >
      <!-- popover -->
      <div class="relative">
        <Popover tag="div"> {{ props.desc }}</Popover>
      </div>
      <!-- end popover -->
    </span>
  </div>
</template>
