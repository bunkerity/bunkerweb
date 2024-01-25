<script setup>
import { reactive, watch, computed } from "vue";
import SettingsLayout from "@components/Settings/Layout.vue";
import SettingsInput from "@components/Settings/Input.vue";
import SettingsSelect from "@components/Settings/Select.vue";
import SettingsUploadSvgWarning from "@components/Settings/Upload/Svg/Warning.vue";
import ModalBase from "@components/Modal/Base.vue";
import ButtonBase from "@components/Button/Base.vue";
import PluginStructure from "@components/Plugin/Structure.vue";
import { fetchAPI } from "@utils/api.js";
import { getMethodList, getSettingsByFilter } from "@utils/settings.js";
import { getRemainFromFilter } from "@utils/plugins.js";
import { contentIndex } from "@utils/tabindex.js";
import {
  useFeedbackStore,
  useBackdropStore,
  useRefreshStore,
} from "@store/global.js";
import { useModalStore } from "@store/services.js";
import { useConfigStore } from "@store/settings.js";

const backdropStore = useBackdropStore();
const modalStore = useModalStore();
const feedbackStore = useFeedbackStore();
const refreshStore = useRefreshStore();
const config = useConfigStore();

// Hide / Show settings and plugin base on that filters
const filters = reactive({
  keyword: "",
  method: "all",
});

const settings = reactive({
  // State of save button, check config and modalStore watchers
  save: false,
  // Get current services by name
  // Compare with current service name on config watcher to disable / enable save button
  servicesName: [],
  // Current service settings
  service: {},
  // Current service name or "new"
  serviceName: "",
  // Current plugin selected or remaining after filtering
  activePlugin: "",
  // Methods from current service
  methods: computed(() => {
    if (!settings.service || Object.keys(settings.service).length === 0)
      return ["all", "default", "ui"];

    const methods = ["all"];

    settings.service.forEach((plugin) => {
      // change methods by ui

      for (const [key, value] of Object.entries(plugin.settings)) {
        value.method = "ui";
        if (!methods.includes(value.method)) methods.push(value.method);
      }
    });

    console.log(methods);
    return methods;
  }),
  operation: "",
  plugins: computed(() => {
    // When opening modal, useModalStore will store data about service or action (like new)
    // useModalStore is watch to update settings keys and trigger setup
    if (
      !modalStore.data.service ||
      Object.keys(modalStore.data.service).length === 0
    )
      return {};
    // Get remain plugins
    const remainPlugins = getRemainFromFilter(
      getSettingsByFilter(modalStore.data.service, filters)
    );

    // Only update active plugin if no one active or previous active one
    // is no longer available with filter
    const isPrevPlugin = remainPlugins.includes(settings.activePlugin);

    // Case active plugin before update, need some check
    if (!isPrevPlugin || !settings.activePlugin) {
      settings.activePlugin = remainPlugins.length > 0 ? remainPlugins[0] : "";
    }

    return remainPlugins.length > 0 ? remainPlugins : [];
  }),
});

// close modal on backdrop click
watch(backdropStore, () => {
  modalStore.isOpen = false;
});

// When modalStore is update, reset prev config and update settings
watch(modalStore, (newVal, oldVal) => {
  // Reset
  config.$reset();
  filters.keyword = "";
  filters.method = "all";
  settings.save = false;

  // Update service settings and info
  settings.operation = newVal.data.operation;
  settings.serviceName = newVal.data.serviceName;
  settings.servicesName = Object.keys(newVal.data.services);
  config.data.services[newVal.data.serviceName] = {};

  settings.service =
    !newVal.data.service || Object.keys(newVal.data.service).length === 0
      ? {}
      : getSettingsByFilter(newVal.data.service, filters);
});

// Every time a setting is change, add some check to enable / disable save button
watch(config, () => {
  // Case new service without name, impossible to save
  if (
    ["new", "clone"].includes(settings.operation) &&
    !("SERVER_NAME" in config.data.services[settings.serviceName])
  ) {
    return (settings.save = false);
  }

  // Case name setting is on config but empty, impossible to save
  if (
    !!("SERVER_NAME" in config.data.services[settings.serviceName]) &&
    !config.data.services[settings.serviceName]["SERVER_NAME"]
  ) {
    return (settings.save = false);
  }

  // Case name already taken by another service, impossible to save
  if (
    !!("SERVER_NAME" in config.data.services[settings.serviceName]) &&
    config.data.services[settings.serviceName]["SERVER_NAME"]
  ) {
    if (
      settings.servicesName.includes(
        config.data.services[settings.serviceName]["SERVER_NAME"]
      )
    ) {
      return (settings.save = false);
    }
  }

  // We can save service if at least one setting is different from default
  // At least SERVER_NAME needed
  if (Object.keys(config.data.services[settings.serviceName]).length === 0) {
    return (settings.save = false);
  }

  // Passed all check, enable save button
  return (settings.save = true);
});

