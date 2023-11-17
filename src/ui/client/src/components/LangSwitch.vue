<script setup>
import { reactive } from "vue";

const lang = reactive({
  isOpen: false,
});

function updateLangStorage(lang) {
  sessionStorage.setItem("lang", lang);
  window.location.href = window.location.href;
}
</script>

<template>
  <div class="fixed bottom-0 left-1 z-[800]">
    <ul v-if="lang.isOpen" class="max-h-[300px] overflow-auto">
      <li :key="`locale-${locale}`" v-for="locale in $i18n.availableLocales">
        <button
          @click="
            () => {
              $i18n.locale = locale;
              lang.isOpen = false;
              updateLangStorage(locale);
            }
          "
        >
          <span class="sr-only">{{ locale }}</span>
          <span :class="[`fi fi-${locale}`]"></span>
        </button>
      </li>
    </ul>
    <!-- current -->
    <button @click="lang.isOpen = lang.isOpen ? false : true">
      <span class="sr-only">{{ $i18n.locale }}</span>
      <span :class="[`fi fi-${$i18n.locale}`]"></span>
    </button>
    <!-- end current -->
  </div>
</template>
