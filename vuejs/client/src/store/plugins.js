import { defineStore } from "pinia";
import { ref } from "vue";

export const useDelModalStore = defineStore("delPluginModal", () => {
  const isOpen = ref(false);
  const data = ref({
    id: "",
    name: "",
    description: "",
  });

  function $reset() {
    data.value = {
      id: "",
      name: "",
      description: "",
    };
  }

  return {
    isOpen,
    data,
    $reset,
  };
});
