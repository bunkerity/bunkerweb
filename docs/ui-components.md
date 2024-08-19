# UI Components

This page contains all the UI components used in the application.

##  Builder

### Modal.vue

This component contains all widgets needed on a modal.
This is different from a page builder as we don't need to define the container and grid layout.
We can't create multiple grids or containers in a modal.

#### Parameters

-   `widgets` **Array** Array of containers and widgets

#### Examples

```javascript
[
  "id": "modal-delete-plugin",
  "widgets": [
      {
          "type": "Title",
          "data": {
              "title": "plugins_modal_delete_title",
              "type": "modal"
          }
      },
      {
          "type": "Text",
          "data": {
              "text": "plugins_modal_delete_confirm"
          }
      },
      {
          "type": "Text",
          "data": {
              "text": "",
              "bold": true,
              "attrs": {
                  "data-modal-plugin-name": "true"
              }
          }
      },
      {
          "type": "ButtonGroup",
          "data": {
              "buttons": [
                  {
                      "id": "delete-plugin-btn",
                      "text": "action_close",
                      "disabled": false,
                      "color": "close",
                      "size": "normal",
                      "attrs": {
                          "data-hide-el": "modal-delete-plugin"
                      }
                  },
                  {
                      "id": "delete-plugin-btn",
                      "text": "action_delete",
                      "disabled": false,
                      "color": "delete",
                      "size": "normal",
                      "attrs": {
                          "data-delete-plugin-submit": ""
                      }
                  }
              ],
          }
      }
  ]
];
```

##  Form

### Advanced.vue

This component is used to create a complete advanced form with plugin selection.

#### Parameters

-   `template` **Object** Template object with plugin and settings data.
-   `containerClass` **String** Container additional class (optional, default `""`)
-   `operation` **String** Operation type (edit, new, delete). (optional, default `"edit"`)
-   `endpoint` **String** Form endpoint. Case none, will be ignored. (optional, default `""`)
-   `method` **String** Http method to be used on form submit. (optional, default `"POST"`)
-   `oldServerName` **String** Old server name. This is a server name before any changes. (optional, default `""`)
-   `columns` **Object** Columns object. (optional, default `{"pc":"12","tablet":"12","mobile":"12"}`)
-   `display` **Array** Array need two values : "groupName" in index 0 and "compId" in index 1 in order to be displayed using the display store. More info on the display store itslef. (optional, default `[]`)

#### Examples

```javascript
{
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
}
```

### Easy.vue

This component is used to create a complete easy form with plugin selection.

#### Parameters

-   `template` **Object** Template object with plugin and settings data.
-   `containerClass` **String** Container additional class (optional, default `""`)
-   `operation` **String** Operation type (edit, new, delete). (optional, default `"edit"`)
-   `endpoint` **String** Form endpoint. Case none, will be ignored. (optional, default `""`)
-   `method` **String** Http method to be used on form submit. (optional, default `"POST"`)
-   `oldServerName` **String** Old server name. This is a server name before any changes. (optional, default `""`)
-   `columns` **Object** Columns object. (optional, default `{"pc":"12","tablet":"12","mobile":"12"}`)
-   `display` **Array** Array need two values : "groupName" in index 0 and "compId" in index 1 in order to be displayed using the display store. More info on the display store itslef. (optional, default `[]`)

#### Examples

```javascript
{
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
}
```

### Fields.vue

This component wraps all available fields for a form.

#### Parameters

-   `setting` **Object** Setting needed to render a field.

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

### Raw.vue

This component is used to create a complete raw form with settings as JSON format.

#### Parameters

-   `template` **Object** Template object with plugin and settings data.
-   `operation` **String** Operation type (edit, new, delete). (optional, default `"edit"`)
-   `oldServerName` **String** Old server name. This is a server name before any changes. (optional, default `""`)
-   `containerClass` **String** Container additional class (optional, default `""`)
-   `endpoint` **String** Form endpoint. Case none, will be ignored. (optional, default `""`)
-   `method` **String** Http method to be used on form submit. (optional, default `"POST"`)
-   `columns` **Object** Columns object. (optional, default `{"pc":"12","tablet":"12","mobile":"12"}`)
-   `display` **Array** Array need two values : "groupName" in index 0 and "compId" in index 1 in order to be displayed using the display store. More info on the display store itslef. (optional, default `[]`)

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

### Regular.vue

This component is used to create a basic form with fields.

#### Parameters

-   `title` **String** Form title (optional, default `""`)
-   `subtitle` **String** Form subtitle (optional, default `""`)
-   `fields` **Object** List of Fields component to display
-   `buttons` **Object** We need to send a regular ButtonGroup buttons prop
-   `containerClass` **String** Container additional class (optional, default `""`)
-   `endpoint` **String** Form endpoint. Case none, will be ignored. (optional, default `""`)
-   `method` **String** Http method to be used on form submit. (optional, default `"POST"`)
-   `display` **Array** Array need two values : "groupName" in index 0 and "compId" in index 1 in order to be displayed using the display store. More info on the display store itslef. (optional, default `[]`)
-   `maxWidthScreen` **String** Max screen width for the settings based on the breakpoint (xs, sm, md, lg, xl, 2xl) (optional, default `"lg"`)
-   `columns` **Object** Columns object. (optional, default `{"pc":"12","tablet":"12","mobile":"12"}`)

