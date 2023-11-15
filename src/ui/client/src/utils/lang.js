import { createI18n } from "vue-i18n";

import fr from "@lang/fr.json" assert { type: "json" };
import en from "@lang/en.json" assert { type: "json" };

function getAllLang() {
  return { fr: fr, en: en };
}

function getAllLangCurrPage(pagesArr) {
  const langs = getAllLang();
  // for each lang
  for (const [key, value] of Object.entries(langs)) {
    console.log(key);
    const lang = langs[key];
    const data = {};
    pagesArr.forEach((page) => {
      data[page] = value[page];
    });
    langs[key] = data;
  }
  console.log(langs);
  return langs;
}

export function getI18n(pagesArr = []) {
  const messages =
    pagesArr.length > 0 ? getAllLangCurrPage(pagesArr) : getAllLang();

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
