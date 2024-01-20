import { defineStore } from "pinia";
import { ref } from "vue";

export const useModalStore = defineStore("jobsModal", () => {
  const isOpen = ref(false);
  const data = ref({
    name: "",
    history: [],
  });

  function $reset() {
    data.value = {
      name: "",
      history: [],
    };
  }

  return {
    isOpen,
    data,
    $reset,
  };
});
