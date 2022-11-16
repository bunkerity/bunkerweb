export var pad = function (number, length) {
    if (length === void 0) { length = 2; }
    return ("000" + number).slice(length * -1);
};
export var int = function (bool) { return (bool === true ? 1 : 0); };
export function debounce(fn, wait) {
    var t;
    return function () {
        var _this = this;
        var args = arguments;
        clearTimeout(t);
        t = setTimeout(function () { return fn.apply(_this, args); }, wait);
    };
}
export var arrayify = function (obj) {
    return obj instanceof Array ? obj : [obj];
};
