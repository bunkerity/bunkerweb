import { defineStore } from "pinia";
import { ref } from "vue";

/**
  @name useEventStore
  @description Store to share the current banner state (visible or not).
  This is useful to update components, specially fixed ones, related to the banner visibility.
*/
export const useBannerStore = defineStore("banner", () => {
  const isBanner = ref(true);
  const bannerClass = ref("banner");

  async function setBannerVisible(bool) {
    isBanner.value = bool;
    bannerClass.value = bool ? "banner" : "no-banner";
  }

  return { isBanner, bannerClass, setBannerVisible };
});
