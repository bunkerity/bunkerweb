import './style.less';
export interface JSONFormatterConfiguration {
    hoverPreviewEnabled?: boolean;
    hoverPreviewArrayCount?: number;
    hoverPreviewFieldCount?: number;
    animateOpen?: boolean;
    animateClose?: boolean;
    theme?: string;
    useToJSON?: boolean;
    sortPropertiesBy?: (a: string, b: string) => number;
}
/**
 * @class JSONFormatter
 *
 * JSONFormatter allows you to render JSON objects in HTML with a
 * **collapsible** navigation.
*/
export default class JSONFormatter {
    json: any;
    private open;
    private config;
    private key?;
    private _isOpen;
    private element;
    /**
     * @param {object} json The JSON object you want to render. It has to be an
     * object or array. Do NOT pass raw JSON string.
     *
     * @param {number} [open=1] his number indicates up to how many levels the
     * rendered tree should expand. Set it to `0` to make the whole tree collapsed
     * or set it to `Infinity` to expand the tree deeply
     *
     * @param {object} [config=defaultConfig] -
     *  defaultConfig = {
     *   hoverPreviewEnabled: false,
     *   hoverPreviewArrayCount: 100,
     *   hoverPreviewFieldCount: 5
     * }
     *
     * Available configurations:
     *  #####Hover Preview
     * * `hoverPreviewEnabled`:  enable preview on hover
     * * `hoverPreviewArrayCount`: number of array items to show in preview Any
     *    array larger than this number will be shown as `Array[XXX]` where `XXX`
     *    is length of the array.
     * * `hoverPreviewFieldCount`: number of object properties to show for object
     *   preview. Any object with more properties that thin number will be
     *   truncated.
     *
     * @param {string} [key=undefined] The key that this object in it's parent
     * context
    */
    constructor(json: any, open?: number, config?: JSONFormatterConfiguration, key?: string);
    private get isOpen();
    private set isOpen(value);
    private get isDate();
    private get isUrl();
    private get isArray();
    private get isObject();
    private get isEmptyObject();
    private get isEmpty();
    private get useToJSON();
    private get hasKey();
    private get constructorName();
    private get type();
    private get keys();
    /**
     * Toggles `isOpen` state
     *
    */
    toggleOpen(): void;
    /**
    * Open all children up to a certain depth.
    * Allows actions such as expand all/collapse all
    *
    */
    openAtDepth(depth?: number): void;
    /**
     * Generates inline preview
     *
     * @returns {string}
    */
    getInlinepreview(): string;
    /**
     * Renders an HTML element and installs event listeners
     *
     * @returns {HTMLDivElement}
    */
    render(): HTMLDivElement;
    /**
     * Appends all the children to children element
     * Animated option is used when user triggers this via a click
    */
    appendChildren(animated?: boolean): void;
    /**
     * Removes all the children from children element
     * Animated option is used when user triggers this via a click
    */
    removeChildren(animated?: boolean): void;
}
