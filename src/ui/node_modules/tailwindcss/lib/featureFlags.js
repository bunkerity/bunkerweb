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
    flagEnabled: ()=>flagEnabled,
    issueFlagNotices: ()=>issueFlagNotices,
    default: ()=>_default
});
const _picocolors = /*#__PURE__*/ _interopRequireDefault(require("picocolors"));
const _log = /*#__PURE__*/ _interopRequireDefault(require("./util/log"));
function _interopRequireDefault(obj) {
    return obj && obj.__esModule ? obj : {
        default: obj
    };
}
let defaults = {
    optimizeUniversalDefaults: false
};
let featureFlags = {
    future: [
        "hoverOnlyWhenSupported",
        "respectDefaultRingColorOpacity"
    ],
    experimental: [
        "optimizeUniversalDefaults",
        "matchVariant" /* , 'variantGrouping' */ 
    ]
};
function flagEnabled(config, flag) {
    if (featureFlags.future.includes(flag)) {
        var ref;
        var ref1, ref2;
        return config.future === "all" || ((ref2 = (ref1 = config === null || config === void 0 ? void 0 : (ref = config.future) === null || ref === void 0 ? void 0 : ref[flag]) !== null && ref1 !== void 0 ? ref1 : defaults[flag]) !== null && ref2 !== void 0 ? ref2 : false);
    }
    if (featureFlags.experimental.includes(flag)) {
        var ref3;
        var ref4, ref5;
        return config.experimental === "all" || ((ref5 = (ref4 = config === null || config === void 0 ? void 0 : (ref3 = config.experimental) === null || ref3 === void 0 ? void 0 : ref3[flag]) !== null && ref4 !== void 0 ? ref4 : defaults[flag]) !== null && ref5 !== void 0 ? ref5 : false);
    }
    return false;
}
function experimentalFlagsEnabled(config) {
    if (config.experimental === "all") {
        return featureFlags.experimental;
    }
    var ref;
    return Object.keys((ref = config === null || config === void 0 ? void 0 : config.experimental) !== null && ref !== void 0 ? ref : {}).filter((flag)=>featureFlags.experimental.includes(flag) && config.experimental[flag]);
}
function issueFlagNotices(config) {
    if (process.env.JEST_WORKER_ID !== undefined) {
        return;
    }
    if (experimentalFlagsEnabled(config).length > 0) {
        let changes = experimentalFlagsEnabled(config).map((s)=>_picocolors.default.yellow(s)).join(", ");
        _log.default.warn("experimental-flags-enabled", [
            `You have enabled experimental features: ${changes}`,
            "Experimental features in Tailwind CSS are not covered by semver, may introduce breaking changes, and can change at any time.", 
        ]);
    }
}
const _default = featureFlags;
