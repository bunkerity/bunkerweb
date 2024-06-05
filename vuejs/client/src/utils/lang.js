import { createI18n } from "vue-i18n";
import en from "@lang/en.json" assert { type: "json" };
import fr from "@lang/fr.json" assert { type: "json" };

/**
  @name lang.js
  @description This file contains utils to manage the language of the application.
  This is here that we retrieve json files to add translations.
  This lang.js works with vue-i18n.
  We need to instanciate the i18n object in the main file of the application inside /pages.
*/

const availablesLangs = ["en", "fr"];

function getAllLang() {
  return { en: en, fr: fr };
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
    fallbackWarn: false,
    missingWarn: false,
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
      navigator.languages[0].split("-")[0].toLowerCase()
    ) !== -1
  ) {
    return navigator.languages[0].split("-")[0].toLowerCase();
  }

  return "en";
}
