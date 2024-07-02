# UI Components

This page contains all the UI components used in the application.

##  Builder

### Bans.vue

This component is lightweight builder containing only the necessary components to create the bans page.

#### Parameters

*   `builder` **[array][4]** Array of containers and widgets

#### Examples

```javascript
[
{
type: "card",
gridLayoutClass: "transparent",
widgets: [{ type: "MessageUnmatch", data: { text: "bans_not_found" } }],
},
];
```

### Collection.vue

This component is a builder containing all collection of widgets / containers / components  to create a complete page.
We have to define each container and each widget inside it.
This is an abstract component that will be used to create any kind of page content (base dashboard elements like menu and news excluded)

#### Parameters

*   `builder` **[array][4]** Array of containers and widgets

#### Examples

```javascript
[
{
// this can be a "card", "modal", "table"... etc
"type": "card",  

// container custom key
"title" : "My awesome card", 

// additionnal tailwind css class
"containerClass": "", 

// We can define the top level grid system (GridLayout.vue)
"containerColumns" : {"pc": 12, "tablet": 12, "mobile": 12},

// Each widget need a name (here type) and associated data
// We need to send specific data for each widget typ
widgets: [
{
type : "Checkbox", 
data : {containerClass : "", columns : {"pc": 6, "tablet": 12, "mobile": 12}, id:"test-check", value: "yes", label: "Checkbox", name: "checkbox", required: true, version: "v1.0.0", hideLabel: false, headerClass: "text-red-500" }
}, {    
type : "Select",   
data : {containerClass : "", columns : {"pc": 6, "tablet": 12, "mobile": 12}, id: 'test-select', value: 'yes', values: ['yes', 'no'], name: 'test-select', disabled: false, required: true, label: 'Test select', tabId: '1',}
}
]
}
]
```

### GlobalConfig.vue

This component is lightweight builder containing only the necessary components to create the instances page.

#### Parameters

*   `builder` **[array][4]** Array of containers and widgets

#### Examples

```javascript
[
{
type: "card",
containerColumns: { pc: 12, tablet: 12, mobile: 12 },
widgets: [
{
type: "Title",
data : {
title: "dashboard_global_config",
type: "card"
},
},
{
type: "Templates",
data: {
title: "home_version",
subtitle: "home_all_features_available" if is_pro_version else "home_upgrade_pro",
subtitleColor: "success" is is_pro_version else "warning",
stat: "home_pro" if is_pro_version else "home_free",
iconName: "crown" if is_pro_version else "core",
},
},
],
},
];
```

### Home.vue

This component is lightweight builder containing only the necessary components to create the home page.

#### Parameters

*   `builder` **[array][4]** Array of containers and widgets

#### Examples

```javascript
[
{
type: "card",
link : "https://panel.bunkerweb.io/?utm_campaign=self&utm_source=ui"
containerColumns: { pc: 4, tablet: 6, mobile: 12 },
widgets: [
{
type: "Stat",
data: {
title: "home_version",
subtitle: "home_all_features_available" if is_pro_version else "home_upgrade_pro",
subtitleColor: "success" is is_pro_version else "warning",
stat: "home_pro" if is_pro_version else "home_free",
iconName: "crown" if is_pro_version else "core",
},
},
],
},
]
```

### Instances.vue

This component is lightweight builder containing only the necessary components to create the instances page.

#### Parameters

*   `builder` **[array][4]** Array of containers and widgets

#### Examples

```javascript
[
{
type: "Instance",
data: {
details: [
{ key: <instances_hostname="hostname">, value: "www.example.com" },
{ key: <instances_method="method">, value: <dashboard_ui> or <dashboard_scheduler>...},
{ key: <instances_port="port">, value: "1084" },
{ key: <instances_status="status">, value: <instances_active="active"> or <instances_inactive="inactive"> },
],
status: "success",
title: "www.example.com",
buttons: [
{
text: <action_*>,
color: "edit",
size: "normal",
},
],
},
},
];
```

### Jobs.vue

This component is lightweight builder containing only the necessary components to create the jobs page.

#### Parameters

*   `builder` **[array][4]** Array of containers and widgets

#### Examples

```javascript
[
{
"type": "card",
"containerColumns": {
"pc": 4,
"tablet": 6,
"mobile": 12
},
"widgets": [
{
"type": "table",
"data": {
"title": "jobs_table_title",
"minWidth": "lg",
"header": [
"jobs_table_name",
"jobs_table_plugin_id",
"jobs_table_interval",
"jobs_table_last_run",
"jobs_table_success",
"jobs_table_last_run_date",
"jobs_table_cache"
],
"positions": [
2,
2,
1,
1,
1,
3,
2
],
"items": [
[
{
"name": "anonymous-report",
"type": "Text",
"data": {
"text": "anonymous-report"
}
},
],
]
}
}
]
}
]
```

### PLugin.vue

This component is lightweight builder containing only the necessary components to create the plugins page.

#### Parameters

*   `builder` **[array][4]** Array of containers and widgets

#### Examples

```javascript
[
{
type: "card",
containerColumns: { pc: 12, tablet: 12, mobile: 12 },
widgets: [
{
type: "Title",
data : {
title: "dashboard_plugins",
type: "card"
},
},
{
type: "ListDetails",
data:   {
text: "Plugin name",
popovers: [
{
text: "This is a popover text",
iconName: "info",
},
{
text: "This is a popover text",
iconName: "info",
},
],
},
},
],
},
];
```

### Reports.vue

This component is lightweight builder containing only the necessary components to create the reports page.

#### Parameters

*   `builder` **[array][4]** Array of containers and widgets

#### Examples

```javascript
[
{
type: "card",
gridLayoutClass: "transparent",
widgets: [{ type: "MessageUnmatch", data: { text: "reports_not_found" } }],
},
];
```

##  Dashboard

### Banner.vue

This component is a banner that display news.
The banner will display news from the api if available, otherwise it will display default news.

### Feedback.vue

This component will display server feedbacks from the user.
This component is working with flash messages under the hood.
This will display an ephemeral on the bottom right of the page and a sidebar with all the feedbacks.

### Footer.vue

This component is a footer that display essential links.
You have all the links to the main website, the documentation, the privacy policy, the blog, the license and the sitemap.

### Header.vue

This component is a header displaying the current page endpoint.

### LangSwitch.vue

This component is a float element with a flag of the current language.
When clicked, it will display a list of available languages, clicking on one will change the language.
Your language isn't here ? You can contribute by following the part of the documentation about translations.

