(function (global, factory) {
  typeof exports === 'object' && typeof module !== 'undefined' ? factory(exports) :
  typeof define === 'function' && define.amd ? define(['exports'], factory) :
  (global = typeof globalThis !== 'undefined' ? globalThis : global || self, factory(global.sv = {}));
}(this, (function (exports) { 'use strict';

  var fp = typeof window !== "undefined" && window.flatpickr !== undefined
      ? window.flatpickr
      : {
          l10ns: {},
      };
  var Swedish = {
      firstDayOfWeek: 1,
      weekAbbreviation: "v",
      weekdays: {
          shorthand: ["sön", "mån", "tis", "ons", "tor", "fre", "lör"],
          longhand: [
              "söndag",
              "måndag",
              "tisdag",
              "onsdag",
              "torsdag",
              "fredag",
              "lördag",
          ],
      },
      months: {
          shorthand: [
              "jan",
              "feb",
              "mar",
              "apr",
              "maj",
              "jun",
              "jul",
              "aug",
              "sep",
              "okt",
              "nov",
              "dec",
          ],
          longhand: [
              "januari",
              "februari",
              "mars",
              "april",
              "maj",
              "juni",
              "juli",
              "augusti",
              "september",
              "oktober",
              "november",
              "december",
          ],
      },
      rangeSeparator: " till ",
      time_24hr: true,
      ordinal: function () {
          return ".";
      },
  };
  fp.l10ns.sv = Swedish;
  var sv = fp.l10ns;

  exports.Swedish = Swedish;
  exports.default = sv;

  Object.defineProperty(exports, '__esModule', { value: true });

})));
