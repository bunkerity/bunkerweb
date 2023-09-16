<script setup>
import { reactive, defineProps, computed } from "vue";
import PluginSettingHeader from "@components/Plugin/Setting/Header.vue";
import PluginInput from "@components/Plugin/Input.vue";
import PluginSelect from "@components/Plugin/Select.vue";
import PluginCheckbox from "@components/Plugin/Checkbox.vue";
import ButtonBase from "@components/Button/Base.vue";
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
    // Remove delete item
    Object.entries(multiple.delete).forEach(
      ([multGroupName, settingsGroupList]) => {
        settingsGroupList.forEach((settingsGroup) => {
          delete filter[multGroupName][settingsGroup];
        });
      }
    );

    // Add new multiple groups
    Object.entries(multiple.new).forEach(([multGroupName, groupData]) => {
      Object.assign(filter[multGroupName], groupData);
    });

    return filter;
  }),
  new: {},
  delete: {},
});

function toggle() {
  multiple.isShow = multiple.isShow ? false : true;
}

function addMultToGroup(groupName) {
  // Get base to add
  const baseMult = JSON.parse(
    JSON.stringify(multiple.groups[groupName]["base"])
  );
  // Get a valid new group number
  // We need to get all already taken nums
  // => multiple.groups (props.settings + new)
  const numList = [];
  Object.entries(multiple.groups[groupName]).forEach(([groupName, data]) => {
    if (!isNaN(groupName) && !numList.includes(groupName))
      numList.push(+groupName);
  });

  // By default, we will use max num possible
  const nextNum = numList.length > 0 ? Math.max(...numList) + 1 : 1;
  // Format item with num
  Object.entries(baseMult).forEach(([settingName, settingData]) => {
    baseMult[`${settingName}_${nextNum}`] = settingData;
    delete baseMult[settingName];
  });
  // Create group and add new item, but two cases
  if (!(groupName in multiple.new)) multiple.new[groupName] = {};
  multiple.new[groupName][nextNum] = baseMult;
}

function deleteMultToGroup(multGroupName, settingsGroupName) {
  if (!(multGroupName in multiple.new)) multiple.new[multGroupName] = {};

  // Case item was a new one, delete from new
  if (!!(settingsGroupName in multiple.new[multGroupName])) {
    delete multiple.new[multGroupName][settingsGroupName];
  }

  // Case item is from props settings, we can delete it directly
  // We will store it on delete group and remove from props
  // When multiple.groups setup
  if (!!(settingsGroupName in multiple.groups[multGroupName])) {
    if (!(multGroupName in multiple.delete))
      multiple.delete[multGroupName] = [];

    // Add setting group to delete
    multiple.delete[multGroupName].includes(settingsGroupName)
      ? true
      : multiple.delete[multGroupName].push(settingsGroupName);
  }
}
</script>

<template>
  <div
    v-if="Object.keys(multiple.groups).length !== 0"
    data-setting-container
    class="col-span-12 grid grid-cols-12"
  >
    <div
      class="col-span-12 my-4"
      v-for="(multGroup, multGroupName) in multiple.groups"
    >
      <div
        data-multiple-handler
        class="flex items-center my-3 mx-4 col-span-12"
      >
        <p
          class="transition duration-300 ease-in-out font-bold uppercase text-[14px] text-gray-700 dark:text-white/90 mb-0"
        >
          {{ multGroupName.replace("-", " ") }}
        </p>
        <ButtonBase
          color="valid"
          size="sm"
          @click="addMultToGroup(multGroupName)"
          class="ml-3"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            stroke-width="1.5"
            stroke="currentColor"
            class="w-7 h-7"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M12 9v6m3-3H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
        </ButtonBase>
        <ButtonBase @click="toggle()" color="info" size="sm" class="ml-2">
          <svg
            v-if="multiple.isShow"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            stroke-width="1.5"
            stroke="currentColor"
            class="w-7 h-7"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z"
            />
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
            />
          </svg>
          <svg
            v-if="!multiple.isShow"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            stroke-width="1.5"
            stroke="currentColor"
            class="w-7 h-7"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 01-4.293 5.774M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65m0 0a3 3 0 10-4.243-4.243m4.242 4.242L9.88 9.88"
            />
          </svg>
        </ButtonBase>
      </div>
      <div class="col-span-12 mx-4" v-if="multiple.isShow">
        <div v-for="(settingsGroup, settingsGroupName) in multGroup">
          <div
            class="relative grid grid-cols-12 bg-gray-50 dark:bg-slate-900/30 w-full my-6 border dark:border-gray-700 rounded"
            v-if="settingsGroupName !== 'base'"
          >
            <div
              v-for="(setting, settingName) in settingsGroup"
              :class="[setting.isMatchFilter ? '' : 'hidden']"
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
            <div class="col-span-12 w-full flex justify-center mt-2 mb-4">
              <ButtonBase
                @click="deleteMultToGroup(multGroupName, settingsGroupName)"
                color="delete"
                size="sm"
                ><svg
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke-width="1.5"
                  stroke="currentColor"
                  class="w-6 h-6"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0"
                  />
                </svg>
              </ButtonBase>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