#### Examples

```javascript
fields : [
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

### Templates.vue

This component is used to create a complete  settings form with all modes (advanced, raw, easy).

#### Parameters

-   `templates` **Object** List of advanced templates that contains settings. Must be a dict with mode as key, then the template name as key with a list of data (different for each modes).
-   `operation` **String** Operation type (edit, new, delete). (optional, default `"edit"`)
-   `oldServerName` **String** Old server name. This is a server name before any changes. (optional, default `""`)
-   `isDraft` **(String | Boolean)** Is draft mode. "yes" or "no" to set a draft select. Else will be ignored. (optional, default `false`)
-   `display` **Array** Array need two values : "groupName" in index 0 and "compId" in index 1 in order to be displayed using the display store. More info on the display store itslef. (optional, default `[]`)

#### Examples

```javascript
{
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

-   `title` **String** The title of the alert. Can be a translation key or by default raw text.
-   `message` **String** The message of the alert. Can be a translation key or by default raw text.
-   `canClose` **Boolean** Determine if the alert can be closed by user (add a close button), by default it is closable (optional, default `true`)
-   `isFixed` **String** Determine if the alert is fixed (visible bottom right of page) or relative (inside a container) (optional, default `false`)
-   `type` **String** The type of the alert, can be success, error, warning or info (optional, default `"info"`)
-   `delayToClose` **Number** The delay to auto close alert in ms, by default always visible (optional, default `0`)
-   `tabId` **String** The tabindex of the alert (optional, default `"-1"`)

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
Additional clipboardClass and copyClass can be added to fit the parent container.

##### Parameters

-   `id` **String** Unique id (optional, default `uuidv4()`)
-   `isClipboard` **Boolean** Display a clipboard button to copy a value (optional, default `false`)
-   `valueToCopy` **String** The value to copy (optional, default `""`)
-   `clipboadClass` **String** Additional class for the clipboard container. Useful to fit the component in a specific container. (optional, default `""`)
-   `copyClass` **String** The class of the copy message. Useful to fit the component in a specific container. (optional, default `""`)
-   `fieldSize` **String** Size between "normal" or "sm" (optional, default `"normal"`)

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

-   `id` **String** Unique id (optional, default `uuidv4()`)
-   `label` **String** The label of the field. Can be a translation key or by default raw text.
-   `name` **String** The name of the field. Case no label, this is the fallback. Can be a translation key or by default raw text.
-   `value` **String**;
-   `attrs` **Object** Additional attributes to add to the field (optional, default `{}`)
-   `popovers` **Array** List of popovers to display more information (optional, default `[]`)
-   `inpType` **String** The type of the field, useful when we have multiple fields in the same container to display the right field (optional, default `"checkbox"`)
-   `disabled` **Boolean**  (optional, default `false`)
-   `required` **Boolean**  (optional, default `false`)
-   `columns` **Object** Field has a grid system. This allow to get multiple field in the same row if needed. (optional, default `{"pc":"12","tablet":"12","mobile":"12"}`)
-   `hideLabel` **Boolean**  (optional, default `false`)
-   `containerClass` **String**  (optional, default `""`)
-   `headerClass` **String**  (optional, default `""`)
-   `inpClass` **String**  (optional, default `""`)
-   `fieldSize` **String** Size between "normal" or "sm" (optional, default `"normal"`)
-   `tabId` **(String | Number)** The tabindex of the field, by default it is the contentIndex (optional, default `contentIndex`)
-   `showErrMsg` **Boolean** Show additionnal required or invalid error message at the bottom of the input. Disable by default because help popover, label and outline color are enough for the user. (optional, default `false`)

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

-   `id` **String** Unique id (optional, default `uuidv4()`)
-   `label` **String** The label of the field. Can be a translation key or by default raw text.
-   `name` **String** The name of the field. Case no label, this is the fallback. Can be a translation key or by default raw text.
-   `value` **String**;
-   `values` **Array**;
-   `attrs` **Object** Additional attributes to add to the field (optional, default `{}`)
-   `maxBtnChars` **String** Max char to display in the dropdown button handler. (optional, default `""`)
-   `popovers` **Array** List of popovers to display more information (optional, default `[]`)
-   `inpType` **String** The type of the field, useful when we have multiple fields in the same container to display the right field (optional, default `"select"`)
-   `disabled` **Boolean**  (optional, default `false`)
-   `required` **Boolean**  (optional, default `false`)
-   `requiredValues` **Array** values that need to be selected to be valid, works only if required is true (optional, default `[]`)
-   `columns` **Object** Field has a grid system. This allow to get multiple field in the same row if needed. (optional, default `{"pc":"12","tablet":"12","mobile":"12"}`)
-   `hideLabel` **Boolean**  (optional, default `false`)
-   `onlyDown` **Boolean** If the dropdown should check the bottom of the (optional, default `false`)
-   `overflowAttrEl` **Boolean** Attribute to select the container the element has to check for overflow (optional, default `""`)
-   `containerClass` **String**  (optional, default `""`)
-   `inpClass` **String**  (optional, default `""`)
-   `fieldSize` **String** Size between "normal" or "sm" (optional, default `"normal"`)
-   `headerClass` **String**  (optional, default `""`)
-   `tabId` **(String | Number)** The tabindex of the field, by default it is the contentIndex (optional, default `contentIndex`)
-   `showErrMsg` **Boolean** Show additionnal required or invalid error message at the bottom of the input. Disable by default because help popover, label and outline color are enough for the user. (optional, default `false`)

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
     },
   ]
 }
