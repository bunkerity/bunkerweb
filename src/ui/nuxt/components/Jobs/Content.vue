<script setup>
const props = defineProps({
  items: {
    type: Array,
    required: true,
  },
  positions: {
    type: Array,
    required: true,
  },
});
</script>

<template>
  <ul class="col-span-12 w-full">
    <!-- job item-->
    <li
      v-for="(item, id) in props.items"
      class="items-center grid grid-cols-12 border-b border-gray-300 py-2.5"
    >
      <div
        v-for="(value, key, index) in item"
        :data-key="key"
        :class="[
          props.positions[index],
          typeof value === 'boolean' ? 'ml-3.5' : '',
          'my-1 dark:text-gray-400 text-sm',
          Array.isArray(value) ? 'mr-6' : '',
        ]"
      >
        <button
          v-if="value.constructor.name === 'Object'"
          type="submit"
          name="run"
          value="reload"
          class="valid-btn mx-1 text-xs"
        >
          run
        </button>
        <p class="m-0" v-if="typeof value === 'string'">
          {{ value }}
        </p>
        <div
          class="dark:opacity-80 -translate-y-0.5"
          v-if="typeof value === 'boolean'"
        >
          <div
            class="bg-white w-3 h-3 rounded -z-10 translate-x-1 translate-y-1.5 absolute"
          ></div>
          <svg
            v-if="value"
            class="fill-green-500 h-5 w-5 z-10"
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 512 512"
          >
            <path
              d="M256 512c141.4 0 256-114.6 256-256S397.4 0 256 0S0 114.6 0 256S114.6 512 256 512zM369 209L241 337c-9.4 9.4-24.6 9.4-33.9 0l-64-64c-9.4-9.4-9.4-24.6 0-33.9s24.6-9.4 33.9 0l47 47L335 175c9.4-9.4 24.6-9.4 33.9 0s9.4 24.6 0 33.9z"
            />
          </svg>
          <svg
            v-if="!value"
            class="fill-red-500 h-5 w-5 z-10"
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 512 512"
          >
            <path
              d="M256 512c141.4 0 256-114.6 256-256S397.4 0 256 0S0 114.6 0 256S114.6 512 256 512zM175 175c9.4-9.4 24.6-9.4 33.9 0l47 47 47-47c9.4-9.4 24.6-9.4 33.9 0s9.4 24.6 0 33.9l-47 47 47 47c9.4 9.4 9.4 24.6 0 33.9s-24.6 9.4-33.9 0l-47-47-47 47c-9.4 9.4-24.6 9.4-33.9 0s-9.4-24.6 0-33.9l47-47-47-47c-9.4-9.4-9.4-24.6 0-33.9z"
            />
          </svg>
        </div>
        <SettingsSelect
          v-if="Array.isArray(value)"
          :setting="{
            id: 'state',
            value: 'all',
            values: ['all', 'true', 'false'],
          }"
        />
      </div>
    </li>
    <!-- end job item-->
  </ul>
</template>
