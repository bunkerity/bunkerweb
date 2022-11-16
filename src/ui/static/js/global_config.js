import { Checkbox, Popover, Select, Tabs, FormatValue } from "./utils.js";

const setCheckbox = new Checkbox("[global-config-form]");
const setSelect = new Select("[global-config-form]", "global-config");
const setPopover = new Popover("main", "global-config");
const setTabs = new Tabs("[global-config-tabs]", "global-config");
const format = new FormatValue();
