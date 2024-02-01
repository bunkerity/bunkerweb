<script setup>
import { defineProps, reactive } from "vue";

const props = defineProps({
  isDraft: {
    type: Boolean,
    required: false,
  },
  servName: {
    type: String,
    required: false,
  },
});

const icon = reactive({
  isOpen: false,
});
</script>

<template>
  <button
    @pointerover="icon.isOpen = true"
    @pointerout="icon.isOpen = true"
    @pointedown="icon.isOpen = true"
    @pointerup="icon.isOpen = true"
    v-if="props.isDraft"
    class="group relative"
    :aria-controls="`${props.servName}-draft`"
    :aria-expanded="icon.isOpen ? 'true' : 'false'"
    :aria-describedby="`${props.servName}-draft-desc`"
  >
    <p
      :id="`${props.servName}-draft`"
      :aria-hidden="icon.isOpen ? 'false' : 'true'"
      class="pointer-events-none dark:text-gray-300 -z-10 opacity-0 group-hover:z-10 group-hover:opacity-100 transition fixed bg-white dark:bg-slate-800 rounded right-12 px-1 py-0.5"
    >
      {{ $t("services_draft") }}
      <span :id="`${props.servName}-draft-text`" class="sr-only">
        {{ $t("services_draft_desc") }}
      </span>
    </p>
    <svg
      aria-hidden="true"
      role="img"
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="currentColor"
      class="w-6 h-6 fill-gray-700 dark:fill-gray-300 cursor-pointer-none"
    >
      <path
        fill-rule="evenodd"
        d="M10.5 3.798v5.02a3 3 0 0 1-.879 2.121l-2.377 2.377a9.845 9.845 0 0 1 5.091 1.013 8.315 8.315 0 0 0 5.713.636l.285-.071-3.954-3.955a3 3 0 0 1-.879-2.121v-5.02a23.614 23.614 0 0 0-3 0Zm4.5.138a.75.75 0 0 0 .093-1.495A24.837 24.837 0 0 0 12 2.25a25.048 25.048 0 0 0-3.093.191A.75.75 0 0 0 9 3.936v4.882a1.5 1.5 0 0 1-.44 1.06l-6.293 6.294c-1.62 1.621-.903 4.475 1.471 4.88 2.686.46 5.447.698 8.262.698 2.816 0 5.576-.239 8.262-.697 2.373-.406 3.092-3.26 1.47-4.881L15.44 9.879A1.5 1.5 0 0 1 15 8.818V3.936Z"
        clip-rule="evenodd"
      />
    </svg>
  </button>
  <button
    @pointerover="icon.isOpen = true"
    @pointerout="icon.isOpen = true"
    @pointedown="icon.isOpen = true"
    @pointerup="icon.isOpen = true"
    v-if="!props.isDraft"
    class="group relative"
    :aria-controls="`${props.servName}-online`"
    :aria-expanded="icon.isOpen ? 'true' : 'false'"
    :aria-describedby="`${props.servName}-online-desc`"
  >
    <p
      :id="`${props.servName}-online`"
      :aria-hidden="icon.isOpen ? 'false' : 'true'"
      class="pointer-events-none dark:text-gray-300 -z-10 opacity-0 group-hover:z-10 group-hover:opacity-100 transition fixed bg-white dark:bg-slate-800 rounded right-12 px-1 py-0.5"
    >
      {{ $t("services_online") }}
      <span :id="`${props.servName}-online-text`" class="sr-only">
        {{ $t("services_online_desc") }}
      </span>
    </p>
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="currentColor"
      class="w-6 h-6 fill-gray-700 dark:fill-gray-300 cursor-pointer-none"
    >
      <path
        d="M21.721 12.752a9.711 9.711 0 0 0-.945-5.003 12.754 12.754 0 0 1-4.339 2.708 18.991 18.991 0 0 1-.214 4.772 17.165 17.165 0 0 0 5.498-2.477ZM14.634 15.55a17.324 17.324 0 0 0 .332-4.647c-.952.227-1.945.347-2.966.347-1.021 0-2.014-.12-2.966-.347a17.515 17.515 0 0 0 .332 4.647 17.385 17.385 0 0 0 5.268 0ZM9.772 17.119a18.963 18.963 0 0 0 4.456 0A17.182 17.182 0 0 1 12 21.724a17.18 17.18 0 0 1-2.228-4.605ZM7.777 15.23a18.87 18.87 0 0 1-.214-4.774 12.753 12.753 0 0 1-4.34-2.708 9.711 9.711 0 0 0-.944 5.004 17.165 17.165 0 0 0 5.498 2.477ZM21.356 14.752a9.765 9.765 0 0 1-7.478 6.817 18.64 18.64 0 0 0 1.988-4.718 18.627 18.627 0 0 0 5.49-2.098ZM2.644 14.752c1.682.971 3.53 1.688 5.49 2.099a18.64 18.64 0 0 0 1.988 4.718 9.765 9.765 0 0 1-7.478-6.816ZM13.878 2.43a9.755 9.755 0 0 1 6.116 3.986 11.267 11.267 0 0 1-3.746 2.504 18.63 18.63 0 0 0-2.37-6.49ZM12 2.276a17.152 17.152 0 0 1 2.805 7.121c-.897.23-1.837.353-2.805.353-.968 0-1.908-.122-2.805-.353A17.151 17.151 0 0 1 12 2.276ZM10.122 2.43a18.629 18.629 0 0 0-2.37 6.49 11.266 11.266 0 0 1-3.746-2.504 9.754 9.754 0 0 1 6.116-3.985Z"
      />
    </svg>
  </button>
</template>