### Layout.vue

This component is a layout that wraps the main content of the dashboard.
It includes the header, the menu, the news, the language switcher, the loader, the banner and the footer.
The content part is a slot that can be filled with custom components or using the Builder.vue.

### Loader.vue

This component is a loader used to transition between pages.

### Menu.vue

This component is a menu that display essential links.
You have all the links to the main pages, the plugins pages, the social links and the logout button.

### News.vue

This component will display news from BunkerWeb blog and allow users to subscribe to the newsletter.
Case the news API is not available, it will display a message.

##  Form

### Advanced.vue

This component is used to create a complete advanced form with plugin selection.

#### Parameters

*   `template` **[object][4]** Template object with plugin and settings data.
*   `containerClass` **[string][5]** Container
*   `columns` **[object][4]** Columns object.

#### Examples

```javascript
template: [
{
columns: { pc: 6, tablet: 12, mobile: 12 },
id: "test-check",
value: "yes",
label: "Checkbox",
name: "checkbox",
required: true,
hideLabel: false,
headerClass: "text-red-500",
inpType: "checkbox",
},
{
id: "test-input",
value: "yes",
type: "text",
name: "test-input",
disabled: false,
required: true,
label: "Test input",
pattern: "(test)",
inpType: "input",
},
],
```

### Easy.vue

This component is used to create a complete easy form with plugin selection.

#### Parameters

*   `template` **[object][4]** Template object with plugin and settings data.
*   `containerClass` **[string][5]** Container
*   `columns` **[object][4]** Columns object.

#### Examples

```javascript
template: [
{
columns: { pc: 6, tablet: 12, mobile: 12 },
id: "test-check",
value: "yes",
label: "Checkbox",
name: "checkbox",
required: true,
hideLabel: false,
headerClass: "text-red-500",
inpType: "checkbox",
},
{
id: "test-input",
value: "yes",
type: "text",
name: "test-input",
disabled: false,
required: true,
label: "Test input",
pattern: "(test)",
inpType: "input",
},
],
```

### Fields.vue

This component wraps all available fields for a form.

#### Parameters

*   `setting` **[object][4]** Setting needed to render a field.

#### Examples

```javascript
{ 
columns : {"pc": 6, "tablet": 12, "mobile": 12}, 
id:"test-check", 
value: "yes", 
label: "Checkbox", 
name: "checkbox", 
required: true, 
hideLabel: false, 
inpType: "checkbox",
headerClass: "text-red-500" 
popovers : [
{
text: "This is a popover text",
iconName: "info",
},
]
}
```

### RAW\.vue

This component is used to create a complete raw form with settings as JSON format.

#### Parameters

*   `template` **[object][4]** Template object with plugin and settings data.
*   `containerClass` **[string][5]** Container
*   `columns` **[object][4]** Columns object.

#### Examples

```javascript
{
"IS_LOADING": "no",
"NGINX_PREFIX": "/etc/nginx/", 
"HTTP_PORT": "8080", 
"HTTPS_PORT": "8443", 
"MULTISITE": "yes" 
}
```

### Templates.vue

This component is used to create a complete  settings form with all modes (advanced, raw, easy).

#### Parameters

*   `templates` **[object][4]** List of advanced templates that contains settings. Must be a dict with mode as key, then the template name as key with a list of data (different for each modes).

#### Examples

```javascript
const data = {
advanced : {
default : [{SETTING_1}, {SETTING_2}...],
low : [{SETTING_1}, {SETTING_2}...],
},
easy : {
default : [...],
low : [...],
}
}
```

##  Forms

###  Error

#### Field.vue

This component is an alert type to send feedback to the user.
We can used it as a fixed alert or we can use it in a container as a list.

##### Parameters

*   `title` **[string][4]** The title of the alert. Can be a translation key or by default raw text.
*   `message` **[string][4]** The message of the alert. Can be a translation key or by default raw text.
*   `canClose` **[boolean][5]** Determine if the alert can be closed by user (add a close button), by default it is closable (optional, default `true`)
*   `id` **[string][4]**  (optional, default `` `feedback-alert-${message.substring(0,10)}` ``)
*   `isFixed` **[string][4]** Determine if the alert is fixed (visible bottom right of page) or relative (inside a container) (optional, default `false`)
*   `type` **[string][4]** The type of the alert, can be success, error, warning or info (optional, default `"info"`)
*   `delayToClose` **[number][6]** The delay to auto close alert in ms, by default always visible (optional, default `0`)
*   `tabId` **[string][4]** The tabindex of the alert (optional, default `"-1"`)

##### Examples

```javascript
{
position : "fixed",
type: "success",
title: "Success",
message: "Your action has been successfully completed",
delayToClose: 5000,
}
```

###  Feature

#### Clipboard.vue

This component can be add to some fields to allow to copy the value of the field.
Additionnal clipboardClass and copyClass can be added to fit the parent container.

##### Parameters

*   `id` **id** Unique id (optional, default `uuidv4()`)
*   `isClipboard` **isClipboard** Display a clipboard button to copy a value (optional, default `false`)
*   `valueToCopy` **valueToCopy** The value to copy (optional, default `""`)
*   `clipboadClass` **clipboadClass** Additional class for the clipboard container. Useful to fit the component in a specific container. (optional, default `""`)
*   `copyClass` **copyClass** The class of the copy message. Useful to fit the component in a specific container. (optional, default `""`)

##### Examples

```javascript
{
id: 'test-input',
isClipboard: true,
valueToCopy: 'yes',
clipboadClass: 'mx-2',
copyClass: 'mt-2',
}
```

###  Field

#### Checkbox.vue

This component is used to create a complete checkbox field input with error handling and label.
We can also add popover to display more information.
It is mainly use in forms.

##### Parameters

*   `id` **[string][4]** Unique id (optional, default `uuidv4()`)
*   `label` **[string][4]** The label of the field. Can be a translation key or by default raw text.
*   `name` **[string][4]** The name of the field. Case no label, this is the fallback. Can be a translation key or by default raw text.
*   `value` **[string][4]**&#x20;
*   `popovers` **[array][5]?** List of popovers to display more information
*   `inpType` **[string][4]** The type of the field, useful when we have multiple fields in the same container to display the right field (optional, default `"checkbox"`)
*   `disabled` **[boolean][6]**  (optional, default `false`)
*   `required` **[boolean][6]**  (optional, default `false`)
*   `columns` **[object][7]** Field has a grid system. This allow to get multiple field in the same row if needed. (optional, default `{"pc":"12","tablet":"12","mobile":"12}`)
*   `hideLabel` **[boolean][6]**  (optional, default `false`)
*   `containerClass` **[string][4]**  (optional, default `""`)
*   `headerClass` **[string][4]**  (optional, default `""`)
*   `inpClass` **[string][4]**  (optional, default `""`)
*   `tabId` **([string][4] | [number][8])** The tabindex of the field, by default it is the contentIndex (optional, default `contentIndex`)