```

#### Datepicker.vue

This component is used to create a complete datepicker field input with error handling and label.
You can define a default date, a min and max date, and a format.
We can also add popover to display more information.
It is mainly use in forms.

##### Parameters

-   `id` **String** Unique id (optional, default `uuidv4()`)
-   `label` **String** The label of the field. Can be a translation key or by default raw text.
-   `name` **String** The name of the field. Case no label, this is the fallback. Can be a translation key or by default raw text.
-   `popovers` **Array** List of popovers to display more information (optional, default `[]`)
-   `attrs` **Object** Additional attributes to add to the field (optional, default `{}`)
-   `inpType` **String** The type of the field, useful when we have multiple fields in the same container to display the right field (optional, default `"datepicker"`)
-   `value` **Timestamp** Default date when instantiate (optional, default `""`)
-   `minDate` **Timestamp** Impossible to pick a date before this date. (optional, default `""`)
-   `maxDate` **Timestamp** Impossible to pick a date after this date. (optional, default `""`)
-   `isClipboard` **Boolean** allow to copy the timestamp value (optional, default `true`)
-   `hideLabel` **Boolean**  (optional, default `false`)
-   `columns` **Object** Field has a grid system. This allow to get multiple field in the same row if needed. (optional, default `{"pc":"12","tablet":"12","mobile":"12"}`)
-   `disabled` **Boolean**  (optional, default `false`)
-   `required` **Boolean**  (optional, default `false`)
-   `headerClass` **String**  (optional, default `""`)
-   `containerClass` **String**  (optional, default `""`)
-   `fieldSize` **String** Size between "normal" or "sm" (optional, default `"normal"`)
-   `tabId` **(String | Number)** The tabindex of the field, by default it is the contentIndex (optional, default `contentIndex`)
-   `showErrMsg` **Boolean** Show additionnal required or invalid error message at the bottom of the input. Disable by default because help popover, label and outline color are enough for the user. (optional, default `false`)

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

-   `id` **String** Unique id (optional, default `uuidv4()`)
-   `label` **String** The label of the field. Can be a translation key or by default raw text.
-   `name` **String** The name of the field. Case no label, this is the fallback. Can be a translation key or by default raw text.
-   `value` **String**;
-   `attrs` **Object** Additional attributes to add to the field (optional, default `{}`)
-   `popovers` **Array** List of popovers to display more information (optional, default `[]`)
-   `inpType` **String** The type of the field, useful when we have multiple fields in the same container to display the right field (optional, default `"editor"`)
-   `columns` **Object** Field has a grid system. This allow to get multiple field in the same row if needed. (optional, default `{"pc":"12","tablet":"12","mobile":"12"}`)
-   `pattern` **String**  (optional, default `""`)
-   `disabled` **Boolean**  (optional, default `false`)
-   `required` **Boolean**  (optional, default `false`)
-   `isClipboard` **Boolean** allow to copy the input value (optional, default `true`)
-   `hideLabel` **Boolean**  (optional, default `false`)
-   `containerClass` **String**  (optional, default `""`)
-   `inpClass` **String**  (optional, default `""`)
-   `headerClass` **String**  (optional, default `""`)
-   `tabId` **(String | Number)** The tabindex of the field, by default it is the contentIndex (optional, default `contentIndex`)
-   `fieldSize` **String** Size between "normal" or "sm" (optional, default `"normal"`)
-   `showErrMsg` **Boolean** Show additionnal required or invalid error message at the bottom of the input. Disable by default because help popover, label and outline color are enough for the user. (optional, default `false`)

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

-   `id` **String** Unique id (optional, default `uuidv4()`)
-   `type` **String** text, email, password, number, tel, url (optional, default `"text"`)
-   `label` **String** The label of the field. Can be a translation key or by default raw text.
-   `name` **String** The name of the field. Case no label, this is the fallback. Can be a translation key or by default raw text.
-   `value` **String**;
-   `attrs` **Object** Additional attributes to add to the field (optional, default `{}`)
-   `popovers` **Array** List of popovers to display more information (optional, default `[]`)
-   `inpType` **String** The type of the field, useful when we have multiple fields in the same container to display the right field (optional, default `"input"`)
-   `columns` **Object** Field has a grid system. This allow to get multiple field in the same row if needed. (optional, default `{"pc":"12","tablet":"12","mobile":"12"}`)
-   `disabled` **Boolean**  (optional, default `false`)
-   `required` **Boolean**  (optional, default `false`)
-   `placeholder` **String**  (optional, default `""`)
-   `pattern` **String**  (optional, default `"(?.*)"`)
-   `isClipboard` **Boolean** allow to copy the input value (optional, default `true`)
-   `readonly` **Boolean** allow to read only the input value (optional, default `false`)
-   `hideLabel` **Boolean**  (optional, default `false`)
-   `containerClass` **String**  (optional, default `""`)
-   `inpClass` **String**  (optional, default `""`)
-   `headerClass` **String**  (optional, default `""`)
-   `fieldSize` **String** Size between "normal" or "sm" (optional, default `"normal"`)
-   `tabId` **(String | Number)** The tabindex of the field, by default it is the contentIndex (optional, default `contentIndex`)
-   `showErrMsg` **Boolean** Show additionnal required or invalid error message at the bottom of the input. Disable by default because help popover, label and outline color are enough for the user. (optional, default `false`)

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

#### List.vue

This component is used display list of values in a dropdown, remove or add an item in an easy way.
We can also add popover to display more information.

##### Parameters

-   `id` **String** Unique id (optional, default `uuidv4()`)
-   `label` **String** The label of the field. Can be a translation key or by default raw text.
-   `name` **String** The name of the field. Case no label, this is the fallback. Can be a translation key or by default raw text.
-   `value` **String**;
-   `attrs` **Object** Additional attributes to add to the field (optional, default `{}`)
-   `separator` **String** Separator to split the value, by default it is a space (optional, default `" "`)
-   `maxBtnChars` **String** Max char to display in the dropdown button handler. (optional, default `""`)
-   `popovers` **Array** List of popovers to display more information (optional, default `[]`)
-   `inpType` **String** The type of the field, useful when we have multiple fields in the same container to display the right field (optional, default `"list"`)
-   `disabled` **Boolean**  (optional, default `false`)
-   `required` **Boolean**  (optional, default `false`)
-   `columns` **Object** Field has a grid system. This allow to get multiple field in the same row if needed. (optional, default `{"pc":"12","tablet":"12","mobile":"12"}`)
-   `hideLabel` **Boolean**  (optional, default `false`)
-   `onlyDown` **Boolean** If the dropdown should stay down (optional, default `false`)
-   `overflowAttrEl` **Boolean** Attribute the element has to check for overflow (optional, default `""`)
-   `containerClass` **String**  (optional, default `""`)
-   `inpClass` **String**  (optional, default `""`)
-   `headerClass` **String**  (optional, default `""`)
-   `fieldSize` **String** Size between "normal" or "sm" (optional, default `"normal"`)
-   `tabId` **(String | Number)** The tabindex of the field, by default it is the contentIndex (optional, default `contentIndex`)
-   `showErrMsg` **Boolean** Show additionnal required or invalid error message at the bottom of the input. Disable by default because help popover, label and outline color are enough for the user. (optional, default `false`)

##### Examples

```javascript
{
   id: 'test-input',
   value: 'yes no maybe',
   name: 'test-list',
   label: 'Test list',
   inpType: "list",
   popovers : [
     {
       text: "This is a popover text",
       iconName: "info",
     },
   ]
 }
