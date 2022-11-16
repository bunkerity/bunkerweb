"use strict";
Object.defineProperty(exports, "__esModule", {
    value: true
});
Object.defineProperty(exports, "splitAtTopLevelOnly", {
    enumerable: true,
    get: ()=>splitAtTopLevelOnly
});
const _regex = /*#__PURE__*/ _interopRequireWildcard(require("../lib/regex"));
function _getRequireWildcardCache(nodeInterop) {
    if (typeof WeakMap !== "function") return null;
    var cacheBabelInterop = new WeakMap();
    var cacheNodeInterop = new WeakMap();
    return (_getRequireWildcardCache = function(nodeInterop) {
        return nodeInterop ? cacheNodeInterop : cacheBabelInterop;
    })(nodeInterop);
}
function _interopRequireWildcard(obj, nodeInterop) {
    if (!nodeInterop && obj && obj.__esModule) {
        return obj;
    }
    if (obj === null || typeof obj !== "object" && typeof obj !== "function") {
        return {
            default: obj
        };
    }
    var cache = _getRequireWildcardCache(nodeInterop);
    if (cache && cache.has(obj)) {
        return cache.get(obj);
    }
    var newObj = {};
    var hasPropertyDescriptor = Object.defineProperty && Object.getOwnPropertyDescriptor;
    for(var key in obj){
        if (key !== "default" && Object.prototype.hasOwnProperty.call(obj, key)) {
            var desc = hasPropertyDescriptor ? Object.getOwnPropertyDescriptor(obj, key) : null;
            if (desc && (desc.get || desc.set)) {
                Object.defineProperty(newObj, key, desc);
            } else {
                newObj[key] = obj[key];
            }
        }
    }
    newObj.default = obj;
    if (cache) {
        cache.set(obj, newObj);
    }
    return newObj;
}
function* splitAtTopLevelOnly(input, separator) {
    let SPECIALS = new RegExp(`[(){}\\[\\]${_regex.escape(separator)}]`, "g");
    let depth = 0;
    let lastIndex = 0;
    let found = false;
    let separatorIndex = 0;
    let separatorStart = 0;
    let separatorLength = separator.length;
    // Find all paren-like things & character
    // And only split on commas if they're top-level
    for (let match of input.matchAll(SPECIALS)){
        let matchesSeparator = match[0] === separator[separatorIndex];
        let atEndOfSeparator = separatorIndex === separatorLength - 1;
        let matchesFullSeparator = matchesSeparator && atEndOfSeparator;
        if (match[0] === "(") depth++;
        if (match[0] === ")") depth--;
        if (match[0] === "[") depth++;
        if (match[0] === "]") depth--;
        if (match[0] === "{") depth++;
        if (match[0] === "}") depth--;
        if (matchesSeparator && depth === 0) {
            if (separatorStart === 0) {
                separatorStart = match.index;
            }
            separatorIndex++;
        }
        if (matchesFullSeparator && depth === 0) {
            found = true;
            yield input.substring(lastIndex, separatorStart);
            lastIndex = separatorStart + separatorLength;
        }
        if (separatorIndex === separatorLength) {
            separatorIndex = 0;
            separatorStart = 0;
        }
    }
    // Provide the last segment of the string if available
    // Otherwise the whole string since no `char`s were found
    // This mirrors the behavior of string.split()
    if (found) {
        yield input.substring(lastIndex);
    } else {
        yield input;
    }
}
