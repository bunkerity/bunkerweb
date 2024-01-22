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
    const data = {};
    for (const [name, plugins] of Object.entries(props.services)) {
      plugins.forEach((plugin) => {
        if (!(name in data)) data[name] = {};
        if (plugin.id === "general") {
          data[name]["method"] = plugin.settings.SERVER_NAME.method;
        }

        for (let i = 0; i < details.length; i++) {
          if (details[i]["id"] !== plugin.id) continue;
          data[name][details[i]["id"]] =
            plugin.settings[details[i].setting].value ||
            plugin.settings[details[i].setting].default;
        }
      });
    }
    return data;
  }),
});

function setModal(modal, action, serviceName, service) {
  modal.data.operation = action;
  modal.data.service = service;
  // Case clone, SERVER_NAME need to be empty
  modal.data.serviceName = serviceName;
  modal.isOpen = true;
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
      {{ services.details[name]["method"] }}
    </h3>

    <div class="grid grid-cols-12">
      <div
        class="mb-1.5 text-sm col-span-12 sm:col-span-6 flex justify-center sm:justify-start items-center"
        v-for="detail in details"
      >
        <p class="mb-0 mr-2 text-black dark:text-white dark:opacity-80">
          {{ $t(`services_detail_${detail.lang}`) }}
        </p>
        <div class="relative">
          <ServicesSvgState
            :success="
              services.details[name][detail.id] === 'yes' ? true : false
            "
          />
        </div>
      </div>
    </div>

    <div class="mt-3.5 relative w-full flex justify-center sm:justify-end">
      <ServicesButtonClone
        @click="setModal(modalStore, 'clone', name, plugins)"
        :hostname="name"
      />
      <ServicesButtonEdit
        @click="setModal(modalStore, 'edit', name, plugins)"
        :hostname="name"
      />
      <ServicesButtonRedirect :hostname="name" />
      <ServicesButtonDelete
        @click="setModal(delModalStore, 'delete', name, plugins)"
        :hostname="name"
        :method="services.details[name]['method']"
      />
    </div>
  </div>
</template>
