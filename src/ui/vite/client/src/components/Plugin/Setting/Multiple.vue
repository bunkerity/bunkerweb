<script setup>
import { reactive, defineProps, computed } from "vue";
import PluginSettingHeader from "@components/Plugin/Setting/Header.vue";
import PluginInput from "@components/Plugin/Input.vue";
import PluginSelect from "@components/Plugin/Select.vue";
import PluginCheckbox from "@components/Plugin/Checkbox.vue";
import { getSettingsMultipleList } from "@utils/settings.js";
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

const multiple = reactive({
  number: 0,
  isShow: true,
  groups: computed(() => {
    const filter = getSettingsMultipleList(
      JSON.parse(JSON.stringify(props.settings))
    );
    return filter;
  }),
  new: {},
});

function toggle() {
  multiple.isShow = multiple.isShow ? false : true;
}

function addMultToGroup(groupName) {
  // Get base to add
  const baseMult = multiple.groups[groupName]["base"];
  // Get new number, check current ones first
  const numList = [];
  Object.entries(multiple.groups[groupName]).forEach(([groupName, data]) => {
    if (!isNaN(groupName)) numList.push(+groupName);
  });
  const nextNum = Math.max(...numList);
}
</script>

<template>
  <div
    v-if="Object.keys(multiple.groups).length !== 0"
    data-setting-container
    class="col-span-12 grid grid-cols-12"
  >
    <div
      class="col-span-12"
      v-for="(multGroup, multGroupName) in multiple.groups"
    >
      <p>{{ multGroupName }}</p>
      <div
        data-multiple-handler
        class="flex items-center mx-0 sm:mx-4 md:mx-6 md:my-3 my-2 2xl:mx-6 2xl:my-3 col-span-12"
      >
        <button
          @click="addMultToGroup(multGroupName)"
          class="ml-3 dark:brightness-90 inline-block px-3 py-1.5 font-bold text-center text-white uppercase align-middle transition-all rounded-lg cursor-pointer bg-green-500 hover:bg-green-500/80 focus:bg-green-500/80 leading-normal text-md ease-in tracking-tight-rem shadow-xs bg-150 bg-x-25 hover:-translate-y-px active:opacity-85 hover:shadow-md"
        >
          Add
        </button>
        <button
          @click="toggle()"
          class="ml-3 dark:brightness-90 inline-block px-3 py-1.5 font-bold text-center text-white uppercase align-middle transition-all rounded-lg cursor-pointer bg-sky-500 hover:bg-sky-500/80 focus:bg-sky-500/80 leading-normal text-md ease-in tracking-tight-rem shadow-xs bg-150 bg-x-25 hover:-translate-y-px active:opacity-85 hover:shadow-md"
        >
          {{ multiple.isShow ? "HIDE" : "SHOW" }}
        </button>
      </div>
      <div class="col-span-12" v-if="multiple.isShow">
        <div>
          <div
            class="grid grid-cols-12"
            v-for="(settingsGroup, settingsGroupName) in multGroup"
            :key="settingsGroup"
          >
            <div
              v-for="(setting, settingName) in settingsGroup"
              class="ml-2 mr-4 md:ml-3 md:mr-6 xl:ml-4 xl:mr-8 my-2 md:my-3 col-span-12 md:col-span-6 2xl:col-span-4"
            >
              <PluginSettingHeader :label="settingName" :help="setting.help" />
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
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