##### Examples

```javascript
{ 
columns : {"pc": 6, "tablet": 12, "mobile": 12}, 
id:"test-check", 
value: "yes", 
label: "Checkbox", 
name: "checkbox", 
required: true, 
hideLabel: false, 
inpType: "checkbox",
headerClass: "text-red-500" 
popovers : [
{
text: "This is a popover text",
iconName: "info",
},
]
}
```

#### Combobox.vue

This component is used to create a complete combobox field input with error handling and label.
We can be more precise by adding values that need to be selected to be valid.
We can also add popover to display more information.

##### Parameters

*   `id` **[string][4]** Unique id (optional, default `uuidv4()`)
*   `label` **[string][4]** The label of the field. Can be a translation key or by default raw text.
*   `name` **[string][4]** The name of the field. Case no label, this is the fallback. Can be a translation key or by default raw text.
*   `value` **[string][4]**&#x20;
*   `values` **[array][5]**&#x20;
*   `maxBtnChars` **[string][4]** Max char to display in the dropdown button handler. (optional, default `""`)
*   `popovers` **[array][5]?** List of popovers to display more information
*   `inpType` **[string][4]** The type of the field, useful when we have multiple fields in the same container to display the right field (optional, default `"select"`)
*   `disabled` **[boolean][6]**  (optional, default `false`)
*   `required` **[boolean][6]**  (optional, default `false`)
*   `requiredValues` **[array][5]** values that need to be selected to be valid, works only if required is true (optional, default `[]`)
*   `columns` **[object][7]** Field has a grid system. This allow to get multiple field in the same row if needed. (optional, default `{"pc":"12","tablet":"12","mobile":"12}`)
*   `hideLabel` **[boolean][6]**  (optional, default `false`)
*   `onlyDown` **[boolean][6]** If the dropdown should check the bottom of the (optional, default `false`)
*   `overflowAttrEl` **[boolean][6]** Attribut to select the container the element has to check for overflow (optional, default `""`)
*   `containerClass` **[string][4]**  (optional, default `""`)
*   `inpClass` **[string][4]**  (optional, default `""`)
*   `headerClass` **[string][4]**  (optional, default `""`)
*   `tabId` **([string][4] | [number][8])** The tabindex of the field, by default it is the contentIndex (optional, default `contentIndex`)

##### Examples

```javascript
{
id: 'test-input',
value: 'yes',
values : ['yes', 'no'],
name: 'test-input',
disabled: false,
required: true,
requiredValues : ['no'], // need required to be checked
label: 'Test select',
inpType: "select",
popovers : [
{
text: "This is a popover text",
iconName: "info",
},]
}
```

#### Datepicker.vue

This component is used to create a complete datepicker field input with error handling and label.
You can define a default date, a min and max date, and a format.
We can also add popover to display more information.
It is mainly use in forms.

##### Parameters

*   `id` **[string][4]** Unique id (optional, default `uuidv4()`)
*   `label` **[string][4]** The label of the field. Can be a translation key or by default raw text.
*   `name` **[string][4]** The name of the field. Case no label, this is the fallback. Can be a translation key or by default raw text.
*   `popovers` **[array][5]** List of popovers to display more information
*   `inpType` **[string][4]** The type of the field, useful when we have multiple fields in the same container to display the right field (optional, default `"datepicker"`)
*   `value` **[number][6]\<timestamp>** Default date when instanciate (optional, default `""`)
*   `minDate` **[number][6]\<timestamp>** Impossible to pick a date before this date. (optional, default `""`)
*   `maxDate` **[number][6]\<timestamp>** Impossible to pick a date after this date. (optional, default `""`)
*   `isClipboard` **[boolean][7]** allow to copy the timestamp value (optional, default `true`)
*   `hideLabel` **[boolean][7]**  (optional, default `false`)
*   `columns` **[object][8]** Field has a grid system. This allow to get multiple field in the same row if needed. (optional, default `{"pc":"12","tablet":"12","mobile":"12}`)
*   `disabled` **[boolean][7]**  (optional, default `false`)
*   `required` **[boolean][7]**  (optional, default `false`)
*   `headerClass` **[string][4]**  (optional, default `""`)
*   `containerClass` **[string][4]**  (optional, default `""`)
*   `tabId` **([string][4] | [number][6])** The tabindex of the field, by default it is the contentIndex (optional, default `contentIndex`)

##### Examples

```javascript
{ 
id: 'test-date',
columns : {"pc": 6, "tablet": 12, "mobile": 12},
disabled: false,
required: true,
value: 1735682600000,
minDate: 1735682600000,
maxDate: 1735689600000,
inpClass: "text-center",
inpType : ""
popovers : [
{
text: "This is a popover text",
iconName: "info",
},
],
}
```

#### Editor.vue

This component is used to create a complete editor field  with error handling and label.
We can also add popover to display more information.
It is mainly use in forms.

##### Parameters

*   `id` **[string][4]** Unique id (optional, default `uuidv4()`)
*   `label` **[string][4]** The label of the field. Can be a translation key or by default raw text.
*   `name` **[string][4]** The name of the field. Case no label, this is the fallback. Can be a translation key or by default raw text.  @param {string} label
*   `value` **[string][4]**&#x20;
*   `popovers` **[array][5]?** List of popovers to display more information
*   `inpType` **[string][4]** The type of the field, useful when we have multiple fields in the same container to display the right field (optional, default `"editor"`)
*   `columns` **[object][6]** Field has a grid system. This allow to get multiple field in the same row if needed. (optional, default `{"pc":"12","tablet":"12","mobile":"12}`)
*   `pattern` **[string][4]**  (optional, default `""`)
*   `disabled` **[boolean][7]**  (optional, default `false`)
*   `required` **[boolean][7]**  (optional, default `false`)
*   `isClipboard` **[boolean][7]** allow to copy the input value (optional, default `true`)
*   `hideLabel` **[boolean][7]**  (optional, default `false`)
*   `containerClass` **[string][4]**  (optional, default `""`)
*   `editorClass` **[string][4]**  (optional, default `""`)
*   `headerClass` **[string][4]**  (optional, default `""`)
*   `tabId` **([string][4] | [number][8])** The tabindex of the field, by default it is the contentIndex (optional, default `contentIndex`)

