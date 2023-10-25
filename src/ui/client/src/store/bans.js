import { defineStore } from "pinia";
import { ref } from "vue";

export const useSelectBanStore = defineStore("selectBan", () => {
  const data = ref([]);

  function addBanItem(ip) {
    // Look if item already exists
    data.value.forEach((ipValue) => {
      if (ipValue === ip) return;
    });

    data.value.push(ip);
  }

  function deleteBanItem(ip) {
    data.value = data.value.filter((ipValue) => ip !== ipValue);
  }

  function $reset() {
    data.value = [];
  }

  return { data, $reset, addBanItem, deleteBanItem };
});
