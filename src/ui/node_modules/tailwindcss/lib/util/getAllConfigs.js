"use strict";
Object.defineProperty(exports, "__esModule", {
    value: true
});
Object.defineProperty(exports, "default", {
    enumerable: true,
    get: ()=>getAllConfigs
});
const _defaultConfigStubJs = /*#__PURE__*/ _interopRequireDefault(require("../../stubs/defaultConfig.stub.js"));
const _featureFlags = require("../featureFlags");
function _interopRequireDefault(obj) {
    return obj && obj.__esModule ? obj : {
        default: obj
    };
}
function getAllConfigs(config) {
    var ref;
    const configs = ((ref = config === null || config === void 0 ? void 0 : config.presets) !== null && ref !== void 0 ? ref : [
        _defaultConfigStubJs.default
    ]).slice().reverse().flatMap((preset)=>getAllConfigs(preset instanceof Function ? preset() : preset));
    const features = {
        // Add experimental configs here...
        respectDefaultRingColorOpacity: {
            theme: {
                ringColor: {
                    DEFAULT: "#3b82f67f"
                }
            }
        }
    };
    const experimentals = Object.keys(features).filter((feature)=>(0, _featureFlags.flagEnabled)(config, feature)).map((feature)=>features[feature]);
    return [
        config,
        ...experimentals,
        ...configs
    ];
}