##### Examples

```javascript
{
id: "test-editor",
value: "yes",
name: "test-editor",
disabled: false,
required: true,
pattern: "(test)",
label: "Test editor",
tabId: "1",
columns: { pc: 12, tablet: 12, mobile: 12 },
};
```

#### Input.vue

This component is used to create a complete input field input with error handling and label.
We can add a clipboard button to copy the input value.
We can also add a password button to show the password.
We can also add popover to display more information.
It is mainly use in forms.

##### Parameters

*   `id` **[string][4]** Unique id (optional, default `uuidv4()`)
*   `type` **[string][4]** text, email, password, number, tel, url
*   `label` **[string][4]** The label of the field. Can be a translation key or by default raw text.
*   `name` **[string][4]** The name of the field. Case no label, this is the fallback. Can be a translation key or by default raw text.  @param {string} label
*   `value` **[string][4]**&#x20;
*   `popovers` **[array][5]?** List of popovers to display more information
*   `inpType` **[string][4]** The type of the field, useful when we have multiple fields in the same container to display the right field (optional, default `"input"`)
*   `columns` **[object][6]** Field has a grid system. This allow to get multiple field in the same row if needed. (optional, default `{"pc":"12","tablet":"12","mobile":"12}`)
*   `disabled` **[boolean][7]**  (optional, default `false`)
*   `required` **[boolean][7]**  (optional, default `false`)
*   `placeholder` **[string][4]**  (optional, default `""`)
*   `pattern` **[string][4]**  (optional, default `"(?.*)"`)
*   `isClipboard` **[boolean][7]** allow to copy the input value (optional, default `true`)
*   `readonly` **[boolean][7]** allow to read only the input value (optional, default `false`)
*   `hideLabel` **[boolean][7]**  (optional, default `false`)
*   `containerClass` **[string][4]**  (optional, default `""`)
*   `inpClass` **[string][4]**  (optional, default `""`)
*   `headerClass` **[string][4]**  (optional, default `""`)
*   `tabId` **([string][4] | [number][8])** The tabindex of the field, by default it is the contentIndex (optional, default `contentIndex`)

##### Examples

```javascript
{
id: 'test-input',
value: 'yes',
type: "text",
name: 'test-input',
disabled: false,
required: true,
label: 'Test input',
pattern : "(test)",
inpType: "input",
popovers : [
{
text: "This is a popover text",
iconName: "info",
},
],
}
```

#### Select.vue

This component is used to create a complete select field input with error handling and label.
We can be more precise by adding values that need to be selected to be valid.
We can also add popover to display more information.
It is mainly use in forms.

##### Parameters

*   `id` **[string][4]** Unique id (optional, default `uuidv4()`)
*   `label` **[string][4]** The label of the field. Can be a translation key or by default raw text.
*   `name` **[string][4]** The name of the field. Case no label, this is the fallback. Can be a translation key or by default raw text.
*   `value` **[string][4]**&#x20;
*   `values` **[array][5]**&#x20;
*   `popovers` **[array][5]?** List of popovers to display more information
*   `inpType` **[string][4]** The type of the field, useful when we have multiple fields in the same container to display the right field (optional, default `"select"`)
*   `maxBtnChars` **[string][4]** Max char to display in the dropdown button handler. (optional, default `""`)
*   `disabled` **[boolean][6]**  (optional, default `false`)
*   `required` **[boolean][6]**  (optional, default `false`)
*   `requiredValues` **[array][5]** values that need to be selected to be valid, works only if required is true (optional, default `[]`)
*   `columns` **[object][7]** Field has a grid system. This allow to get multiple field in the same row if needed. (optional, default `{"pc":"12","tablet":"12","mobile":"12}`)
*   `hideLabel` **[boolean][6]**  (optional, default `false`)
*   `onlyDown` **[boolean][6]** If the dropdown should check the bottom of the container (optional, default `false`)
*   `overflowAttrEl` **[boolean][6]** Attribut to select the container the element has to check for overflow (optional, default `""`)
*   `containerClass` **[string][4]**  (optional, default `""`)
*   `inpClass` **[string][4]**  (optional, default `""`)
*   `headerClass` **[string][4]**  (optional, default `""`)
*   `tabId` **([string][4] | [number][8])** The tabindex of the field, by default it is the contentIndex (optional, default `contentIndex`)

##### Examples

```javascript
{
id: 'test-input',
value: 'yes',
values : ['yes', 'no'],
name: 'test-input',
disabled: false,
required: true,
requiredValues : ['no'], // need required to be checked
label: 'Test select',
inpType: "select",
popovers : [
{
text: "This is a popover text",
iconName: "info",
},]
}
```

###  Header

#### Field.vue

This component is used with field in order to link a label to field type.
We can add popover to display more information.
Always use with field component.

##### Parameters

*   `label` **[string][4]** The label of the field. Can be a translation key or by default raw text.
*   `id` **[string][4]** The id of the field. This is used to link the label to the field.
*   `name` **[string][4]** The name of the field. Case no label, this is the fallback. Can be a translation key or by default raw text.
*   `popovers` **[array][5]?** List of popovers to display more information
*   `required` **[boolean][6]**  (optional, default `false`)
*   `hideLabel` **[boolean][6]**  (optional, default `false`)
*   `headerClass` **[string][4]**  (optional, default `""`)

##### Examples

```javascript
{
label: 'Test',
version : "0.1.0",
name: 'test-input',
required: true,
popovers : [
{
text: "This is a popover text",
iconName: "info",
},
],
}
```

##  Icon

### Status.vue

This component is a icon used with status.

#### Parameters

*   `id` **[string][4]** The id of the status icon.
*   `status` **[string][4]** The color of the icon between error, success, warning, info (optional, default `"info"`)
*   `statusClass` **[string][4]** Additional class, for example to use with grid system. (optional, default `""`)

#### Examples

```javascript
{
id: "instance-1",
status: "success",
statusClass: "col-span-12",
}
```

##  Icons

### Box.vue

This component is a svg icon representing box.

#### Parameters

*   `iconClass` **[string][4]** The class of the icon. (optional, default `"icon-default"`)
*   `color` **[string][4]** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"dark"`)
*   `disabled` **[boolean][5]** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
color: 'info',
}
```

### Carton.vue

This component is a svg icon representing carton box.

