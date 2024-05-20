<script setup>
import { reactive } from "vue";
import { langIndex } from "@utils/tabindex.js";
const lang = reactive({
  isOpen: false,
});

function updateLangStorage(lang) {
  sessionStorage.setItem("lang", lang);
  document.location.reload();
}
</script>

<template>
  <div class="fixed bottom-0 left-1 z-[800]">
    <ul
      id="switch-lang"
      role="radiogroup"
      v-show="lang.isOpen"
      class="max-h-[300px] overflow-auto"
    >
      <li
        v-for="(locale, id) in $i18n.availableLocales"
        role="radio"
        :key="`locale-${locale}`"
        :aria-checked="$i18n.locale === locale ? 'true' : 'false'"
      >
        <button
          :tabindex="lang.isOpen ? langIndex : -1"
          @click="
            () => {
              lang.isOpen = false;
              updateLangStorage(locale);
            }
          "
          aria-controls="switch-lang-text"
          :aria-selected="$i18n.locale === locale ? 'true' : 'false'"
        >
          <span :id="`${locale}-${id}`" class="sr-only">{{ locale }}</span>
          <span
            :aria-labelledby="`${locale}-${id}`"
            :class="[`fi fi-${locale}`]"
          ></span>
        </button>
      </li>
    </ul>
    <!-- current -->
    <button
      :tabindex="langIndex"
      aria-controls="switch-lang"
      :aria-expanded="lang.isOpen ? 'true' : 'false'"
      :aria-description="$t('dashboard_lang_dropdown_button_desc')"
      @click="lang.isOpen = lang.isOpen ? false : true"
    >
      <span id="current-lang" class="sr-only">{{ $i18n.locale }}</span>
      <span
        :aria-labelledby="`current-lang`"
        id="switch-lang-text"
        :class="[`fi fi-${$i18n.locale}`]"
      ></span>
    </button>
    <!-- end current -->
  </div>
</template>
