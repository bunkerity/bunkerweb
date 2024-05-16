import { defineStore } from "pinia";
import { ref } from "vue";

export const useConfigStore = defineStore("config", () => {
  const data = ref({ global: {}, services: {} });

  function updateConf(name, id, value, regex = ".*") {
    // Remove prev value
    removeConf(name, id);

    // Try to update with another value
    const formatID = id.toUpperCase().replaceAll("-", "_");

    // Case value is invalid to be added
    const validInp = new RegExp(regex);
    if (validInp.test(value) === false) return;

    // Else add value
    if (name === "global") data.value[name][formatID] = value;
    if (name !== "global") {
      if (!(name in data.value["services"])) data.value["services"][name] = {};
      data.value["services"][name][formatID] = value;
    }
  }

  // Case value is default or previous (and already in core config value)
  // Or before updating a value
  function removeConf(name, id) {
    if (!name || !id) return; // Need this to proceed

    const formatID = id.toUpperCase().replaceAll("-", "_");

    //  Remove global value
    try {
      if (name === "global" && !!(formatID in data.value[name]))
        delete data.value[name][formatID];
    } catch (err) {}

    // Remove service value
    try {
      if (name !== "global" && !!(formatID in data.value["services"][name]))
        delete data.value["services"][name][formatID];
    } catch (err) {}
  }

  function $reset() {
    data.value = {
      global: {},
      services: {},
    };
  }

  return { data, $reset, updateConf, removeConf };
});

export const useModesStore = defineStore("modes", () => {
  const data = ref(["AUTOCONF_MODE", "SWARM_MODE", "KUBERNETES_MODE"]);

  return { data, updateConf };
});
