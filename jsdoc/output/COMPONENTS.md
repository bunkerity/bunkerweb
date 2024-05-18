## Builder.vue

This component is a wrapper to create a complete page using containers and widgets.
We have to define each container and each widget inside it.
This is an abstract component that will be used to create any kind of page content (base dashboard elements like menu and news excluded)

### Parameters

*   `builder` **[array][4]** Array of containers and widgets

### Examples

```javascript
[
{
"type": "card",  // this can be a "card", "modal", "table"... etc
"containerClass": "", // tailwind css grid class (items-start, ...)
"containerColumns" : {"pc": 12, "tablet": 12, "mobile": 12},
"title" : "My awesome card", // container title
// Each widget need a name (here type) and associated data
// We need to send specific data for each widget type
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

##  Forms

###  Field

#### Checkbox.vue

This component is used to create a complete checkbox field input with error handling and label.
We can also add popover to display more information.
It is mainly use in forms.

##### Parameters

*   `id` **[string][4]**&#x20;
*   `name` **[string][4]**&#x20;
*   `label` **[string][4]**&#x20;
*   `value` **[string][4]**&#x20;
*   `disabled` **[boolean][5]**  (optional, default `false`)
*   `required` **[boolean][5]**  (optional, default `false`)
*   `columns` **[object][6]**  (optional, default `{"pc":"12","tab":"12","mob":"12}`)
*   `hideLabel` **[boolean][5]**  (optional, default `false`)
*   `containerClass` **[string][4]**  (optional, default `""`)
*   `headerClass` **[string][4]**  (optional, default `""`)
*   `inpClass` **[string][4]**  (optional, default `""`)
*   `tabId` **([string][4] | [number][7])**  (optional, default `""`)

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
headerClass: "text-red-500" 
}
```

#### Datepicker.vue

This component is used to create a complete datepicker field input with error handling and label.
You can define a default date, a min and max date, and a format.
We can also add popover to display more information.
It is mainly use in forms.

##### Parameters

*   `id` **[string][4]**&#x20;
*   `name` **[string][4]**&#x20;
*   `label` **[string][4]**&#x20;
*   `defaultDate` **([string][4] | [number][5] | [date][6])** Default date when instanciate (optional, default `null`)
*   `noPickBeforeStamp` **([string][4] | [number][5])** Impossible to pick a date before this date (optional, default `""`)
*   `noPickAfterStamp` **([string][4] | [number][5])** Impossible to pick a date after this date (optional, default `""`)
*   `hideLabel` **[boolean][7]**  (optional, default `false`)
*   `columns` **([object][8] | [boolean][7])**  (optional, default `{"pc":"12","tab":"12","mob":"12}`)
*   `disabled` **[boolean][7]**  (optional, default `false`)
*   `required` **[boolean][7]**  (optional, default `false`)
*   `headerClass` **[string][4]**  (optional, default `""`)
*   `containerClass` **[string][4]**  (optional, default `""`)
*   `tabId` **([string][4] | [number][5])**  (optional, default `""`)

##### Examples

```javascript
{ 
id: 'test-date',
columns : {"pc": 6, "tablet": 12, "mobile": 12},
disabled: false,
required: true,
defaultDate: 1735682600000,
noPickBeforeStamp: 1735682600000,
noPickAfterStamp: 1735689600000,
inpClass: "text-center",
}
```

#### Input.vue

This component is used to create a complete input field input with error handling and label.
We can add a clipboard button to copy the input value.
We can also add a password button to show the password.
We can also add popover to display more information.
It is mainly use in forms.

##### Parameters

*   `id` **[string][4]**&#x20;
*   `name` **[string][4]**&#x20;
*   `type` **[string][4]** text, email, password, number, tel, url
*   `value` **[string][4]**&#x20;
*   `label` **[string][4]**&#x20;
*   `disabled` **[boolean][5]**  (optional, default `false`)
*   `required` **[boolean][5]**  (optional, default `false`)
*   `placeholder` **[string][4]**  (optional, default `""`)
*   `pattern` **[string][4]**  (optional, default `"(?.*)"`)
*   `clipboard` **[boolean][5]** allow to copy the input value (optional, default `false`)
*   `readonly` **[boolean][5]** allow to read only the input value (optional, default `false`)
*   `hideLabel` **[boolean][5]**  (optional, default `false`)
*   `containerClass` **[string][4]**  (optional, default `""`)
*   `inpClass` **[string][4]**  (optional, default `""`)
*   `headerClass` **[string][4]**  (optional, default `""`)
*   `tabId` **([string][4] | [number][6])**  (optional, default `""`)

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
}
```

#### Select.vue

This component is used to create a complete select field input with error handling and label.
We can be more precise by adding values that need to be selected to be valid.
We can also add popover to display more information.
It is mainly use in forms.

##### Parameters

*   `id` **[string][4]**&#x20;
*   `name` **[string][4]**&#x20;
*   `value` **[string][4]**&#x20;
*   `label` **[string][4]**&#x20;
*   `values` **[array][5]**&#x20;
*   `disabled` **[boolean][6]**  (optional, default `false`)
*   `required` **[boolean][6]**  (optional, default `false`)
*   `requiredValues` **[array][5]** values that need to be selected to be valid, works only if required is true (optional, default `[]`)
*   `columns` **([object][7] | [boolean][6])**  (optional, default `{"pc":"12","tab":"12","mob":"12}`)
*   `hideLabel` **[boolean][6]**  (optional, default `false`)
*   `containerClass` **[string][4]**  (optional, default `""`)
*   `inpClass` **[string][4]**  (optional, default `""`)
*   `headerClass` **[string][4]**  (optional, default `""`)
*   `tabId` **([string][4] | [number][8])**  (optional, default `""`)

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
}
```

###  Header

#### Field.vue

This component is used with field in order to link a label to field type.
We can add popover to display more information.
Always use with field component.

##### Parameters

*   `label` **[string][4]**&#x20;
*   `name` **[string][4]**&#x20;
*   `required` **[boolean][5]**  (optional, default `false`)
*   `hideLabel` **[boolean][5]**  (optional, default `false`)
*   `headerClass` **[string][4]**  (optional, default `""`)

##### Examples

```javascript
{
label: 'Test',
version : "0.1.0",
name: 'test-input',
required: true,
}
```

##  Icons

###  Button

#### Add.vue

This component is used to create a complete svg icon for a button.
This svg is related to a add action button.

##### Parameters

*   `iconColor` **[string][4]**  (optional, default `"white"`)

##### Examples

```javascript
{
iconColor: 'white',
}
```

##  Widget

### Button.vue

This component is a standard button.
You can link this button to the event store on click with eventAttr.
This will allow you to share a value with other components, for example switching form on a click.
The eventAttr object must contain the store name and the value to send on click at least.
It can also contain the target id element and the expanded value, this will add additionnal accessibility attributs to the button.

#### Parameters

*   `id` **[string][4]**&#x20;
*   `text` **[string][4]** Content of the button
*   `type` **[string][4]** Can be of type button || submit (optional, default `"button"`)
*   `disabled` **[boolean][5]**  (optional, default `false`)
*   `hideText` **[boolean][5]** Hide text to only display icon (optional, default `false`)
*   `color` **[string][4]**  (optional, default `"primary"`)
*   `size` **[string][4]** Can be of size sm || normal || lg || xl (optional, default `"normal"`)
*   `iconName` **[string][4]** Name in lowercase of icons store on /Icons/Button (optional, default `""`)
*   `iconColor` **[string][4]**  (optional, default `""`)
*   `eventAttr` **[object][6]** Store event on click {"store" : \<store\_name>, "default" : \<default\_value>,  "value" : \<value\_stored\_on\_click>, "target"<optional> : \<target\_id\_element>, "valueExpanded" : "expanded\_value"} (optional, default `{}`)
*   `tabId` **([string][4] | [number][7])**  (optional, default `""`)

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
iconColor: "white",
eventAttr: {"store" : "modal", "value" : "open", "target" : "modal_id", "valueExpanded" : "open"},7
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

#### Examples

```javascript
{
containerClass: "w-full h-full bg-white rounded shadow-md",
columns: { pc: 12, tablet: 12, mobile: 12}
}
```

### Flex.vue

This component is a basic container that can be used to wrap other components.
Per default, it aligns the components horizontally using flex.
We can define additional class too.
This component is mainly use as widget container or for groups of widget.

#### Parameters

*   `flexClass` **[string][4]** Additional class (optional, default `"flex-start"`)

#### Examples

```javascript
{
flexClass: "flex-start"
}
```

### Grid.vue

This component is a basic container that can be used to wrap other components.
This container is based on a grid system and will return a grid container with 12 columns.
In case we are working with grid system, we can add columns to position the container.
We can define additional class too.
This component is mainly use as widget container or as a child of a GridLayout.

#### Parameters

*   `gridClass` **[string][4]** Additional class (optional, default `"items-start"`)
*   `columns` **([object][5] | [boolean][6])** Work with grid system { pc: 12, tablet: 12, mobile: 12} (optional, default `false`)

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

*   `type` **[string][4]** Type of layout component, we can have : card, table, modal and others (optional, default `"card"`)
*   `title` **[string][4]** Title of the layout component, will be displayed at the top if exists. Type of layout component will determine the style of the title. (optional, default `""`)
*   `columns` **[object][5]** Work with grid system { pc: 12, tablet: 12, mobile: 12} (optional, default `{"pc":12,"tablet":12,"mobile":12}`)
*   `gridLayoutClass` **[string][4]** Additional class (optional, default `"items-start"`)

#### Examples

```javascript
{
type: "card",
title: "Test",
columns: { pc: 12, tablet: 12, mobile: 12},
gridLayoutClass: "items-start"
}
```

