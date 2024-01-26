import { defineStore } from "pinia";
import { ref } from "vue";

export const useSelectIPStore = defineStore("selectIP", () => {
  const data = ref(new Set());

  function addIP(ip) {
    data.value.add(ip);
  }

  function deleteIP(ip) {
    data.value.delete(ip);
  }

  function $reset() {
    data.value.clear();
  }

  return { data, $reset, addIP, deleteIP };
});

export const useAddModalStore = defineStore("addBanModal", () => {
  const isOpen = ref(false);

  return {
    isOpen,
  };
});
