"use strict";
Object.defineProperty(exports, "__esModule", {
    value: true
});
exports.default = _createSuper;
var _isNativeReflectConstruct = _interopRequireDefault(require("./_is_native_reflect_construct"));
var _getPrototypeOf = _interopRequireDefault(require("./_get_prototype_of"));
var _possibleConstructorReturn = _interopRequireDefault(require("./_possible_constructor_return"));
function _interopRequireDefault(obj) {
    return obj && obj.__esModule ? obj : {
        default: obj
    };
}
function _createSuper(Derived) {
    var hasNativeReflectConstruct = (0, _isNativeReflectConstruct).default();
    return function _createSuperInternal() {
        var Super = (0, _getPrototypeOf).default(Derived), result;
        if (hasNativeReflectConstruct) {
            var NewTarget = (0, _getPrototypeOf).default(this).constructor;
            result = Reflect.construct(Super, arguments, NewTarget);
        } else {
            result = Super.apply(this, arguments);
        }
        return (0, _possibleConstructorReturn).default(this, result);
    };
}
