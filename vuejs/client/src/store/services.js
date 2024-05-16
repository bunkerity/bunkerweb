import { defineStore } from "pinia";
import { ref } from "vue";

export const useModalStore = defineStore("ServiceModal", () => {
  const isOpen = ref(false);
  const data = ref({
    services: [],
    service: "",
    serviceName: "",
    operation: "",
    servicesNames: [],
    method: "",
    isDraft: false,
  });

  function $reset() {
    data.value = {
      services: [],
      service: "",
      serviceName: "",
      operation: "",
      servicesNames: [],
      method: "",
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
    method: "",
  });

  function $reset() {
    data.value = {
      service: "",
      method: "",
    };
  }

  return {
    isOpen,
    data,
    $reset,
  };
});

export const useFilterStore = defineStore("serviceCardFilter", () => {
  const isOpen = ref(false);

  return {
    isOpen,
  };
});
