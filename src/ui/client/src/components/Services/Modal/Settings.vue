<script setup>
import { reactive, watch } from "vue";
import SettingsLayout from "@components/Settings/Layout.vue";
import SettingsInput from "@components/Settings/Input.vue";
import SettingsSelect from "@components/Settings/Select.vue";
import SettingsUploadSvgWarning from "@components/Settings/Upload/Svg/Warning.vue";
import { getMethodList, getSettingsByFilter } from "@utils/settings.js";
import { getRemainFromFilter } from "@utils/plugins.js";
import ModalBase from "@components/Modal/Base.vue";
import ButtonBase from "@components/Button/Base.vue";
import { contentIndex } from "@utils/tabindex.js";
import PluginStructure from "@components/Plugin/Structure.vue";
import {
  useFeedbackStore,
  useBackdropStore,
  useRefreshStore,
} from "@store/global.js";
import { useModalStore } from "@store/services.js";
import { useConfigStore } from "@store/settings.js";
import { computed } from "vue";
import { onMounted } from "vue";

const backdropStore = useBackdropStore();
const modalStore = useModalStore();
const feedbackStore = useFeedbackStore();
const refreshStore = useRefreshStore();
const config = useConfigStore();

// close modal on backdrop click
watch(backdropStore, () => {
  modalStore.isOpen = false;
});

// Hide / Show settings and plugin base on that filters
const filters = reactive({
  keyword: "",
  method: "all",
});

const settings = reactive({
  service: {},
  serviceName: "",
  plugins: [],
  activePlugin: "",
  methods: getMethodList(),
  setup: computed(() => {
    if (!settings.service || Object.keys(settings.service).length === 0)
      return {};
    // Filter data to display
    const filterSettings = getSettingsByFilter(settings.service, filters);

    // Get remain plugins
    const remainPlugins = getRemainFromFilter(filterSettings);

    // Only update active plugin if no one active or previous active one
    // is no longer available with filter
    const isPrevPlugin = remainPlugins.includes(settings.activePlugin);

    // Case active plugin before update, need some check
    if (!isPrevPlugin || !settings.activePlugin) {
      settings.activePlugin = remainPlugins.length > 0 ? remainPlugins[0] : "";
    }

    settings.plugins = remainPlugins.length > 0 ? remainPlugins : [];

    return filterSettings;
  }),
});

watch(modalStore, (newVal, oldVal) => {
  settings.service = newVal.data.service;
  settings.serviceName = newVal.data.serviceName;
});

const sendConf = reactive({
  isPend: false,
  isErr: false,
  // Data from fetch
  data: [],
});

async function sendServConf() {
  // Case nothing to send
  console.log(config.data.services);
  if (Object.keys(config.data.services).length === 0) return;

  const promises = [];
  // Send services
  const services = config.data.services;
}

const saveBtn = reactive({
  disabled: true,
});
</script>
<template>
  <ModalBase
    cardSize="large"
    id="service-delete-modal"
    :aria-hidden="modalStore.isOpen ? 'false' : 'true'"
    :title="
      settings.serviceName === 'new'
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
          :key="settings.serviceName"
        />
      </SettingsLayout>
    </div>

    <hr class="col-span-12 line-separator z-10 w-full mb-6" />

    <div class="col-span-12">
      <PluginStructure
        :serviceName="modalStore.data.serviceName"
        :plugins="settings.setup"
        :active="settings.activePlugin"
      />
    </div>
    <div
      class="col-span-12 flex flex-col items-center w-full justify-center mt-8 mb-0"
    >
      <ButtonBase
        :tabindex="contentIndex"
        :disabled="saveBtn.disabled"
        :aria-disabled="saveBtn.disabled ? 'true' : 'false'"
        @click="sendServConf()"
        color="valid"
        size="lg"
        class="w-fit"
      >
        {{ $t("action_save") }}
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