```

#### Select.vue

This component is used to create a complete select field input with error handling and label.
We can be more precise by adding values that need to be selected to be valid.
We can also add popover to display more information.
It is mainly use in forms.

##### Parameters

-   `id` **String** Unique id (optional, default `uuidv4()`)
-   `label` **String** The label of the field. Can be a translation key or by default raw text.
-   `name` **String** The name of the field. Case no label, this is the fallback. Can be a translation key or by default raw text.
-   `value` **String**;
-   `values` **Array**;
-   `attrs` **Object** Additional attributes to add to the field (optional, default `{}`)
-   `popovers` **Array** List of popovers to display more information (optional, default `[]`)
-   `inpType` **String** The type of the field, useful when we have multiple fields in the same container to display the right field (optional, default `"select"`)
-   `maxBtnChars` **String** Max char to display in the dropdown button handler. (optional, default `""`)
-   `disabled` **Boolean**  (optional, default `false`)
-   `required` **Boolean**  (optional, default `false`)
-   `requiredValues` **Array** values that need to be selected to be valid, works only if required is true (optional, default `[]`)
-   `columns` **Object** Field has a grid system. This allow to get multiple field in the same row if needed. (optional, default `{"pc":"12","tablet":"12","mobile":"12"}`)
-   `hideLabel` **Boolean**  (optional, default `false`)
-   `onlyDown` **Boolean** If the dropdown should check the bottom of the container (optional, default `false`)
-   `overflowAttrEl` **Boolean** Attribute to select the container the element has to check for overflow (optional, default `""`)
-   `containerClass` **String**  (optional, default `""`)
-   `inpClass` **String**  (optional, default `""`)
-   `headerClass` **String**  (optional, default `""`)
-   `fieldSize` **String** Size between "normal" or "sm" (optional, default `"normal"`)
-   `tabId` **(String | Number)** The tabindex of the field, by default it is the contentIndex (optional, default `contentIndex`)
-   `hideValidation` **Boolean** If field should be validate and show error. Useful to disable it for filters. (optional, default `false`)

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
     },
   ]
 }
```

