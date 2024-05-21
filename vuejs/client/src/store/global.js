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

/**
  @name useBackdropStore
  @description Store to share the current backdrop state (visible or not).
  This backdrop avoid to click on the main content when we want to show a modal or a dialog.
*/
export const useBackdropStore = defineStore("backdrop", () => {
  const clickCount = ref(0);

  return { clickCount };
});
