<script setup>
import { computed, defineProps, onMounted } from "vue";
import { getSettingsSimple } from "@utils/settings.js";
import PluginSettingHeader from "@components/Plugin/Setting/Header.vue";
import PluginInput from "@components/Plugin/Input.vue";
import PluginSelect from "@components/Plugin/Select.vue";
import PluginCheckbox from "@components/Plugin/Checkbox.vue";
const props = defineProps({
  settings: {
    type: Object,
  },
  serviceName: {
    type: String,
    required: false,
    default: "",
  },
});

const filterSettings = computed(() =>
  getSettingsSimple(JSON.parse(JSON.stringify(props.settings)))
);
</script>

<template>
  <div
    v-for="setting in filterSettings"
    :class="[setting.isMatchFilter ? '' : 'hidden']"
    class="ml-2 mr-4 md:ml-3 md:mr-6 xl:ml-4 xl:mr-8 my-2 md:my-3 col-span-12 md:col-span-6 2xl:col-span-4"
  >
    <PluginSettingHeader :label="setting.label" :help="setting.help" />
    <PluginInput
      v-if="setting.type === 'text' || setting.type === 'password'"
      :serviceName="props.serviceName"
      :setting="setting"
    />
    <PluginSelect
      v-if="setting.type === 'select'"
      :serviceName="props.serviceName"
      :setting="setting"
    />
    <PluginCheckbox
      v-if="setting.type === 'check'"
      :serviceName="props.serviceName"
      :setting="setting"
    />
  </div>
</template>