###  Group

#### Multiple.vue

This Will regroup all multiples settings with add and remove logic.
This component under the hood is rendering default fields but by group with possibility to add or remove a multiple group.

##### Parameters

-   `multiples` **Object** The multiples settings to display. This needs to be a dict of settings using default field format.
-   `columns` **Object** Field has a grid system. This allow to get multiple field in the same row if needed. (optional, default `{"pc":"12","tablet":"12","mobile":"12"}`)
-   `containerClass` **String** Additionnal class to add to the container (optional, default `""`)
-   `tadId` **String** The tabindex of the field, by default it is the contentIndex (optional, default `contentIndex`)

##### Examples

```javascript
{
   "columns": {"pc": 6, "tablet": 12, "mobile": 12},
     "multiples": {
         "reverse-proxy": {
             "0": {
                 "REVERSE_PROXY_HOST": {
                     "context": "multisite",
                     "default": "",
                     "help": "Full URL of the proxied resource (proxy_pass).",
                     "id": "reverse-proxy-host",
                     "label": "Reverse proxy host",
                     "regex": "^.*$",
                     "type": "text",
                     "multiple": "reverse-proxy",
                     "pattern": "^.*$",
                     "inpType": "input",
                     "name": "Reverse proxy host",
                     "columns": {
                         "pc": 4,
                         "tablet": 6,
                         "mobile": 12
                     },
                     "disabled": false,
                     "value": "service",
                     "popovers": [
                         {
                             "iconName": "disk",
                             "text": "inp_popover_multisite"
                         },
                         {
                             "iconName": "info",
                             "text": "Full URL of the proxied resource (proxy_pass)."
                         }
                     ],
                     "containerClass": "z-26",
                     "method": "ui"
                 },
                 "REVERSE_PROXY_KEEPALIVE": {
                     "context": "multisite",
                     "default": "no",
                     "help": "Enable or disable keepalive connections with the proxied resource.",
                     "id": "reverse-proxy-keepalive",
                     "label": "Reverse proxy keepalive",
                     "regex": "^(yes|no)$",
                     "type": "check",
                     "multiple": "reverse-proxy",
                     "pattern": "^(yes|no)$",
                     "inpType": "checkbox",
                     "name": "Reverse proxy keepalive",
                     "columns": {
                         "pc": 4,
                         "tablet": 6,
                         "mobile": 12
                     },
                     "disabled": false,
                     "value": "no",
                     "popovers": [
                         {
                             "iconName": "disk",
                             "text": "inp_popover_multisite"
                         },
                         {
                             "iconName": "info",
                             "text": "Enable or disable keepalive connections with the proxied resource."
                         }
                     ],
                     "containerClass": "z-20"
                 },
               },
             }
         }
       }
   },
```

###  Header

#### Field.vue

This component is used with field in order to link a label to field type.
We can add popover to display more information.
Always use with field component.

##### Parameters

-   `label` **String** The label of the field. Can be a translation key or by default raw text.
-   `id` **String** The id of the field. This is used to link the label to the field.
-   `name` **String** The name of the field. Case no label, this is the fallback. Can be a translation key or by default raw text.
-   `popovers` **Array** List of popovers to display more information (optional, default `[]`)
-   `required` **Boolean**  (optional, default `false`)
-   `hideLabel` **Boolean**  (optional, default `false`)
-   `headerClass` **String**  (optional, default `""`)
-   `fieldSize` **String** Size between "normal" or "sm" inherit from field (optional, default `"normal"`)

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

-   `id` **String** The id of the status icon.
-   `status` **String** The color of the icon between error, success, warning, info (optional, default `"info"`)
-   `statusClass` **String** Additional class, for example to use with grid system. (optional, default `""`)

#### Examples

```javascript
{
   id: "instance-1",
   status: "success",
   statusClass: "col-span-12",
 }
```

##  List

### Details.vue

This component is a list of items separate on two columns : one for the title, and other for a list of popovers related to the plugin (type, link...)

#### Parameters

-   `details` **string** List of details item that contains a text, disabled state, attrs and list of popovers. We can also add a disabled key to disable the item.
-   `filters` **array** List of filters to apply on the list of items. (optional, default `[]`)
-   `columns` **columns** Determine the position of the items in the grid system. (optional, default `{"pc":"4","tablet":"6","mobile":"12"}`)

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
}
```

### Pairs.vue

This component is used to display key value information in a list.

#### Parameters

-   `pairs` **Array** The list of key value information. The key and value can be a translation key or a raw text.
-   `columns` **Object** Determine the  position of the items in the grid system. (optional, default `{"pc":"12","tablet":"12","mobile":"12"}`)

#### Examples

```javascript
{
   pairs : [
             { key: "Total Users", value: "100" }
           ],
   columns: { pc: 12, tablet: 12, mobile: 12 }
 }
