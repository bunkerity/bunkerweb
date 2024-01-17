<script setup>
import { onMounted, reactive } from "vue";
import { useBannerStore } from "@store/global.js";
import { bannerIndex } from "@utils/tabindex.js";
const bannerStore = useBannerStore();

const banner = reactive({
  visibleId: 1,
});

function setupBanner() {
  const nextDelay = 14000;
  const transDuration = 10000;
  // Switch item every interval and
  setInterval(() => {
    const prev = banner.visibleId;
    banner.visibleId = banner.visibleId === 3 ? 1 : banner.visibleId + 1;
    const next = banner.visibleId;

    // Hide previous one
    const oldItem = document.getElementById(`banner-item-${prev}`);
    oldItem.classList.add("-left-full");
    oldItem.classList.remove("left-0");
    setTimeout(() => {
      oldItem.classList.remove("transition-all");
    }, transDuration + 10);
    setTimeout(() => {
      oldItem.classList.add("opacity-0");
    }, transDuration + 30);
    setTimeout(() => {
      oldItem.classList.remove("-left-full");
      oldItem.classList.add("left-full");
    }, transDuration * 2);

    // Show new one
    const newItem = document.getElementById(`banner-item-${next}`);
    newItem.classList.remove("opacity-0");
    newItem.classList.add("transition-all");
    newItem.classList.add("left-0");
    newItem.classList.remove("left-full");
  }, nextDelay);

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

  observer.observe(document.getElementById("banner"));
}

onMounted(() => {
  setupBanner();
});
</script>

<template>
  <div id="banner" tabindex="-1" role="list" class="banner-container">
    <div role="img" aria-hidden="true" class="banner-bg"></div>
    <div
      v-for="index in 3"
      role="listitem"
      :id="`banner-item-${index}`"
      class="banner-item"
      :class="[index === 1 ? 'left-0' : 'left-full opacity-0']"
    >
      <p class="banner-item-text">
        {{ $t(`dashboard_banner_title_${index}`) }}
        <a
          :tabindex="bannerIndex"
          class="banner-item-link"
          :href="$t(`dashboard_banner_link_${index}`)"
        >
          {{ $t(`dashboard_banner_link_text_${index}`) }}
        </a>
      </p>
    </div>
  </div>
</template>
