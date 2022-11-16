(function (global, factory) {
  typeof exports === 'object' && typeof module !== 'undefined' ? factory(exports) :
  typeof define === 'function' && define.amd ? define(['exports'], factory) :
  (global = typeof globalThis !== 'undefined' ? globalThis : global || self, factory(global.ckb = {}));
}(this, (function (exports) { 'use strict';

  var fp = typeof window !== "undefined" && window.flatpickr !== undefined
      ? window.flatpickr
      : {
          l10ns: {},
      };
  var Kurdish = {
      weekdays: {
          shorthand: [
              "یەکشەممە",
              "دووشەممە",
              "سێشەممە",
              "چوارشەممە",
              "پێنجشەممە",
              "هەینی",
              "شەممە",
          ],
          longhand: [
              "یەکشەممە",
              "دووشەممە",
              "سێشەممە",
              "چوارشەممە",
              "پێنجشەممە",
              "هەینی",
              "شەممە",
          ],
      },
      months: {
          shorthand: [
              "ڕێبەندان",
              "ڕەشەمە",
              "نەورۆز",
              "گوڵان",
              "جۆزەردان",
              "پووشپەڕ",
              "گەلاوێژ",
              "خەرمانان",
              "ڕەزبەر",
              "گەڵاڕێزان",
              "سەرماوەز",
              "بەفرانبار",
          ],
          longhand: [
              "ڕێبەندان",
              "ڕەشەمە",
              "نەورۆز",
              "گوڵان",
              "جۆزەردان",
              "پووشپەڕ",
              "گەلاوێژ",
              "خەرمانان",
              "ڕەزبەر",
              "گەڵاڕێزان",
              "سەرماوەز",
              "بەفرانبار",
          ],
      },
      firstDayOfWeek: 6,
      ordinal: function () {
          return "";
      },
  };
  fp.l10ns.ckb = Kurdish;
  var ckb = fp.l10ns;

  exports.Kurdish = Kurdish;
  exports.default = ckb;

  Object.defineProperty(exports, '__esModule', { value: true });

})));