```

##  Message

### Unmatch.vue

Display a default message "no match" with dedicated icon.
The message text can be overridden by passing a text prop.

#### Parameters

-   `text` **String** The text to display
-   `iconName` **String** The icon to display (optional, default `"search"`)
-   `iconColor` **String** The color of the icon (optional, default `""`)
-   `unmatchClass` **String** The class to apply to the message. If not provided, the class will be based on the parent component. (optional, default `""`)

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

-   `id` **String** Unique id of the button (optional, default `uuidv4()`)
-   `text` **String** Content of the button. Can be a translation key or by default raw text.
-   `display` **Array** Case display, we will update the display store with the given array. Useful when we want to use button as tabs. (optional, default `[]`)
-   `type` **String** Can be of type button || submit (optional, default `"button"`)
-   `disabled` **Boolean**  (optional, default `false`)
-   `hideText` **Boolean** Hide text to only display icon (optional, default `false`)
-   `color` **String**  (optional, default `"primary"`)
-   `iconColor` **String** Color we want to apply to the icon. If falsy value, default icon color is applied. (optional, default `""`)
-   `size` **String** Can be of size sm || normal || lg || xl or tab (optional, default `"normal"`)
-   `iconName` **String** Name in lowercase of icons store on /Icons. If falsy value, no icon displayed. (optional, default `""`)
-   `attrs` **Object** List of attributes to add to the button. Some attributes will conduct to additional script (optional, default `{}`)
-   `modal` **(Object | boolean)** We can link the button to a Modal component. We need to pass the widgets inside the modal. Button click will open the modal. (optional, default `false`)
-   `tabId` **(String | Number)** The tabindex of the field, by default it is the contentIndex (optional, default `contentIndex`)
-   `containerClass` **String** Additional class to the container (optional, default `""`)

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

-   `buttons` **Array** List of buttons to display. Button component is used.
-   `buttonGroupClass` **String** Additional class for the flex container (optional, default `""`)

#### Examples

```javascript
{
   id: "group-btn",
   boutonGroupClass : "justify-center",
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

-   `containerClass` **String** Additional class (optional, default `""`)
-   `columns` **(Object | boolean)** Work with grid system { pc: 12, tablet: 12, mobile: 12} (optional, default `{"pc":"12","tablet":"12","mobile":"12"}`)
-   `tag` **String** The tag for the container (optional, default `"div"`)
-   `display` **Array** Array need two values : "groupName" in index 0 and "compId" in index 1 in order to be displayed using the display store. More info on the display store itslef. (optional, default `[]`)

#### Examples

```javascript
{
   containerClass: "w-full h-full bg-white rounded shadow-md",
   columns: { pc: 12, tablet: 12, mobile: 12}
 }
```

### FileManager.vue

File manager component. Useful with cache page.

#### Parameters

-   `data` **Object** Can be a translation key or by default raw text.
-   `baseFolder` **String** The base folder to display by default (optional, default `"base"`)
-   `columns` **Object** Work with grid system { pc: 12, tablet: 12, mobile: 12} (optional, default `{"pc":"12","tablet":"12","mobile":"12"}`)
-   `containerClass` **String** Additional class (optional, default `""`)

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

-   `filters` **Array** Fields with additional data to be used as filters. (optional, default `[]`)
-   `data` **(Object | Array)** Data object or array to filter. Emit a filter event with the filtered data. (optional, default `{}`)
-   `containerClass` **String** Additional class for the container. (optional, default `""`)

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
   ]
```

### Grid.vue

This component is a basic container that can be used to wrap other components.
This container is based on a grid system and will return a grid container with 12 columns.
We can define additional class too.
This component is mainly use as widget container or as a child of a GridLayout.

#### Parameters

-   `gridClass` **String** Additional class (optional, default `"items-start"`)
-   `display` **Array** Array need two values : "groupName" in index 0 and "compId" in index 1 in order to be displayed using the display store. More info on the display store itslef. (optional, default `[]`)

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

-   `type` **String** Type of layout component, we can have "card" (optional, default `"card"`)
-   `id` **String** Id of the layout component, will be used to identify the component. (optional, default `uuidv4()`)
-   `title` **String** Title of the layout component, will be displayed at the top if exists. Type of layout component will determine the style of the title. (optional, default `""`)
-   `link` **String** Will transform the container tag from a div to an a tag with the link as href. Useful with card type. (optional, default `""`)
-   `columns` **Object** Work with grid system { pc: 12, tablet: 12, mobile: 12} (optional, default `{"pc":12,"tablet":12,"mobile":12}`)
-   `gridLayoutClass` **String** Additional class (optional, default `"items-start"`)
-   `display` **Array** Array need two values : "groupName" in index 0 and "compId" in index 1 in order to be displayed using the display store. More info on the display store itslef. (optional, default `[]`)
-   `tabId` **String** Case the container is converted to an anchor with a link, we can define the tabId, by default it is the contentIndex (optional, default `contentIndex`)
-   `maxWidthScreen` **String** Max screen width for the settings based on the breakpoint (xs, sm, md, lg, xl, 2xl, 3xl) (optional, default `"2xl"`)

#### Examples

```javascript
{
   type: "card",
   title: "Test",
   columns: { pc: 12, tablet: 12, mobile: 12},
   gridLayoutClass: "items-start",
  display: ["main", 1],
 }
