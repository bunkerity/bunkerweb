"use strict";
Object.defineProperty(exports, "__esModule", {
    value: true
});
const _setupTrackingContext = /*#__PURE__*/ _interopRequireDefault(require("./lib/setupTrackingContext"));
const _processTailwindFeatures = /*#__PURE__*/ _interopRequireDefault(require("./processTailwindFeatures"));
const _sharedState = require("./lib/sharedState");
function _interopRequireDefault(obj) {
    return obj && obj.__esModule ? obj : {
        default: obj
    };
}
module.exports = function tailwindcss(configOrPath) {
    return {
        postcssPlugin: "tailwindcss",
        plugins: [
            _sharedState.env.DEBUG && function(root) {
                console.log("\n");
                console.time("JIT TOTAL");
                return root;
            },
            function(root, result) {
                let context = (0, _setupTrackingContext.default)(configOrPath);
                if (root.type === "document") {
                    let roots = root.nodes.filter((node)=>node.type === "root");
                    for (const root1 of roots){
                        if (root1.type === "root") {
                            (0, _processTailwindFeatures.default)(context)(root1, result);
                        }
                    }
                    return;
                }
                (0, _processTailwindFeatures.default)(context)(root, result);
            },
            _sharedState.env.DEBUG && function(root) {
                console.timeEnd("JIT TOTAL");
                console.log("\n");
                return root;
            }, 
        ].filter(Boolean)
    };
};
module.exports.postcss = true;
