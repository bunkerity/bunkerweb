import { defineStore } from "pinia";
import { ref } from "vue";

export const useModalStore = defineStore("instanceModal", () => {
  const isOpen = ref(false);
  const data = ref({
    hostname: "",
  });

  function $reset() {
    data.value = {
      hostname: "",
    };
  }

  return {
    isOpen,
    data,
    $reset,
  };
});