```

### Icons.vue

This component is a wrapper that contains all the icons available in the application (Icons folder).
This component is used to display the icon based on the icon name.
This component is mainly use inside others widgets.

#### Parameters

-   `iconName` **String** The name of the icon to display. The icon name is the name of the file without the extension on lowercase.
-   `iconClass` **String** Class to apply to the icon. In case the icon is related to a widget, the widget will set the right class automatically. (optional, default `"base"`)
-   `color` **String** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `""`)
-   `isStick` **Boolean** If true, the icon will be stick to the top right of the parent container. (optional, default `false`)
-   `disabled` **Boolean** If true, the icon will be disabled. (optional, default `false`)
-   `value` **Any** Attach a value to icon. Useful on some cases like table filtering using icons. (optional, default `""`)

#### Examples

```javascript
{
   iconName: 'box',
   iconClass: 'base',
   color: 'amber',
 }
```

### Image.vue

This component is used for regular paragraph.

#### Parameters

-   `src` **String** The src value of the image.
-   `alt` **String** The alt value of the image.  Can be a translation key or by default raw text. (optional, default `""`)
-   `imgClass` **String**  (optional, default `""`)
-   `imgContainerClass` **String**  (optional, default `""`)
-   `attrs` **Object** List of attributes to add to the image. (optional, default `{}`)

#### Examples

```javascript
{
   src: "https://via.placeholder.com/150",
   alt: "My image",
   attrs: { id: "paragraph" },
 }
```

### Popover.vue

This component is a standard popover.

#### Parameters

-   `text` **String** Content of the popover. Can be a translation key or by default raw text.
-   `href` **String** Link of the anchor. By default it is a # link. (optional, default `"#"`)
-   `color` **String** Color of the icon between tailwind colors
-   `attrs` **Object** List of attributs to add to the text. (optional, default `{}`)
-   `tag` **String** By default it is a anchor tag, but we can use other tag like div in case of popover on another anchor (optional, default `"a"`)
-   `iconClass` **String**  (optional, default `"icon-default"`)
-   `tabId` **(String | Number)** The tabindex of the field, by default it is the contentIndex (optional, default `contentIndex`)

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

-   `popovers` **Array** List of popovers to display. Popover component is used.
-   `groupClasss` **String** Additional class for the flex container (optional, default `""`)

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

-   `title` **String** The title of the stat. Can be a translation key or by default raw text.
-   `stat` **(String | Number)** The value
-   `subtitle` **String** The subtitle of the stat. Can be a translation key or by default raw text. (optional, default `""`)
-   `iconName` **String** A top-right icon to display between icon available in Icons/Stat. Case falsy value, no icon displayed. The icon name is the name of the file without the extension on lowercase. (optional, default `""`)
-   `subtitleColor` **String** The color of the subtitle between error, success, warning, info (optional, default `"info"`)

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

-   `subtitle` **String** Can be a translation key or by default raw text.
-   `type` **String** The type of title between "container", "card", "content", "min" or "stat" (optional, default `"card"`)
-   `tag` **String** The tag of the subtitle. Can be h1, h2, h3, h4, h5, h6 or p. If empty, will be determine by the type of subtitle. (optional, default `""`)
-   `color` **String** The color of the subtitle between error, success, warning, info or tailwind color (optional, default `""`)
-   `bold` **Boolean** If the subtitle should be bold or not. (optional, default `false`)
-   `uppercase` **Boolean** If the subtitle should be uppercase or not. (optional, default `false`)
-   `lowercase` **Boolean** If the subtitle should be lowercase or not. (optional, default `false`)
-   `subtitleClass` **String** Additional class, useful when component is used directly on a grid system (optional, default `""`)

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

-   `title` **String** Determine the title of the table.
-   `header` **Array** Determine the header of the table.
-   `positions` **Array** Determine the position of each item in the table in a list of number based on 12 columns grid.
-   `items` **Array** items to render in the table. This need to be an array (row) of array (cols) with a cell being a regular widget.
-   `filters` **Array** Determine the filters of the table. (optional, default `[]`)
-   `minWidth` **String** Determine the minimum size of the table. Can be "base", "sm", "md", "lg", "xl". (optional, default `"base"`)
-   `containerClass` **String** Container additional class. (optional, default `""`)
-   `containerWrapClass` **String** Container wrap additional class. (optional, default `""`)
-   `tableClass` **String** Table additional class. (optional, default `""`)

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
     ],
   ],

 filters : [
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
   ];
 }
```

### Tabulator.vue

