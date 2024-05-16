import { createI18n } from "vue-i18n";

import fr from "@lang/fr.json" assert { type: "json" };
import en from "@lang/en.json" assert { type: "json" };

const availablesLangs = ["en", "fr"];

function getAllLang() {
  return { fr: fr, en: en };
}

function getAllLangCurrPage(pagesArr) {
  const langs = getAllLang();
  // for each lang
  for (const [langName, langVal] of Object.entries(langs)) {
    const data = {};
    for (const [key, value] of Object.entries(langVal)) {
      pagesArr.forEach((name) => {
        if (key.startsWith(`${name}_`)) data[key] = value;
      });
    }
    langs[langName] = data;
  }
  return langs;
}

export function getI18n(pagesArr = []) {
  const messages =
    pagesArr.length > 0 ? getAllLangCurrPage(pagesArr) : getAllLang();

  const i18n = createI18n({
    legacy: false,
    locale: getLocalLang(), // set locale
    fallbackLocale: "en",
    messages, // set locale messages
    availableLocales: availablesLangs,
  });

  return i18n;
}

export function getLocalLang() {
  // get store lang, or local, or default
  if (
    sessionStorage.getItem("lang") &&
    availablesLangs.indexOf(sessionStorage.getItem("lang")) !== -1
  ) {
    return sessionStorage.getItem("lang");
  }

  if (
    navigator.language &&
    availablesLangs.indexOf(navigator.language.split("-")[0].toLowerCase()) !==
      -1
  ) {
    return navigator.language.split("-")[0].toLowerCase();
  }

  if (
    navigator.languages &&
    navigator.languages > 0 &&
    availablesLangs.indexOf(
      navigator.languages[0].split("-")[0].toLowerCase(),
    ) !== -1
  ) {
    return navigator.languages[0].split("-")[0].toLowerCase();
  }

  return "en";
}
