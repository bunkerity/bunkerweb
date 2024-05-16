import { defineStore } from "pinia";
import { ref } from "vue";

export const useDelModalStore = defineStore("delInstanceModal", () => {
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

export const useAddModalStore = defineStore("addInstanceModal", () => {
  const isOpen = ref(false);

  return {
    isOpen,
  };
});

export const useEditModalStore = defineStore("editInstanceModal", () => {
  const isOpen = ref(false);
  const data = ref({
    hostname: "",
    old_hostname: "",
    server_name: "",
    port: "",
  });

  function $reset() {
    data.value = {
      hostname: "",
      old_hostname: "",
      server_name: "",
      port: "",
    };
  }

  return {
    isOpen,
    data,
    $reset,
  };
});
