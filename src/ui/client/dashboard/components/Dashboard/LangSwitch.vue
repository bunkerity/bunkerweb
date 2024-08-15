<script setup>
import { onMounted, reactive } from "vue";
import { langIndex } from "@utils/tabindex.js";

/**
 * @name Dashboard/LangSwitch.vue
 *  @description This component is a float element with a flag of the current language.
 *  When clicked, it will display a list of available languages, clicking on one will change the language.
 * Your language isn't here ? You can contribute by following the part of the documentation about translations.
 */

const lang = reactive({
  isOpen: false,
  curr: "",
});

/**
 * @name updateLangStorage
 * @description This function will update the language in the session storage and reload the page.
 * On reload, we will retrieve the language from the session storage and set it.
 * @param {String} lang - The language to set.
 * @returns {void}
 */
function updateLangStorage(lang) {
  sessionStorage.setItem("lang", lang);
  document.location.reload();
}

onMounted(() => {
  lang.curr = document.querySelector("#current-lang").textContent;
  document.querySelector("html").setAttribute("lang", lang.curr);
});
</script>

<template>
  <div class="lang-switch-container">
    <div
      role="radiogroup"
      id="switch-lang"
      v-show="lang.isOpen"
      class="lang-switch-list"
    >
      <template v-for="(locale, id) in $i18n.availableLocales" :key="locale">
        <button
          :class="['lang-switch-item']"
          role="radio"
          type="button"
          :tabindex="lang.isOpen ? langIndex : '-1'"
          :aria-labelledby="`${locale}-${id}`"
          @click.prevent="
            () => {
              lang.isOpen = false;
              updateLangStorage(locale);
            }
          "
          aria-controls="switch-lang-text"
          :aria-checked="$i18n.locale === locale ? 'true' : 'false'"
        >
          <span
            :aria-labelledby="`${locale}-${id}`"
            :class="[`fi fi-${locale}`]"
          ></span>
          <span :id="`${locale}-${id}`" class="sr-only">{{ locale }}</span>
        </button>
      </template>
    </div>
    <!-- current -->
    <button
      :tabindex="langIndex"
      aria-controls="switch-lang"
      :aria-expanded="lang.isOpen ? 'true' : 'false'"
      :aria-labelledby="'current-lang'"
      @click="lang.isOpen = lang.isOpen ? false : true"
      class="lang-switch-item"
    >
      <span id="current-lang" class="sr-only">{{ $i18n.locale }}</span>
      <span
        role="img"
        aria-hidden="true"
        id="switch-lang-text"
        :class="[`fi fi-${$i18n.locale}`]"
      ></span>
    </button>
    <!-- end current -->
  </div>
</template>