#### Parameters

*   `iconClass` **[string][4]** The class of the icon. (optional, default `"icon-default"`)
*   `color` **[string][4]** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"orange-darker"`)
*   `disabled` **[boolean][5]** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
color: 'info',
}
```

### Check.vue

This component is a svg icon representing a check mark.

#### Parameters

*   `iconClass` **[string][4]** The class of the icon. (optional, default `"icon-default"`)
*   `color` **[string][4]** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"success"`)
*   `disabled` **[boolean][5]** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
color: 'info',
}
```

### Close.vue

This component is a svg icon representing a close mark.

#### Parameters

*   `iconClass` **[string][4]** The class of the icon. (optional, default `"icon-default"`)
*   `color` **[string][4]** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"dark"`)
*   `disabled` **[boolean][5]** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
color: 'info',
}
```

### Core.vue

This component is a svg icon representing core plugin.

#### Parameters

*   `iconClass` **[string][4]** The class of the icon. (optional, default `"icon-default"`)
*   `color` **[string][4]** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"cyan-darker"`)
*   `disabled` **[boolean][5]** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
color: 'info',
}
```

### Core.vue

This component is a svg icon representing core plugin.

#### Parameters

*   `iconClass` **[string][4]** The class of the icon. (optional, default `"icon-default"`)
*   `color` **[string][4]** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"blue"`)
*   `disabled` **[boolean][5]** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
color: 'info',
}
```

### Cross.vue

This component is a svg icon representing a cross mark.

#### Parameters

*   `iconClass` **[string][4]** The class of the icon. (optional, default `"icon-default"`)
*   `color` **[string][4]** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"red"`)
*   `disabled` **[boolean][5]** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
color: 'info',
}
```

### Crown.vue

This component is a svg icon representing crown.

#### Parameters

*   `iconClass` **[string][4]** The class of the icon. (optional, default `"icon-default"`)
*   `color` **[string][4]** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"amber"`)
*   `disabled` **[boolean][5]** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
color: 'info',
}
```

### Discord.vue

This component is a svg icon representing Discord.

#### Parameters

*   `iconClass` **[string][4]** The class of the icon. (optional, default `"icon-default"`)
*   `color` **[string][4]**  (optional, default `"discord"`)
*   `disabled` **[boolean][5]** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
color: 'info',
}
```

### Disk.vue

This component is a svg icon representing disk.

#### Parameters

*   `iconClass` **[string][4]** The class of the icon. (optional, default `"icon-default"`)
*   `color` **[string][4]** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"orange"`)
*   `disabled` **[boolean][5]** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
color: 'info',
}
```

### Disks.vue

This component is a svg icon representing disks.

#### Parameters

*   `iconClass` **[string][4]** The class of the icon. (optional, default `"icon-default"`)
*   `color` **[string][4]** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"orange"`)
*   `disabled` **[boolean][5]** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
color: 'info',
}
```

### Exclamation.vue

This component is a svg icon representing exclamation.

#### Parameters

*   `iconClass` **[string][4]** The class of the icon. (optional, default `"icon-default"`)
*   `color` **[string][4]** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"red"`)
*   `disabled` **[boolean][5]** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
color: 'info',
}
```

### Flag.vue

This component is a svg icon representing flag.

#### Parameters

*   `iconClass` **[string][4]** The class of the icon. (optional, default `"icon-default"`)
*   `color` **[string][4]** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"amber-dark"`)
*   `disabled` **[boolean][5]** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
color: 'info',
}
```

### Funnel.vue

This component is a svg icon representing funnel.

#### Parameters

*   `iconClass` **[string][4]** The class of the icon. (optional, default `"icon-default"`)
*   `color` **[string][4]** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"red"`)
*   `disabled` **[boolean][5]** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
color: 'info',
}
```

### Gear.vue

This component is a svg icon representing gear.

#### Parameters

*   `iconClass` **[string][4]** The class of the icon. (optional, default `"icon-default"`)
*   `color` **[string][4]** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"dark"`)
*   `disabled` **[boolean][5]** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
color: 'info',
}
```

### Github.vue

This component is a svg icon representing Github.

#### Parameters

*   `iconClass` **[string][4]** The class of the icon. (optional, default `"icon-default"`)
*   `color` **[string][4]**  (optional, default `"github"`)
*   `disabled` **[boolean][5]** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
color: 'info',
}
```

### Globe.vue

This component is a svg icon representing globe.

#### Parameters

*   `iconClass` **[string][4]** The class of the icon. (optional, default `"icon-default"`)
*   `color` **[string][4]** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"blue"`)
*   `disabled` **[boolean][5]** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
color: 'info',
}
```

### House.vue

This component is a svg icon representing house.

#### Parameters

*   `iconClass` **[string][4]** The class of the icon. (optional, default `"icon-default"`)
*   `color` **[string][4]** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"cyan-darker"`)
*   `disabled` **[boolean][5]** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
color: 'info',
}
```

### Info.vue

This component is a svg icon representing info.

#### Parameters

*   `iconClass` **[string][4]** The class of the icon. (optional, default `"icon-default"`)
*   `color` **[string][4]** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"info"`)
*   `disabled` **[boolean][5]** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
color: 'info',
}
```

### Key.vue

This component is a svg icon representing key.

#### Parameters

*   `iconClass` **[string][4]** The class of the icon. (optional, default `"icon-default"`)
*   `color` **[string][4]** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `""`)
*   `disabled` **[boolean][5]** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
color: 'info',
}
```

### Linkedin.vue

This component is a svg icon representing Linkedin.

#### Parameters

*   `iconClass` **[string][4]** The class of the icon. (optional, default `"icon-default"`)
*   `color` **[string][4]**  (optional, default `"linkedin"`)
*   `disabled` **[boolean][5]** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
color: 'info',
}
```

### List.vue

This component is a svg icon representing list.

#### Parameters

*   `iconClass` **[string][4]** The class of the icon. (optional, default `"icon-default"`)
*   `color` **[string][4]** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"dark"`)
*   `disabled` **[boolean][5]** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
color: 'info',
}
```

### Lock.vue

This component is a svg icon representing lock.

#### Parameters

