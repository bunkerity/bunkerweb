import { defineStore } from "pinia";
import { ref } from "vue";

export const useModalStore = defineStore("fileManagerModal", () => {
  const isOpen = ref(false);
  const data = ref({
    type: "folder",
    action: "view",
    path: "root/",
    pathLevel: 1,
    value: "",
    name: "root",
  });

  function $reset() {
    data.value = {
      type: "folder",
      action: "view",
      path: "root/",
      pathLevel: 1,
      value: "",
      name: "root",
    };
  }

  return {
    isOpen,
    data,
    $reset,
  };
});
