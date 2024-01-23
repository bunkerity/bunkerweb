import { defineStore } from "pinia";
import { ref } from "vue";

export const useModalStore = defineStore("ServiceModal", () => {
  const isOpen = ref(false);
  const data = ref({
    services: [],
    service: "",
    serviceName: "",
    operation: "",
  });

  function $reset() {
    data.value = {
      services: [],
      service: "",
      serviceName: "",
      operation: "",
    };
  }

  return {
    isOpen,
    data,
    $reset,
  };
});

export const useDelModalStore = defineStore("ServiceDelModal", () => {
  const isOpen = ref(false);
  const data = ref({
    service: "",
    serviceName: "",
    operation: "",
  });

  function $reset() {
    data.value = {
      service: "",
      serviceName: "",
      operation: "",
    };
  }

  return {
    isOpen,
    data,
    $reset,
  };
});
