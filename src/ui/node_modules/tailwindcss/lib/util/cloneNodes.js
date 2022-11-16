"use strict";
Object.defineProperty(exports, "__esModule", {
    value: true
});
Object.defineProperty(exports, "default", {
    enumerable: true,
    get: ()=>cloneNodes
});
function cloneNodes(nodes, source = undefined, raws = undefined) {
    return nodes.map((node)=>{
        var ref;
        let cloned = node.clone();
        // We always want override the source map
        // except when explicitly told not to
        let shouldOverwriteSource = ((ref = node.raws.tailwind) === null || ref === void 0 ? void 0 : ref.preserveSource) !== true || !cloned.source;
        if (source !== undefined && shouldOverwriteSource) {
            cloned.source = source;
            if ("walk" in cloned) {
                cloned.walk((child)=>{
                    child.source = source;
                });
            }
        }
        if (raws !== undefined) {
            cloned.raws.tailwind = {
                ...cloned.raws.tailwind,
                ...raws
            };
        }
        return cloned;
    });
}