const sendConf = reactive({
  isPend: false,
  isErr: false,
  // Data from fetch
  data: [],
});

async function sendServConf() {
  // Case no service to send
  if (Object.keys(config.data.services).length === 0) return;

  // Case new service, name is empty, get it from setting
  // Else get it from service name
  const servName = ["new", "clone"].includes(settings.serviceName)
    ? config.data.services[settings.serviceName]["SERVER_NAME"]
    : settings.serviceName;

  await fetchAPI(
    `/api/config/service/${servName}?method=ui`,
    "PUT",
    config.data.services[settings.serviceName],
    sendConf,
    feedbackStore.addFeedback
  )
    .then((res) => {
      // Case saved, close modal, go to root path and refresh
      if (res.type === "success") {
        modalStore.isOpen = false;
        refreshStore.refresh();
        return;
      }
    })
    .catch((e) => {});
}
</script>
<template>
  <ModalBase
    cardSize="large"
    id="service-settings-modal"
    :aria-hidden="modalStore.isOpen ? 'false' : 'true'"
    :title="
      settings.operation === 'clone'
        ? $t('services_active_clone')
        : settings.operation === 'new'
        ? $t('services_active_new')
        : $t('services_active_base', {
            name: settings.serviceName,
          })
    "
    v-show="modalStore.isOpen"
  >
    <div class="grid grid-cols-12">
      <SettingsLayout
        class="flex w-full col-span-12 sm:col-span-6 md:col-span-4 lg:col-span-3"
        :label="$t('services_list_select_plugin')"
        name="plugins"
      >
        <SettingsSelect
          @inp="(v) => (settings.activePlugin = v)"
          :settings="{
            id: 'plugins',
            value: settings.activePlugin,
            values: settings.plugins,
          }"
          :key="settings.serviceName"
        />
      </SettingsLayout>
      <SettingsLayout
        class="flex w-full col-span-12 sm:col-span-6 md:col-span-4 lg:col-span-3"
        :label="$t('services_filter_search_setting')"
        name="keyword"
      >
        <SettingsInput
          @inp="(v) => (filters.keyword = v)"
          :settings="{
            id: 'keyword',
            type: 'text',
            value: '',
            placeholder: $t('services_filter_search_setting_placeholder'),
          }"
        />
      </SettingsLayout>
      <SettingsLayout
        class="flex w-full col-span-12 sm:col-span-6 md:col-span-4 lg:col-span-3"
        :label="$t('services_filter_method_setting')"
        name="method"
      >
        <SettingsSelect
          @inp="(v) => (filters.method = v)"
          :settings="{
            id: 'method',
            value: filters.method,
            values: settings.methods,
          }"
          :key="settings.methods"
        />
      </SettingsLayout>
    </div>

    <hr class="col-span-12 line-separator z-10 w-full mb-3" />

    <div class="col-span-12">
      <PluginStructure
        :serviceName="settings.serviceName"
        :plugins="settings.service"
        :active="settings.activePlugin"
        :key="settings.serviceName"
      />
    </div>
    <div
      class="col-span-12 flex flex-col items-center w-full justify-center mt-8 mb-0"
    >
      <ButtonBase
        :tabindex="contentIndex"
        :aria-disabled="settings.save ? 'true' : 'false'"
        :disabled="settings.save ? false : true"
        @click="sendServConf()"
        :color="settings.operation === 'edit' ? 'edit' : 'valid'"
        size="lg"
        class="w-fit"
      >
        {{
          settings.operation === "edit" ? $t("action_edit") : $t("action_add")
        }}
      </ButtonBase>
      <hr class="line-separator z-10 w-1/2" />
      <p class="dark:text-gray-500 text-xs text-center mb-0">
        <span class="mx-0.5">
          <SettingsUploadSvgWarning class="scale-90" />
        </span>
        <span>
          {{ $t("services_actions_warning") }}
        </span>
      </p>
    </div>
  </ModalBase>
</template>
