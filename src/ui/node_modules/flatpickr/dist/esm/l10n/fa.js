var fp = typeof window !== "undefined" && window.flatpickr !== undefined
    ? window.flatpickr
    : {
        l10ns: {},
    };
export var Persian = {
    weekdays: {
        shorthand: ["یک", "دو", "سه", "چهار", "پنج", "جمعه", "شنبه"],
        longhand: [
            "یک‌شنبه",
            "دوشنبه",
            "سه‌شنبه",
            "چهارشنبه",
            "پنچ‌شنبه",
            "جمعه",
            "شنبه",
        ],
    },
    months: {
        shorthand: [
            "ژانویه",
            "فوریه",
            "مارس",
            "آوریل",
            "مه",
            "ژوئن",
            "ژوئیه",
            "اوت",
            "سپتامبر",
            "اکتبر",
            "نوامبر",
            "دسامبر",
        ],
        longhand: [
            "ژانویه",
            "فوریه",
            "مارس",
            "آوریل",
            "مه",
            "ژوئن",
            "ژوئیه",
            "اوت",
            "سپتامبر",
            "اکتبر",
            "نوامبر",
            "دسامبر",
        ],
    },
    firstDayOfWeek: 6,
    ordinal: function () {
        return "";
    },
};
fp.l10ns.fa = Persian;
export default fp.l10ns;
