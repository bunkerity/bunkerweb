import { defineStore } from "pinia";
import { ref } from "vue";

export const useFeedbackStore = defineStore("feedback", () => {
  const data = ref([]);
  let feedID = 0;

  async function addFeedback(type, status, message) {
    feedID++;
    data.value.push({
      id: feedID,
      isNew: true,
      type: type,
      status: status,
      message: message,
    });
  }

  function removeFeedback(id) {
    data.value.splice(
      data.value.findIndex((item) => item["id"] === id),
      1,
    );
  }

  return { data, addFeedback, removeFeedback };
});

export const useRefreshStore = defineStore("refresh", () => {
  const count = ref(0);

  async function refresh() {
    count.value++;
  }

  return { count, refresh };
});

export const useBannerStore = defineStore("banner", () => {
  const isBanner = ref(true);
  const bannerClass = ref("banner");

  async function setBannerVisible(bool) {
    isBanner.value = bool;
    bannerClass.value = bool ? "banner" : "no-banner";
  }

  return { isBanner, bannerClass, setBannerVisible };
});

export const useBackdropStore = defineStore("backdrop", () => {
  const clickCount = ref(0);

  return { clickCount };
});