*   `iconClass` **[string][4]** The class of the icon. (optional, default `"icon-default"`)
*   `color` **[string][4]** The color of the icon between some tailwind css available colors (purple, green, red, yellow, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"yellow"`)
*   `disabled` **[boolean][5]** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
color: 'info',
}
```

### Plus.vue

This component is a svg icon representing addition (+).

#### Parameters

*   `iconClass` **[string][4]** The class of the icon. (optional, default `"icon-default"`)
*   `color` **[string][4]** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"success"`)
*   `disabled` **[boolean][5]** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
color: 'info',
}
```

### Puzzle.vue

This component is a svg icon representing puzzle.

#### Parameters

*   `iconClass` **[string][4]** The class of the icon. (optional, default `"icon-default"`)
*   `color` **[string][4]** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"yellow"`)
*   `disabled` **[boolean][5]** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
color: 'info',
}
```

### Redirect.vue

This component is a svg icon representing redirect.

#### Parameters

*   `iconClass` **[string][4]** The class of the icon. (optional, default `"icon-default"`)
*   `color` **[string][4]** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"blue"`)
*   `disabled` **[boolean][5]** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
color: 'info',
}
```

### Search.vue

This component is a svg icon representing search.

#### Parameters

*   `iconClass` **[string][4]** The class of the icon. (optional, default `"icon-default"`)
*   `color` **[string][4]** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"info"`)
*   `disabled` **[boolean][5]** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
color: 'info',
}
```

### Settings.vue

This component is a svg icon representing settings.

#### Parameters

*   `iconClass` **[string][4]** The class of the icon. (optional, default `"icon-default"`)
*   `color` **[string][4]** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"blue-darker"`)
*   `disabled` **[boolean][5]** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
color: 'info',
}
```

### Task.vue

This component is a svg icon representing task.

#### Parameters

*   `iconClass` **[string][4]** The class of the icon. (optional, default `"icon-default"`)
*   `color` **[string][4]** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"success"`)
*   `disabled` **[boolean][5]** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
color: 'info',
}
```

### Trash.vue

This component is a svg icon representing trash.

#### Parameters

*   `iconClass` **[string][4]** The class of the icon. (optional, default `"icon-default"`)
*   `color` **[string][4]** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"red"`)
*   `disabled` **[boolean][5]** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
color: 'info',
}
```

### Trespass.vue

This component is a svg icon representing no trespassing.

#### Parameters

*   `iconClass` **[string][4]** The class of the icon. (optional, default `"icon-default"`)
*   `color` **[string][4]** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"error"`)
*   `disabled` **[boolean][5]** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
color: 'info',
}
```

### Twiiter.vue

This component is a svg icon representing Twiiter.

#### Parameters

*   `iconClass` **[string][4]** The class of the icon. (optional, default `"icon-default"`)
*   `color` **[string][4]**  (optional, default `"twitter"`)
*   `disabled` **[boolean][5]** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
color: 'info',
}
```

### Wire.vue

This component is a svg icon representing wire.

#### Parameters

*   `iconClass` **[string][4]** The class of the icon. (optional, default `"icon-default"`)
*   `color` **[string][4]** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, green, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"green"`)
*   `disabled` **[boolean][5]** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
color: 'info',
}
```

##  List

### Details.vue

This component is a list of items separate on two columns : one for the title, and other for a list of popovers related to the plugin (type, link...)

#### Parameters

*   `details` **[string][4]** List of details item that contains a text, disabled state, attrs and list of popovers. We can also add a disabled key to disable the item.
*   `filters` **[array][5]** List of filters to apply on the list of items. (optional, default `[]`)
*   `columns` **columns** Determine the position of the items in the grid system. (optional, default `{pc:4,tablet:6,mobile:12}`)

#### Examples

```javascript
{
details : [{
text: "name",
disabled : false,
attrs: {
id: "id",
value: "value",
},
popovers: [
{
text: "This is a popover text",
iconName: "info",
},
{
text: "This is a popover text",
iconName: "info",
},
],
}]
```

### Pairs.vue

This component is used to display key value information in a list.

#### Parameters

*   `pairs` **[array][4]** The list of key value information. The key and value can be a translation key or a raw text.
*   `columns` **[object][5]** Determine the  position of the items in the grid system. (optional, default `{pc:12,tablet:12,mobile:12}`)

#### Examples

```javascript
{
pairs : [{key: "Total Users", value: "100"}],
columns: {pc: 12, tablet: 12, mobile: 12}
}
```

##  Message

### Unmatch.vue

Display a default message "no match" with dedicated icon.
The message text can be overriden by passing a text prop.

#### Parameters

*   `text` **[string][4]** The text to display
*   `unmatchClass` **[string][4]** The class to apply to the message. If not provided, the class will be based on the parent component. (optional, default `""`)

#### Examples

```javascript
{
text: "dashboard_no_match",
}
```

##  Widget

### Button.vue

This component is a standard button.

#### Parameters

*   `id` **[string][4]** Unique id of the button (optional, default `uuidv4()`)
*   `text` **[string][4]** Content of the button. Can be a translation key or by default raw text.
*   `type` **[string][4]** Can be of type button || submit (optional, default `"button"`)
*   `disabled` **[boolean][5]**  (optional, default `false`)
*   `hideText` **[boolean][5]** Hide text to only display icon (optional, default `false`)
*   `color` **[string][4]**  (optional, default `"primary"`)
*   `iconColor` **[string][4]** Color we want to apply to the icon. If falsy value, default icon color is applied. (optional, default `""`)
*   `size` **[string][4]** Can be of size sm || normal || lg || xl (optional, default `"normal"`)
*   `iconName` **[string][4]** Name in lowercase of icons store on /Icons. If falsy value, no icon displayed. (optional, default `""`)
*   `attrs` **[Object][6]** List of attributs to add to the button. Some attributs will conduct to additionnal script (optional, default `{}`)
*   `tabId` **([string][4] | [number][7])** The tabindex of the field, by default it is the contentIndex (optional, default `contentIndex`)

#### Examples

```javascript
{
id: "open-modal-btn",
text: "Open modal",
disabled: false,
hideText: true,
color: "green",
size: "normal",
iconName: "modal",
attrs: { data-toggle: "modal", "data-target": "#modal"},

}
```

### ButtonGroup.vue

This component allow to display multiple buttons in the same row using flex.
We can define additional class too for the flex container.
We need a list of buttons to display.

#### Parameters

*   `buttons` **[array][4]** List of buttons to display. Button component is used.
*   `groupClass` **[string][5]** Additional class for the flex container (optional, default `""`)

#### Examples

```javascript
{
id: "group-btn",
groupClass : "justify-center",
buttons: [
{
id: "open-modal-btn",
text: "Open modal",
disabled: false,
hideText: true,
color: "green",
size: "normal",
iconName: "modal",
eventAttr: {"store" : "modal", "value" : "open", "target" : "modal_id", "valueExpanded" : "open"},
},
{
id: "close-modal-btn",
text: "Close modal",
disabled: false,
hideText: true,
color: "red",
size: "normal",
iconName: "modal",
eventAttr: {"store" : "modal", "value" : "close", "target" : "modal_id", "valueExpanded" : "close"},
},
],
}
```

### Container.vue

This component is a basic container that can be used to wrap other components.
In case we are working with grid system, we can add columns to position the container.
We can define additional class too.
This component is mainly use as widget container.

#### Parameters

*   `containerClass` **[string][4]** Additional class (optional, default `""`)
*   `columns` **([object][5] | [boolean][6])** Work with grid system { pc: 12, tablet: 12, mobile: 12} (optional, default `false`)
*   `tag` **[string][4]** The tag for the container (optional, default `"div"`)

#### Examples

```javascript
{
containerClass: "w-full h-full bg-white rounded shadow-md",
columns: { pc: 12, tablet: 12, mobile: 12}
}
```

### Filter.vue

This component allow to filter any data object or array with a list of filters.
For the moment, we have 2 types of filters: select and keyword.
We have default values that avoid filter ("all" for select and "" for keyword).
Filters are fields so we need to provide a "field" key with same structure as a Field.
We have to define "keys" that will be the keys the filter value will check.
We can set filter "default" in order to filter the base keys of an object.
We can set filter "settings" in order to filter settings, data must be an advanced template.
We can set filter "table" in order to filter table items.
Check example for more details.

#### Parameters

*   `filters` **[array][4]** Fields with additional data to be used as filters. (optional, default `[]`)
*   `data` **([object][5] | [array][4])** Data object or array to filter. Emit a filter event with the filtered data. (optional, default `{}`)
*   `containerClass` **[string][6]** Additional class for the container. (optional, default `""`)

#### Examples

```javascript
[
{
filter: "default", // or "settings"  or "table"
type: "select",
value: "all",
keys: ["type"],
field: {
inpType: "select",
id: uuidv4(),
value: "all",
// add 'all' as first value
values: ["all"].concat(plugin_types),
name: uuidv4(),
onlyDown: true,
label: "inp_select_plugin_type",
popovers: [
{
text: "inp_select_plugin_type_desc",
iconName: "info",
},
],
columns: { pc: 3, tablet: 4, mobile: 12 },
},
},
...
]
```

### Grid.vue

This component is a basic container that can be used to wrap other components.
This container is based on a grid system and will return a grid container with 12 columns.
We can define additional class too.
This component is mainly use as widget container or as a child of a GridLayout.

#### Parameters

*   `gridClass` **[string][4]** Additional class (optional, default `"items-start"`)

#### Examples

```javascript
{
columns: { pc: 12, tablet: 12, mobile: 12},
gridClass: "items-start"
}
```

### GridLayout.vue

This component is used for top level page layout.
This will determine the position of layout components based on the grid system.
We can create card, modal, table and others top level layout using this component.
This component is mainly use as Grid parent component.

#### Parameters

*   `type` **[string][4]** Type of layout component, we can have "card" or "modal" (optional, default `"card"`)
*   `id` **[string][4]** Id of the layout component, will be used to identify the component. (optional, default `uuidv4()`)
*   `title` **[string][4]** Title of the layout component, will be displayed at the top if exists. Type of layout component will determine the style of the title. (optional, default `""`)
*   `link` **[string][4]** Will transform the container tag from a div to an a tag with the link as href. Useful with card type. (optional, default `""`)
*   `columns` **[object][5]** Work with grid system { pc: 12, tablet: 12, mobile: 12} (optional, default `{"pc":12,"tablet":12,"mobile":12}`)
*   `gridLayoutClass` **[string][4]** Additional class (optional, default `"items-start"`)
*   `tabId` **[string][4]** Case the container is converted to an anchor with a link, we can define the tabId, by default it is the contentIndex (optional, default `contentIndex`)

#### Examples

```javascript
{
type: "card",
title: "Test",
columns: { pc: 12, tablet: 12, mobile: 12},
gridLayoutClass: "items-start"
}
```

### Icons.vue

This component is a wrapper that contains all the icons available in the application (Icons folder).
This component is used to display the icon based on the icon name.
This component is mainly use inside others widgets.

#### Parameters

*   `iconName` **[string][4]** The name of the icon to display. The icon name is the name of the file without the extension on lowercase.
*   `iconClass` **[string][4]** Class to apply to the icon. In case the icon is related to a widget, the widget will set the right class automatically. (optional, default `"base"`)
*   `color` **[string][4]** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `""`)
*   `isStick` **[boolean][5]** If true, the icon will be stick to the top right of the parent container. (optional, default `false`)
*   `disabled` **[boolean][5]** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
iconName: 'box',
iconClass: 'base',
color: 'amber',
}
```

### Instance.vue

This component is an instance widget.
This component is using the Container, TitleCard, IconStatus, ListPairs and ButtonGroup components.

#### Parameters

*   `title` **[string][4]**&#x20;
*   `status` **[string][4]**&#x20;
*   `details` **[array][5]** List of details to display
*   `buttons` **[array][5]** List of buttons to display

#### Examples

```javascript
{
id: "instance-1",
title: "Instance 1",
status: "success",
details: [
{ key: "Version", value: "1.0.0" },
{ key: "Status", value: "Running" },
{ key: "Created", value: "2021-01-01" },
],
buttons : [
{
id: "open-modal-btn",
text: "Open modal",
disabled: false,
hideText: true,
color: "green",
size: "normal",
iconName: "modal",
},
]
}
```

### Popover.vue

This component is a standard popover.

#### Parameters

*   `text` **[string][4]** Content of the popover. Can be a translation key or by default raw text.
*   `href` **[string][4]** Link of the anchor. By default it is a # link. (optional, default `"#"`)
*   `color` **[string][4]** Color of the icon between tailwind colors
*   `attrs` **[object][5]** List of attributs to add to the text. (optional, default `{}`)
*   `tag` **[string][4]** By default it is a anchor tag, but we can use other tag like div in case of popover on another anchor (optional, default `"a"`)
*   `iconClass` **[string][4]**  (optional, default `"icon-default"`)
*   `tabId` **([string][4] | [number][6])** The tabindex of the field, by default it is the contentIndex (optional, default `contentIndex`)

#### Examples

```javascript
{
text: "This is a popover text",
href: "#",
iconName: "info",
attrs: { "data-popover": "test" },
}
```

### PopoverGroup.vue

This component allow to display multiple popovers in the same row using flex.
We can define additional class too for the flex container.
We need a list of popovers to display.

#### Parameters

*   `popovers` **[array][4]** List of popovers to display. Popover component is used.
*   `groupClasss` **[string][5]** Additional class for the flex container (optional, default `""`)

#### Examples

```javascript
{
flexClass : "justify-center",
popovers: [
{
text: "This is a popover text",
iconName: "info",
},
{
text: "This is a popover text",
iconName: "info",
},
],
}
```

### Stat.vue

This component is wrapper of all stat components.
This component has no grid system and will always get the full width of the parent.
This component is mainly use inside a blank card.

#### Parameters

*   `title` **[string][4]** The title of the stat. Can be a translation key or by default raw text.
*   `value` **([string][4] | [number][5])** The value of the stat
*   `subtitle` **[string][4]** The subtitle of the stat. Can be a translation key or by default raw text. (optional, default `""`)
*   `iconName` **[string][4]** A top-right icon to display between icon available in Icons/Stat. Case falsy value, no icon displayed. The icon name is the name of the file without the extension on lowercase. (optional, default `""`)
*   `subtitleColor` **[string][4]** The color of the subtitle between error, success, warning, info (optional, default `"info"`)
*   `statClass` **[string][4]** Additional class (optional, default `""`)

#### Examples

```javascript
{
title: "Total Users",
value: 100,
subtitle : "Last 30 days",
iconName: "user",
link: "/users",
subtitleColor: "info",
}
```

### Subtitle.vue

This component is a general subtitle wrapper.

#### Parameters

*   `subtitle` **[string][4]** Can be a translation key or by default raw text.
*   `type` **[string][4]** The type of title between "container", "card", "content", "min" or "stat" (optional, default `"card"`)
*   `tag` **[string][4]** The tag of the subtitle. Can be h1, h2, h3, h4, h5, h6 or p. If empty, will be determine by the type of subtitle. (optional, default `""`)
*   `color` **[string][4]** The color of the subtitle between error, success, warning, info or tailwind color (optional, default `""`)
*   `bold` **[boolean][5]** If the subtitle should be bold or not. (optional, default `false`)
*   `uppercase` **[boolean][5]** If the subtitle should be uppercase or not. (optional, default `false`)
*   `subtitleClass` **[string][4]** Additional class, useful when component is used directly on a grid system (optional, default `""`)

#### Examples

```javascript
{
subtitle: "Total Users",
type: "card",
subtitleClass: "text-lg",
color : "info",
tag: "h2"
}
```

### Table.vue

This component is used to create a table.
You need to provide a title, a header, a list of positions, and a list of items.
Items need to be an array of array with a cell being a regular widget. Not all widget are supported. Check this component import list to see which widget are supported.
For example, Text, Icons, Icons, Buttons and Fields are supported.

#### Parameters

*   `title` **[string][4]** Determine the title of the table.
*   `header` **[array][5]** Determine the header of the table.
*   `positions` **[array][5]** Determine the position of each item in the table in a list of number based on 12 columns grid.
*   `items` **[array][5]** items to render in the table. This need to be an array (row) of array (cols) with a cell being a regular widget.
*   `filters` **[array][5]** Determine the filters of the table. (optional, default `[]`)
*   `minWidth` **[string][4]** Determine the minimum size of the table. Can be "base", "sm", "md", "lg", "xl". (optional, default `"base"`)
*   `containerClass` **[string][4]** Container additional class. (optional, default `""`)
*   `containerWrapClass` **[string][4]** Container wrap additional class. (optional, default `""`)
*   `tableClass` **[string][4]** Table additional class. (optional, default `""`)

#### Examples

```javascript
{
"title": "Table title",
"header": ["Header 1", "Header 2", "Header 3"],
"minWidth": "base",
"positions": [4,4,4],
"items": [
[
{
"type": "Text",
"data": {
"text": "whitelist-download"

}
},
...
],
...
],

const  filters = [
{
filter: "default",
filterName: "type",
type: "select",
value: "all",
keys: ["type"],
field: {
id: uuidv4(),
value: "all",
// add 'all' as first value
values: ["all"].concat(plugin_types),
name: uuidv4(),
onlyDown: true,
label: "inp_select_plugin_type",
containerClass: "setting",
popovers: [
{
text: "inp_select_plugin_type_desc",
iconName: "info",
},
],
columns: { pc: 3, tablet: 4, mobile: 12 },
},
},
...
}
```

### Text.vue

This component is used for regular paragraph.

#### Parameters

*   `text` **[string][4]** The text value. Can be a translation key or by default raw text.
*   `textClass` **[string][4]** Style of text. Can be replace by any class starting by 'text-' like 'text-stat'. (optional, default `""`)
*   `color` **[string][4]** The color of the text between error, success, warning, info or tailwind color (optional, default `""`)
*   `bold` **[boolean][5]** If the text should be bold or not. (optional, default `false`)
*   `uppercase` **[boolean][5]** If the text should be uppercase or not. (optional, default `false`)
*   `tag` **[string][4]** The tag of the text. Can be p, span, div, h1, h2, h3, h4, h5, h6 (optional, default `"p"`)
*   `icon` **([boolean][5] | [object][6])** The icon to add before the text. If true, will add a default icon. If object, will add the icon with the name and the color. (optional, default `false`)
*   `attrs` **[object][6]** List of attributs to add to the text. (optional, default `{}`)

#### Examples

```javascript
{
text: "This is a paragraph",
textClass: "text-3xl"
attrs: { id: "paragraph" },
}
```

### Title.vue

This component is a general title wrapper.

#### Parameters

*   `title` **[string][4]** Can be a translation key or by default raw text.
*   `type` **[string][4]** The type of title between "container", "card", "content", "min" or "stat" (optional, default `"card"`)
*   `tag` **[string][4]** The tag of the title. Can be h1, h2, h3, h4, h5, h6 or p. If empty, will be determine by the type of title. (optional, default `""`)
*   `color` **[string][4]** The color of the title between error, success, warning, info or tailwind color (optional, default `""`)
*   `uppercase` **[boolean][5]** If the title should be uppercase or not. (optional, default `false`)
*   `titleClass` **[string][4]** Additional class, useful when component is used directly on a grid system (optional, default `""`)

#### Examples

```javascript
{
title: "Total Users",
type: "card",
titleClass: "text-lg",
color : "info",
tag: "h2"
}
```

