"use strict";
Object.defineProperty(exports, "__esModule", {
    value: true
});
Object.defineProperty(exports, "default", {
    enumerable: true,
    get: ()=>collapseAdjacentRules
});
let comparisonMap = {
    atrule: [
        "name",
        "params"
    ],
    rule: [
        "selector"
    ]
};
let types = new Set(Object.keys(comparisonMap));
function collapseAdjacentRules() {
    function collapseRulesIn(root) {
        let currentRule = null;
        root.each((node)=>{
            if (!types.has(node.type)) {
                currentRule = null;
                return;
            }
            if (currentRule === null) {
                currentRule = node;
                return;
            }
            let properties = comparisonMap[node.type];
            var _property, _property1;
            if (node.type === "atrule" && node.name === "font-face") {
                currentRule = node;
            } else if (properties.every((property)=>((_property = node[property]) !== null && _property !== void 0 ? _property : "").replace(/\s+/g, " ") === ((_property1 = currentRule[property]) !== null && _property1 !== void 0 ? _property1 : "").replace(/\s+/g, " "))) {
                // An AtRule may not have children (for example if we encounter duplicate @import url(…) rules)
                if (node.nodes) {
                    currentRule.append(node.nodes);
                }
                node.remove();
            } else {
                currentRule = node;
            }
        });
        // After we've collapsed adjacent rules & at-rules, we need to collapse
        // adjacent rules & at-rules that are children of at-rules.
        // We do not care about nesting rules because Tailwind CSS
        // explicitly does not handle rule nesting on its own as
        // the user is expected to use a nesting plugin
        root.each((node)=>{
            if (node.type === "atrule") {
                collapseRulesIn(node);
            }
        });
    }
    return (root)=>{
        collapseRulesIn(root);
    };
}
