<script setup>
import ServicesButtonClone from "@components/Services/Button/Clone.vue";
import ServicesButtonEdit from "@components/Services/Button/Edit.vue";
import ServicesButtonRedirect from "@components/Services/Button/Redirect.vue";
import ServicesButtonDelete from "@components/Services/Button/Delete.vue";
import ServicesSvgState from "@components/Services/Svg/State.vue";
import { useModalStore, useDelModalStore } from "@store/services.js";
import { defineProps, reactive, computed, onMounted } from "vue";

const modalStore = useModalStore();
const delModalStore = useDelModalStore();

const props = defineProps({
  services: {
    type: Object,
    required: true,
    default: {},
  },
});

const details = [
  {
    lang: "bad_behavior",
    id: "badbehavior",
    setting: "USE_BAD_BEHAVIOR",
  },
  {
    lang: "modsecurity",
    id: "modsecurity",
    setting: "USE_MODSECURITY",
  },
  {
    lang: "limit",
    id: "limit",
    setting: "USE_LIMIT_REQ",
  },
  {
    lang: "reverse_proxy",
    id: "reverseproxy",
    setting: "USE_REVERSE_PROXY",
  },
];

const services = reactive({
  details: computed(() => {
    if (!props.services) return [];

    // create object entries loop
    const detail = {};
    for (const [name, plugins] of Object.entries(props.services)) {
      if (!(name in detail)) detail[name] = {};

      plugins.forEach((plugin) => {});
    }
    return detail;
  }),
});

onMounted(() => {
  setInterval(() => {
    console.log(services.details);
  }, 1000);
});

function setModal(modal, action, serviceName, service) {
  modal.data.operation = action;
  modal.data.service = service;
  // Case clone, SERVER_NAME need to be empty
  modal.data.serviceName = serviceName;
  modal.isOpen = true;
}

function getMethod(plugins) {
  let method = "";
  for (const [key, plugin] of Object.entries(plugins)) {
    if (plugin.id !== "general") continue;
    method = plugin.settings["SERVER_NAME"].method;
  }
  console.log("method", method);
  return method;
}

function getDetailBool(plugins, id, setting) {
  let value = null;
  for (const [key, plugin] of Object.entries(plugins)) {
    if (plugin.id !== id) continue;
    try {
      value = plugin.settings[setting].value === "yes" ? true : false;
    } catch (e) {
      try {
        value = plugin.settings[setting].default === "yes" ? true : false;
      } catch (e) {}
    }
    return value;
  }
}
</script>

<template>
  <div
    v-for="(plugins, name) in props.services"
    class="my-2 dark:brightness-110 overflow-hidden hover:scale-102 transition col-span-12 lg:col-span-6 3xl:col-span-4 p-4 w-full shadow-md break-words bg-white dark:bg-slate-850 dark:shadow-dark-xl rounded-2xl bg-clip-border"
  >
    <h2
      class="text-xl transition duration-300 ease-in-out text-center sm:text-left mb-1 font-bold dark:text-white/90"
    >
      {{ name }}
    </h2>
    <h3
      class="text-lg text-center sm:text-left mb-2 font-semibold text-gray-600 dark:text-white/80"
    >
      {{ getMethod(plugins) }}
    </h3>

    <div class="grid grid-cols-12">
      <p
        class="text-sm col-span-12 sm:col-span-6 flex justify-start items-center"
        v-for="detail in details"
      >
        <span class="mr-2">{{ $t(`services_detail_${detail.lang}`) }}</span>
        <ServicesSvgState
          :success="getDetailBool(plugins, detail.id, detail.setting)"
        />
      </p>
    </div>

    <div class="relative w-full flex justify-center sm:justify-end">
      <ServicesButtonClone
        @click="setModal(modalStore, 'clone', name, props.services[name])"
        :hostname="name"
      />
      <ServicesButtonEdit
        @click="setModal(modalStore, 'edit', name, props.services[name])"
        :hostname="name"
      />
      <ServicesButtonRedirect :hostname="name" />
      <ServicesButtonDelete
        @click="setModal(delModalStore, 'delete', name, props.services[name])"
        :hostname="name"
        :method="getMethod(plugins)"
      />
    </div>
  </div>
</template>
