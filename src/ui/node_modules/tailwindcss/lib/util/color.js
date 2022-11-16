"use strict";
Object.defineProperty(exports, "__esModule", {
    value: true
});
function _export(target, all) {
    for(var name in all)Object.defineProperty(target, name, {
        enumerable: true,
        get: all[name]
    });
}
_export(exports, {
    parseColor: ()=>parseColor,
    formatColor: ()=>formatColor
});
const _colorName = /*#__PURE__*/ _interopRequireDefault(require("color-name"));
function _interopRequireDefault(obj) {
    return obj && obj.__esModule ? obj : {
        default: obj
    };
}
let HEX = /^#([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})?$/i;
let SHORT_HEX = /^#([a-f\d])([a-f\d])([a-f\d])([a-f\d])?$/i;
let VALUE = /(?:\d+|\d*\.\d+)%?/;
let SEP = /(?:\s*,\s*|\s+)/;
let ALPHA_SEP = /\s*[,/]\s*/;
let CUSTOM_PROPERTY = /var\(--(?:[^ )]*?)\)/;
let RGB = new RegExp(`^(rgb)a?\\(\\s*(${VALUE.source}|${CUSTOM_PROPERTY.source})(?:${SEP.source}(${VALUE.source}|${CUSTOM_PROPERTY.source}))?(?:${SEP.source}(${VALUE.source}|${CUSTOM_PROPERTY.source}))?(?:${ALPHA_SEP.source}(${VALUE.source}|${CUSTOM_PROPERTY.source}))?\\s*\\)$`);
let HSL = new RegExp(`^(hsl)a?\\(\\s*((?:${VALUE.source})(?:deg|rad|grad|turn)?|${CUSTOM_PROPERTY.source})(?:${SEP.source}(${VALUE.source}|${CUSTOM_PROPERTY.source}))?(?:${SEP.source}(${VALUE.source}|${CUSTOM_PROPERTY.source}))?(?:${ALPHA_SEP.source}(${VALUE.source}|${CUSTOM_PROPERTY.source}))?\\s*\\)$`);
function parseColor(value, { loose =false  } = {}) {
    var ref, ref1;
    if (typeof value !== "string") {
        return null;
    }
    value = value.trim();
    if (value === "transparent") {
        return {
            mode: "rgb",
            color: [
                "0",
                "0",
                "0"
            ],
            alpha: "0"
        };
    }
    if (value in _colorName.default) {
        return {
            mode: "rgb",
            color: _colorName.default[value].map((v)=>v.toString())
        };
    }
    let hex = value.replace(SHORT_HEX, (_, r, g, b, a)=>[
            "#",
            r,
            r,
            g,
            g,
            b,
            b,
            a ? a + a : ""
        ].join("")).match(HEX);
    if (hex !== null) {
        return {
            mode: "rgb",
            color: [
                parseInt(hex[1], 16),
                parseInt(hex[2], 16),
                parseInt(hex[3], 16)
            ].map((v)=>v.toString()),
            alpha: hex[4] ? (parseInt(hex[4], 16) / 255).toString() : undefined
        };
    }
    var ref2;
    let match = (ref2 = value.match(RGB)) !== null && ref2 !== void 0 ? ref2 : value.match(HSL);
    if (match === null) {
        return null;
    }
    let color = [
        match[2],
        match[3],
        match[4]
    ].filter(Boolean).map((v)=>v.toString());
    if (!loose && color.length !== 3) {
        return null;
    }
    if (color.length < 3 && !color.some((part)=>/^var\(.*?\)$/.test(part))) {
        return null;
    }
    return {
        mode: match[1],
        color,
        alpha: (ref = match[5]) === null || ref === void 0 ? void 0 : (ref1 = ref.toString) === null || ref1 === void 0 ? void 0 : ref1.call(ref)
    };
}
function formatColor({ mode , color , alpha  }) {
    let hasAlpha = alpha !== undefined;
    return `${mode}(${color.join(" ")}${hasAlpha ? ` / ${alpha}` : ""})`;
}
