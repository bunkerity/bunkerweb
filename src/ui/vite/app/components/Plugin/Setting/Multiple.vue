<script setup>
const props = defineProps({
  settings: {
    type: Object,
  },
});

const filterSettings = {};

const multiple = reactive({
  number: 0,
  isShow: false,
});

function toggle() {
  multiple.isShow = multiple.isShow ? false : true;
}
</script>

<template>
  <div
    v-for="setting in filterSettings"
    data-setting-container
    class="ml-2 mr-4 md:ml-3 md:mr-6 xl:ml-4 xl:mr-8 my-2 md:my-3 col-span-12 md:col-span-6 2xl:col-span-4"
  >
    <div
      data-multiple-handler
      class="flex items-center mx-0 sm:mx-4 md:mx-6 md:my-3 my-2 2xl:mx-6 2xl:my-3 col-span-12"
    >
      <h5 class="input-title">
        {{ settings.multiple }}
      </h5>
      <button
        @click="multiple.number++"
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
    <div v-if="multiple.isShow">
      <div
        v-for="n in multiple.number"
        class="bg-gray-50 dark:bg-slate-900/30 grid w-full mb-8 grid-cols-12 border dark:border-gray-700 rounded"
      >
        <SettingInput v-if="setting.type === 'input'" :setting="setting" />
        <SettingSelect v-if="setting.type === 'select'" :setting="setting" />
        <SettingCheckbox
          v-if="setting.type === 'checkbox'"
          :setting="setting"
        />
      </div>
    </div>
  </div>
</template>
