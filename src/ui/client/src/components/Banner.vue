<script setup>
import { onMounted, watch } from "vue";
import { useBannerStore } from "@store/global.js";

const bannerStore = useBannerStore();

const banner = reactive({
  nextDelay: 9000,
  transDuration: 700,
  visibleId: "1",
});

watch(bannerStore.visibleId, (newVal, oldVal) => {
  banner.visibleId = newVal;

  // Hide previous one
  const oldItem = document.getElementById(`banner-item-${oldVal}`);
  oldItem.classList.add("-left-full");
  oldItem.classList.remove("left-0");
  setTimeout(() => {
    oldItem.classList.remove("transition-all");
  }, banner.transDuration + 10);
  setTimeout(() => {
    oldItem.classList.add("opacity-0");
  }, banner.transDuration + 20);
  setTimeout(() => {
    oldItem.classList.remove("-left-full");
    oldItem.classList.add("left-full");
  }, banner.transDuration * 2);

  // Show new one
  const newItem = document.getElementById(`banner-item-${newVal}`);
  newItem.classList.remove("opacity-0");
  newItem.classList.add("transition-all");
  newItem.classList.add("left-0");
  newItem.classList.remove("left-full");
});

function setupBanner() {
  // Switch item every interval and
  setInterval(() => {
    banner.isVisible =
      banner.isVisibleId === "3" ? "1" : `${banner.isVisibleId + 1}`;
  }, banner.nextDelay);

  // Observe banner and set is visible or not to
  // Update float button and menu position
  let options = {
    root: null,
    rootMargin: "0px",
    threshold: 0.35,
  };

  let observer = new IntersectionObserver((entries, observer) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) bannerStore.setBannerVisible(true);
      if (!entry.isIntersecting) bannerStore.setBannerVisible(false);
    });
  }, options);

  observer.observe(ocument.getElementById("banner"));
}

onMounted(() => {
  setupBanner();
});
</script>

<template>
  <div id="banner" tabindex="-1" role="list" class="banner-container">
    <div class="banner-bg"></div>

    <div
      v-for="index in 3"
      role="listitem"
      :aria-hidden="banner.visibleId === index ? 'false' : 'true'"
      :id="`banner-item-${index}`"
      class="banner-item"
    >
      <p class="banner-item-text">
        {{ $t(`dashboard_banner_title_${index}`) }}
        <a
          class="banner-item-link"
          href="https://panel.bunkerweb.io/?utm_campaign=self&utm_source=ui"
        >
          {{ $t(`dashboard_banner_link_text_${index}`) }}
        </a>
      </p>
    </div>
  </div>
</template>
