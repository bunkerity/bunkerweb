import { createI18n } from "vue-i18n";

import en from "@lang/en.json" assert { type: "json" };
import fr from "@lang/fr.json" assert { type: "json" };

/**
 *  @name utils/lang.js
 *  @description This file contains utils to manage the language of the application.
 *  This is here that we retrieve json files to add translations.
 *  This lang.js works with vue-i18n.
 *  We need to instanciate the i18n object in the main file of the application inside /pages.
 */

const availablesLangs = ["en", "fr"];

/**
 *  @name getAllLang
 *  @description  Return all the languages json data available in the application.
 *  @returns {object} - Object with all the languages data.
 */
function getAllLang() {
  return { en: en, fr: fr };
}

/**
 *  @name getAllLangCurrPage
 *  @description   Filter the needed translations for the current page in order to reduce the size of the i18n object.
 *  @example ["dashboard", "settings", "profile"]
 *  @param {array} pagesArr -  Array of strings with the names of the prefixes of the translations needed.
 *  @returns {object} - Object with the languages data for the current page.
 */
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

/**
 *  @name getI18n
 *  @description  Return the i18n object with the translations needed for the current page for all available languages.
 *  @example ["dashboard", "settings", "profile"]
 *  @param {array} pagesArr -  Array of strings with the names of the prefixes of the translations needed.
 *  @returns {object} - Object with the i18n object.
 */
function getI18n(pagesArr = []) {
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
    warnHtmlMessage: false,
    silentTranslationWarn: false,
    missingWarn: false,
    WarnHtmlInMessageLevel: "off",
    messageCompiler: true,
  });

  return i18n;
}

/**
 *  @name getLocalLang
 *  @description  This will return the user langage checking the store, the browser, or the default lang.
 *  @returns {string} - The user langage.
 */
function getLocalLang() {
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

export { getI18n, getLocalLang };
