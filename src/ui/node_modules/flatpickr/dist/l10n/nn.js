(function (global, factory) {
  typeof exports === 'object' && typeof module !== 'undefined' ? factory(exports) :
  typeof define === 'function' && define.amd ? define(['exports'], factory) :
  (global = typeof globalThis !== 'undefined' ? globalThis : global || self, factory(global.nn = {}));
}(this, (function (exports) { 'use strict';

  var fp = typeof window !== "undefined" && window.flatpickr !== undefined
      ? window.flatpickr
      : {
          l10ns: {},
      };
  var NorwegianNynorsk = {
      weekdays: {
          shorthand: ["Sø.", "Må.", "Ty.", "On.", "To.", "Fr.", "La."],
          longhand: [
              "Søndag",
              "Måndag",
              "Tysdag",
              "Onsdag",
              "Torsdag",
              "Fredag",
              "Laurdag",
          ],
      },
      months: {
          shorthand: [
              "Jan",
              "Feb",
              "Mars",
              "Apr",
              "Mai",
              "Juni",
              "Juli",
              "Aug",
              "Sep",
              "Okt",
              "Nov",
              "Des",
          ],
          longhand: [
              "Januar",
              "Februar",
              "Mars",
              "April",
              "Mai",
              "Juni",
              "Juli",
              "August",
              "September",
              "Oktober",
              "November",
              "Desember",
          ],
      },
      firstDayOfWeek: 1,
      rangeSeparator: " til ",
      weekAbbreviation: "Veke",
      scrollTitle: "Scroll for å endre",
      toggleTitle: "Klikk for å veksle",
      time_24hr: true,
      ordinal: function () {
          return ".";
      },
  };
  fp.l10ns.nn = NorwegianNynorsk;
  var nn = fp.l10ns;

  exports.NorwegianNynorsk = NorwegianNynorsk;
  exports.default = nn;

  Object.defineProperty(exports, '__esModule', { value: true });

})));
