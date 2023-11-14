import { createI18n } from "vue-i18n";

import fr from "@lang/fr.json" assert { type: "json" };
import en from "@lang/en.json" assert { type: "json" };

function getAllLang() {
  return { fr: fr, en: en };
}

function getAllLangCurrPage(page) {
  const langs = getAllLang();
  for (const [key, value] of Object.entries(langs)) {
    langs[key] = value[page];
    console.log(`${key}: ${value}`);
  }
  return langs;
}

export function getI18n(page = false) {
  const messages = page ? getAllLangCurrPage(page) : getAllLang();

  const i18n = createI18n({
    legacy: false,
    locale: getLocalLang(), // set locale
    messages, // set locale messages
    availableLocales: ["en", "fr"],
  });

  return i18n;
}

export function getLocalLang() {
  // get store lang, or local, or default

  if (sessionStorage.getItem("lang")) {
    return sessionStorage.getItem("lang");
  }

  if (navigator.language) {
    return navigator.language.split("-")[0].toLowerCase();
  }

  if (navigator.languages && navigator.languages > 0) {
    return navigator.languages[0].split("-")[0].toLowerCase();
  }

  return "en";
}
