<script setup>
import ServicesButtonClone from "@components/Services/Button/Clone.vue";
import ServicesButtonEdit from "@components/Services/Button/Edit.vue";
import ServicesButtonRedirect from "@components/Services/Button/Redirect.vue";
import ServicesButtonDelete from "@components/Services/Button/Delete.vue";
import ServicesSvgState from "@components/Services/Svg/State.vue";
import { useModalStore, useDelModalStore } from "@store/services.js";
import { useConfigStore } from "@store/settings.js";
import { defineProps, reactive, computed } from "vue";

const modalStore = useModalStore();
const delModalStore = useDelModalStore();
const config = useConfigStore();

const props = defineProps({
  services: {
    type: Object,
    required: true,
    default: {},
  },
  filters: {
    type: Object,
    required: true,
    default: {},
  },
  details: {
    type: Array,
    required: true,
    default: [],
  },
});

const services = reactive({
  details: computed(() => {
    if (!props.services || props.details.length === 0) return [];

    // create object entries loop
    const data = {};
    for (const [name, plugins] of Object.entries(props.services)) {
      plugins.forEach((plugin) => {
        if (!(name in data)) data[name] = {};
        if (plugin.id === "general") {
          data[name]["method"] = plugin.settings.SERVER_NAME.method;
        }

        for (let i = 0; i < props.details.length; i++) {
          if (props.details[i]["id"] !== plugin.id) continue;
          data[name][props.details[i]["id"]] =
            plugin.settings[props.details[i].setting].value ||
            plugin.settings[props.details[i].setting].default;
        }
      });
    }
    return data;
  }),
});

function setModal(modal, operation, serviceName, service, method = "") {
  config.$reset();

  // Case delete
  if (operation === "delete") {
    modal.data.serviceName = serviceName;
    modal.data.method = method;
    return (modal.isOpen = true);
  }

  modal.data.operation = operation;

  // Case clone
  if (operation === "clone") {
    modal.data.serviceName = "clone";

    const serviceClone = JSON.parse(JSON.stringify(service));
    serviceClone.forEach((plugin) => {
      // change methods by ui
      plugin.method = "ui";

      for (const [key, value] of Object.entries(plugin.settings)) {
        value.method = "ui";
      }

      // change default server_name by empty
      if (plugin.id.toLowerCase() !== "general") return;
      plugin.settings.SERVER_NAME.value = "";
      plugin.settings.SERVER_NAME.default = "";
    });

    modal.data.service = serviceClone;

    return (modal.isOpen = true);
  }

  // Others cases
  modal.data.service = JSON.parse(JSON.stringify(service));
  modal.data.serviceName = serviceName;
  modal.isOpen = true;
}
</script>

<template>
  <div
    v-for="(plugins, name) in props.services"
    :class="[filters[name] ? '' : 'hidden']"
    class="my-2 dark:brightness-110 overflow-hidden hover:scale-102 transition col-span-12 md:col-span-6 3xl:col-span-4 p-4 w-full shadow-md break-words bg-white dark:bg-slate-850 dark:shadow-dark-xl rounded-2xl bg-clip-border"
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
        class="mb-1.5 text-sm col-span-12 sm:col-span-6 md:col-span-12 lg:col-span-6 flex justify-center sm:justify-start md:justify-center lg:justify-start items-center"
        v-for="detail in props.details"
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
        @click="
          setModal(
            delModalStore,
            'delete',
            name,
            plugins,
            services.details[name]['method'],
          )
        "
        :hostname="name"
        :method="services.details[name]['method']"
      />
    </div>
  </div>
</template>
