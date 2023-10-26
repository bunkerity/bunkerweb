import { defineStore } from "pinia";
import { ref } from "vue";

export const useConfigStore = defineStore("config", () => {
  const data = ref({ global: {}, services: {} });

  function updateConf(name, id, value, currValue, regex = ".*") {
    if (!name || !id) return; // Need this to proceed

    const formatID = id.toUpperCase().replaceAll("-", "_");

    // Invalid setting if current one or didn't match  regex
    const validInp = new RegExp(regex);

    if (value === currValue || validInp.test(value) === false) {
      if (name === "global" && !!(formatID in data.value[name]))
        delete data.value[name][formatID];
      if (name !== "global" && !!(formatID in data.value["services"][name]))
        delete data.value["services"][name][formatID];

      return;
    }

    if (name === "global") data.value[name][formatID] = value;
    if (name !== "global") {
      if (!(name in data.value["services"])) data.value["services"][name] = {};
      data.value["services"][name][formatID] = value;
    }
  }

  function $reset() {
    data.value = {
      global: {},
      services: {},
    };
  }

  return { data, $reset, updateConf };
});

export const useModesStore = defineStore("modes", () => {
  const data = ref(["AUTOCONF_MODE", "SWARM_MODE", "KUBERNETES_MODE"]);

  return { data, updateConf };
});