This component allow to display a table using the Tabulator library with utils and custom components around to work with (like filters).
Because we can't instantiate Vue component inside the Tabulator cell, I choose to send default component props to the cell and teleport the component inside the cell.
The created instance is store in the tableStore using the id as key in order to use it in other components.
UI : I created a formatter for each custom component that will return an empty string.
Sorting : because we aren't working with primitives but props object, each columns that have a custom component will have a custom sorter to avoid sorting error.
Filtering : I created isomorphic filters that will get the right data to check for each custom component object.
To apply a filter, we need to render a field that will be link to the filterTable() function.
A11y :I created a11yTable(), with sortable header tab index.

#### Parameters

-   `id` **String** Unique id of the table
-   `isStriped` **Boolean** Add striped class to the table (optional, default `true`)
-   `filters` **Array** List of filters to display (optional, default `[]`)
-   `columns` **Array** List of columns to display
-   `items` **Array** List of items to display
-   `actionsButtons` **Array** Buttons group props to render buttons that will be after filters and before the table stick left. (optional, default `[]`)
-   `layout` **String** Layout of the table. "fitDataTable" useful with wide columns, "fitColumns" useful with narrow columns. (optional, default `"fitDataTable"`)
-   `rowHeight` **Number** Case value is 0, this will be ignored. (optional, default `0`)
-   `colMinWidth` **Number** Minimum width for each col of  a row (optional, default `150`)
-   `colMaxWidth` **Number** Maximum width for each col of  a row. Case value is 0, this will be ignored. (optional, default `0`)
-   `isPagination` **Boolean** Add pagination to the table (optional, default `true`)
-   `itemsBeforePagination` **Number** Hide pagination unless number is reach. (optional, default `10`)
-   `paginationSize` **Number** Number of items per page (optional, default `10`)
-   `paginationInitialPage` **Number** Initial page (optional, default `1`)
-   `paginationButtonCount` **Number** Available pagination buttons (optional, default `3`)
-   `paginationSizeSelector` **Array** Select number of items per page (optional, default `[10,25,50,100]`)

#### Examples

```javascript
filter =  [{
            "type": "like", // isomorphic filter type
            "fields": ["ip"], // fields to filter
            // setting is a regular Fields props object
            "setting": {
                "id": "input-search-ip",
                "name": "input-search-ip",
                "label": "bans_search_ip",  # keep it (a18n)
                "value": "",
                "inpType": "input",
                "columns": {"pc": 3, "tablet": 4, "mobile": 12},
            },
    }];
```

Returns **Void**;

### Text.vue

This component is used for regular paragraph.

#### Parameters

-   `text` **String** The text value. Can be a translation key or by default raw text.
-   `textClass` **String** Style of text. Can be replace by any class starting by 'text-' like 'text-stat'. (optional, default `""`)
-   `textIconContainerClass` **String** Case we have icon with text, we wrap the text on a container with the icon. We can add a class to this container. (optional, default `"col-span-12 flex justify-center items-center"`)
-   `color` **String** The color of the text between error, success, warning, info or tailwind color (optional, default `""`)
-   `iconName` **String** The name of the icon to display before the text. (optional, default `""`)
-   `iconColor` **String** The color of the icon. (optional, default `""`)
-   `bold` **Boolean** If the text should be bold or not. (optional, default `false`)
-   `uppercase` **Boolean** If the text should be uppercase or not. (optional, default `false`)
-   `tag` **String** The tag of the text. Can be p, span, div, h1, h2, h3, h4, h5, h6 (optional, default `"p"`)
-   `icon` **(Boolean | Object)** The icon to add before the text. If true, will add a default icon. If object, will add the icon with the name and the color. (optional, default `false`)
-   `attrs` **Object** List of attributes to add to the text. (optional, default `{}`)

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

-   `title` **String** Can be a translation key or by default raw text.
-   `type` **String** The type of title between "container", "card", "content", "min" or "stat" (optional, default `"card"`)
-   `tag` **String** The tag of the title. Can be h1, h2, h3, h4, h5, h6 or p. If empty, will be determine by the type of title. (optional, default `""`)
-   `color` **String** The color of the title between error, success, warning, info or tailwind color (optional, default `""`)
-   `uppercase` **Boolean** If the title should be uppercase or not. (optional, default `false`)
-   `lowercase` **Boolean** If the title should be lowercase or not. (optional, default `false`)
-   `titleClass` **String** Additional class, useful when component is used directly on a grid system (optional, default `""`)

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

### Upload.vue

This component is used to upload files to the server. ATM only used to upload plugins.

#### Parameters

-   `disabled` **Boolean** If true, the upload will be disabled. (optional, default `False`)
-   `columns` **Object** Columns object. (optional, default `{"pc":"12","tablet":"12","mobile":"12"}`)
-   `containerClass` **String** Container additional class (optional, default `""`)
-   `maxScreenW` **String** Max screen width within sm, md, lg, xl, 2xl, 3xl (optional, default `"2xl"`)

#### Examples

```javascript
{
   disabled : True
 }
```

