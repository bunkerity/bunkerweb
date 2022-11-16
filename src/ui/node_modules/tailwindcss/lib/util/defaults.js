"use strict";
Object.defineProperty(exports, "__esModule", {
    value: true
});
Object.defineProperty(exports, "defaults", {
    enumerable: true,
    get: ()=>defaults
});
function defaults(target, ...sources) {
    for (let source of sources){
        for(let k in source){
            var ref;
            if (!(target === null || target === void 0 ? void 0 : (ref = target.hasOwnProperty) === null || ref === void 0 ? void 0 : ref.call(target, k))) {
                target[k] = source[k];
            }
        }
        for (let k1 of Object.getOwnPropertySymbols(source)){
            var ref1;
            if (!(target === null || target === void 0 ? void 0 : (ref1 = target.hasOwnProperty) === null || ref1 === void 0 ? void 0 : ref1.call(target, k1))) {
                target[k1] = source[k1];
            }
        }
    }
    return target;
}
