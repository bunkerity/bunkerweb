import { defineStore } from "pinia";
interface config {
  [key: string]: any;
}

export const useConfigStore = defineStore("config", () => {
  const data: config = ref({ global: {}, services: {} });

  function updateConf(
    context: string,
    id: string,
    method: string,
    value: string
  ) {
    if (!context || !id) return;
    data.value[context][id] = {
      method: method,
      value: value,
    };
  }

  return { data, updateConf };
});

export const usePluginStore = defineStore("plugin", () => {
  const data = ref({});

  return { data };
});
