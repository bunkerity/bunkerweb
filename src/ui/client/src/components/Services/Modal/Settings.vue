<script setup>
import { reactive, watch } from "vue";
import SettingsLayout from "@components/Settings/Layout.vue";
import SettingsInput from "@components/Settings/Input.vue";
import SettingsSelect from "@components/Settings/Select.vue";
import SettingsUploadSvgWarning from "@components/Settings/Upload/Svg/Warning.vue";
import { getMethodList, getSettingsByFilter } from "@utils/settings.js";
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
  plugins: [],
  activePlugin: "",
  setup: computed(() => {
    if (!modalStore.data.service) return {};
    // Filter data to display
    const filterSettings = getSettingsByFilter(
      modalStore.data.service,
      filters
    );

    // Get remain plugins
    const remainPlugins = getRemainFromFilter(cloneMultisitePlugin);
    settings.plugins = remainPlugins.length > 0 ? remainPlugins : [];

    // Set active plugin
    let pluginName = "";
    // Set first plugin as active if none
    if (!settings.activePlugin) return;
    pluginName = remainPlugins.length > 0 ? remainPlugins[0] : "";

    // Case active plugin before update, need some check
    if (pluginName) {
      // Case prev active plugin passed filter
      const isPlugin = remainPlugins.indexOf(pluginName) !== -1 ? true : false;

      // Case not, set first passed one or empty
      if (!isPlugin) {
        pluginName = remainPlugins.length > 0 ? remainPlugins[0] : "";
      }
    }

    return filterSettings;
  }),
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
    id="service-delete-modal"
    :aria-hidden="modalStore.isOpen ? 'false' : 'true'"
    :title="$t('services_delete_title')"
    v-show="modalStore.isOpen"
    class="z-10 col-span-12 grid grid-cols-12 relative"
  >
    <div>
      <SettingsLayout
        class="flex w-full col-span-12"
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
        />
      </SettingsLayout>
    </div>
    <div>
      <SettingsLayout
        class="flex w-full col-span-12 md:col-span-6 lg:col-span-12"
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
    </div>
    <div>
      <SettingsLayout
        class="flex w-full col-span-12 md:col-span-6 lg:col-span-12"
        :label="$t('services_filter_method_setting')"
        name="method"
      >
        <SettingsSelect
          @inp="(v) => (filters.method = v)"
          :settings="{
            id: 'method',
            value: filters.method,
            values: getMethodList(),
          }"
        />
      </SettingsLayout>
    </div>
    <hr class="col-span-12 line-separator z-10 w-full mb-6" />

    <div class="col-span-12">
      <PluginStructure
        :serviceName="modalStore.serviceName"
        :plugins="settings.setup"
      />
    </div>
    <div
      class="col-span-12 flex flex-col items-center w-full justify-center mt-8 mb-2"
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
      <p class="dark:text-gray-500 text-xs text-center mt-1 mb-2">
        <span class="mx-0.5">
          <SettingsUploadSvgWarning class="scale-90" />
        </span>
        {{ $t("services_actions_warning") }}
      </p>
    </div>
  </ModalBase>
</template>
