<script setup>
import { reactive } from "vue";

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
      :aria-hidden="lang.isOpen ? 'false' : 'true'"
      role="radiogroup"
      v-show="lang.isOpen"
      class="max-h-[300px] overflow-auto"
    >
      <li
        v-for="(locale, id) in $i18n.availableLocales"
        role="radio"
        :tabindex="id"
        :aria-checked="$i18n.locale === locale ? 'true' : 'false'"
        :key="`locale-${locale}`"
      >
        <button
          @click="
            () => {
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
    <button
      aria-controls="switch-lang"
      :aria-description="$t('dashboard_lang_dropdown_button_desc')"
      @click="lang.isOpen = lang.isOpen ? false : true"
    >
      <span class="sr-only">{{ $i18n.locale }}</span>
      <span :class="[`fi fi-${$i18n.locale}`]"></span>
    </button>
    <!-- end current -->
  </div>
</template>
