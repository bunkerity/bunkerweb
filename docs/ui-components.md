# UI Components

This page contains all the UI components used in the application.

##  Builder

### Bans.vue

This component is lightweight builder containing only the necessary components to create the bans page.

#### Parameters

-   `builder` **array** Array of containers and widgets

#### Examples

```javascript
[
  {
    type: "card",
    gridLayoutClass: "transparent",
    widgets: [
               { type: "MessageUnmatch",
                 data: { text: "bans_not_found" }
              },
   ],
  },
];
```

### Cell.vue

This component includes all elements that can be shown in a table cell.

#### Parameters

-   `type` **string** The type of the cell. This needs to be a Vue component.
-   `data` **object** The data to display in the cell. This needs to be the props of the Vue component.

#### Examples

```javascript
{
    type : "button",
    data : {
      id: "open-modal-btn",
      text: "Open modal",
      disabled: false,
      hideText: true,
      color: "green",
      size: "normal",
      iconName: "modal",
      attrs: { data-toggle: "modal", "data-target": "#modal"},
    }
 }
```

### GlobalConfig.vue

This component is lightweight builder containing only the necessary components to create the instances page.

#### Parameters

-   `builder` **array** Array of containers and widgets

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

-   `builder` **array** Array of containers and widgets

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

-   @example
    \[
    {
    type: "Instance",
    data: {
    details: \[
    { key: \<instances\_hostname="hostname">, value: "[www.example.com][2]" },
    { key: \<instances\_method="method">, value: \<dashboard\_ui> or \<dashboard\_scheduler>...},
    { key: \<instances\_port="port">, value: "1084" },
    { key: \<instances\_status="status">, value: \<instances\_active="active"> or \<instances\_inactive="inactive"> },
    ],
    status: "success",
    title: "[www.example.com][2]",
    buttons: \[
    {
    text: \<action\_\*>,
    color: "edit",
    size: "normal",
    },
    ],
    },
    },
    ];
-   @param {array} builder - Array of containers and widgets

### Modal.vue

This component contains all widgets needed on a modal.
This is different from a page builder as we don't need to define the container and grid layout.
We can't create multiple grids or containers in a modal.

#### Parameters

-   `widgets` **array** Array of containers and widgets

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

## useFocusModal

Check if the modal is present and a focusable element is present inside it.
If it's the case, the function will focus the element.
Case there is already a focused element inside the modal, avoid to focus it again.

#### Parameters

-   `modalId` **string** The id of the modal element.

Returns **void**;

### Modes.vue

This component is lightweight builder containing only the necessary components to create a service mode page.

#### Parameters

-   `builder` **array** Array of containers and widgets

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
                  type: "Raw",
                  data: {
                    template: {},
                  },
                },
      ],
    },
];
```

### PLugin.vue

This component is lightweight builder containing only the necessary components to create the plugins page.

#### Parameters

-   `builder` **array** Array of containers and widgets

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

-   `builder` **array** Array of containers and widgets

#### Examples

```javascript
[
  {
    type: "card",
    gridLayoutClass: "transparent",
    widgets: [
              {
                type: "MessageUnmatch",
                data: { text: "reports_not_found" }
              }
    ],
  },
];
```

### Services.vue

This component is lightweight builder containing only the necessary components to create the services page.

#### Parameters

-   `builder` **array** Array of containers and widgets

#### Examples

```javascript
[
    {
        "type": "card",
        "containerColumns": {
            "pc": 12,
            "tablet": 12,
            "mobile": 12
        },
        "widgets": [
            {
                "type": "Title",
                "data": {
                    "title": "services_title"
                }
            },
            {
                "type": "Table",
                "data": {
                    "title": "services_table_title",
                    "minWidth": "lg",
                    "header": [
                        "services_table_name",
                        "services_table_method",
                        "services_table_settings",
                        "services_table_manage",
                        "services_table_is_draft",
                        "services_table_delete"
                    ],
                    "positions": [
                        2,
                        2,
                        2,
                        2,
                        2,
                        2
                    ],
                    "items": [
                        [
                            {
                                "name": "app1.example.com",
                                "type": "Text",
                                "data": {
                                    "text": "app1.example.com"
                                }
                            },
                            {
                                "method": "scheduler",
                                "type": "Text",
                                "data": {
                                    "text": "scheduler"
                                }
                            },
                            {
                                "type": "Button",
                                "data": {
                                    "id": "open-modal-settings-0",
                                    "text": "settings",
                                    "hideText": false,
                                    " color": "info",
                                    "size": "normal",
                                    "iconName": "settings"
                                }
                            },
                            {
                                "type": "Button",
                                "data": {
                                    "attrs": {
                                        "data-server-name": "app1.example.com"
                                    },
                                    "id": "open-modal-manage-0",
                                    "text": "manage",
                                    "hideText": false,
                                    " color": "green",
                                    "size": "normal",
                                    "iconName": "manage"
                                }
                            },
                            {
                                "type": "Button",
                                "data": {
                                    "attrs": {
                                        "data-server-name": "app1.example.com",
                                        "data-is-draft": "no"
                                    },
                                    "id": "open-modal-draft-0",
                                    "text": "online",
                                    "hideText": false,
                                    " color": "cyan",
                                    "size": "normal",
                                    "iconName": "online"
                                }
                            },
                            {
                                "type": "Button",
                                "data": {
                                    "attrs": {
                                        "data-server-name": "app1.example.com"
                                    },
                                    "id": "open-modal-delete-0",
                                    "text": "delete",
                                    "disabled": true,
                                    "hideText": false,
                                    " color": "red",
                                    "size": "normal",
                                    "iconName": "trash"
                                }
                            }
                        ],
                        [
                            {
                                "name": "www.example.com",
                                "type": "Text",
                                "data": {
                                    "text": "www.example.com"
                                }
                            },
                            {
                                "method": "scheduler",
                                "type": "Text",
                                "data": {
                                    "text": "scheduler"
                                }
                            },
                            {
                                "type": "Button",
                                "data": {
                                    "id": "open-modal-settings-1",
                                    "text": "settings",
                                    "hideText": false,
                                    " color": "info",
                                    "size": "normal",
                                    "iconName": "settings"
                                }
                            },
                            {
                                "type": "Button",
                                "data": {
                                    "attrs": {
                                        "data-server-name": "www.example.com"
                                    },
                                    "id": "open-modal-manage-1",
                                    "text": "manage",
                                    "hideText": false,
                                    " color": "green",
                                    "size": "normal",
                                    "iconName": "manage"
                                }
                            },
                            {
                                "type": "Button",
                                "data": {
                                    "attrs": {
                                        "data-server-name": "www.example.com",
                                        "data-is-draft": "no"
                                    },
                                    "id": "open-modal-draft-1",
                                    "text": "online",
                                    "hideText": false,
                                    " color": "cyan",
                                    "size": "normal",
                                    "iconName": "online"
                                }
                            },
                            {
                                "type": "Button",
                                "data": {
                                    "attrs": {
                                        "data-server-name": "www.example.com"
                                    },
                                    "id": "open-modal-delete-1",
                                    "text": "delete",
                                    "disabled": true,
                                    "hideText": false,
                                    " color": "red",
                                    "size": "normal",
                                    "iconName": "trash"
                                }
                            }
                        ]
                    ],
                    "filters": [
                        {
                            "filter": "table",
                            "filterName": "keyword",
                            "type": "keyword",
                            "value": "",
                            "keys": [
                                "name"
                            ],
                            "field": {
                                "id": "services-keyword",
                                "value": "",
                                "type": "text",
                                "name": "services-keyword",
                                "label": "services_search",
                                "placeholder": "inp_keyword",
                                "isClipboard": false,
                                "popovers": [
                                    {
                                        "text": "services_search_desc",
                                        "iconName": "info"
                                    }
                                ],
                                "columns": {
                                    "pc": 3,
                                    "tablet": 4,
                                    "mobile": 12
                                }
                            }
                        },
                        {
                            "filter": "table",
                            "filterName": "method",
                            "type": "select",
                            "value": "all",
                            "keys": [
                                "method"
                            ],
                            "field": {
                                "id": "services-methods",
                                "value": "all",
                                "values": [
                                    "scheduler"
                                ],
                                "name": "services-methods",
                                "onlyDown": true,
                                "label": "services_methods",
                                "popovers": [
                                    {
                                        "text": "services_methods_desc",
                                        "iconName": "info"
                                    }
                                ],
                                "columns": {
                                    "pc": 3,
                                    "tablet": 4,
                                    "mobile": 12
                                }
                            }
                        },
                        {
                            "filter": "table",
                            "filterName": "draft",
                            "type": "select",
                            "value": "all",
                            "keys": [
                                "draft"
                            ],
                            "field": {
                                "id": "services-draft",
                                "value": "all",
                                "values": [
                                    "all",
                                    "online",
                                    "draft"
                                ],
                                "name": "services-draft",
                                "onlyDown": true,
                                "label": "services_draft",
                                "popovers": [
                                    {
                                        "text": "services_draft_desc",
                                        "iconName": "info"
                                    }
                                ],
                                "columns": {
                                    "pc": 3,
                                    "tablet": 4,
                                    "mobile": 12
                                }
                            }
                        }
                    ]
                }
            }
        ]
    }
]
```

### Setup.vue

This component is lightweight builder containing only the necessary components to create the setup page.

#### Parameters

-   `builder` **array** Array of containers and widgets

##  Dashboard

### Banner.vue

This component is a banner that display news.
The banner will display news from the api if available, otherwise it will display default news.

## setupBanner

This function will try to retrieve banner news from the local storage, and in case it is not available or older than one hour, it will fetch the news from the api.

Returns **void**;

## runBanner

Run the banner animation to display all news at a regular interval.

Returns **void**;

## observeBanner

Check if the banner is visible in the viewport and set the state in the global bannerStore to update related components.

-   @returns {void}

## noTabindex

Stop highlighting a banner item that was focused with tabindex.

Returns **void**;

## isTabindex

Highlighting a banner item that is focused with tabindex.

Returns **void**;

## handleTabIndex

-   @name isTabindex
-   @description Focus with tabindex break banner animation.
    When a banner is focused, we need to add in front of the current banner the focus element.
    And remove it when the focus is lost.

Returns **void**;

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

## updateLangStorage

This function will update the language in the session storage and reload the page.
On reload, we will retrieve the language from the session storage and set it.

#### Parameters

-   `lang` **string** The language to set.

Returns **void**;

### Layout.vue

This component is a layout that wraps the main content of the dashboard.
It includes the header, the menu, the news, the language switcher, the loader, the banner and the footer.
The content part is a slot that can be filled with custom components or using the Builder.vue.

### Loader.vue

This component is a loader used to transition between pages.

## loading

This function will toggle the loading animation.

Returns **void**;

### Menu.vue

This component is a menu that display essential links.
You have all the links to the main pages, the plugins pages, the social links and the logout button.

## getDarkMode

Get the dark mode state from the session storage or the user's preferences.

Returns **void**;

## switchMode

## updateMode

Update the mode of the page.

Returns **void**;

## closeMenu

Close menu when we are on mobile device (else always visible).

Returns **void**;

## closeMenu

Toggle menu when we are on mobile device (else always visible).

Returns **void**;

### News.vue

This component will display news from BunkerWeb blog and allow users to subscribe to the newsletter.
Case the news API is not available, it will display a message.

## loadNews

Retrieve blog news from storage or fetch from the API.

Returns **void**;

##  Form

### Advanced.vue

This component is used to create a complete advanced form with plugin selection.

#### Parameters

-   `template` **object** Template object with plugin and settings data.
-   `containerClass` **string** Container
-   `operation` **string** Operation type (edit, new, delete). (optional, default `"edit"`)
-   `oldServerName` **string** Old server name. This is a server name before any changes. (optional, default `""`)
-   `columns` **object** Columns object.

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

## filter

-   @name filter
-   @description Get the filter data from the <Filter /> component and store the result in the advanced store.
    After that, update some UI states like disabled state.
-   @param {Object} filterData - The filter data from the <Filter /> component.
-   @returns {void}

#### Parameters

-   `filterData` ;

## updateStates

-   @name updateStates
-   @description Update some UI states, usually after a filter, a reload, a remount or a change in the template.
    We will check to set the current plugins available and update the current plugin if needed.
-   @returns {void}

## setValidity

Check template settings and return if there is any error.
Error will disabled save button and display an error message.

Returns **void**;

## getFirstPlugin

-   @name getFirstPlugin
-   @description Get the first available plugin in the template.
-   @param {Object} template - The template object.
-   @returns {string} - The first plugin name.

#### Parameters

-   `template` ;

## getPluginNames

-   @name getPluginNames
-   @description Get the first available plugin in the template.
-   @param {Object} template - The template object.
-   @returns {array} - The list of plugin names.

#### Parameters

-   `template` ;

### Easy.vue

This component is used to create a complete easy form with plugin selection.

#### Parameters

-   `template` **object** Template object with plugin and settings data.
-   `containerClass` **string** Container
-   `operation` **string** Operation type (edit, new, delete). (optional, default `"edit"`)
-   `oldServerName` **string** Old server name. This is a server name before any changes. (optional, default `""`)
-   `columns` **object** Columns object.

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

## setValidity

Check template settings and return if there is any error.
Error will disabled save button and display an error message.

Returns **void**;

## setup

Setup the needed data for the component to work properly.

Returns **void**;

## listenToValidate

Setup the needed data for the component to work properly.

Returns **void**;

### Fields.vue

This component wraps all available fields for a form.

#### Parameters

-   `setting` **object** Setting needed to render a field.

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

-   `template` **object** Template object with plugin and settings data.
-   `operation` **string** Operation type (edit, new, delete). (optional, default `"edit"`)
-   `oldServerName` **string** Old server name. This is a server name before any changes. (optional, default `""`)
-   `containerClass` **string** Container
-   `columns` **object** Columns object.

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

## updateRaw

Get the raw data from editor, update the raw store with it and check if it is valid JSON.

#### Parameters

-   `v` **string** The raw data to update.

Returns **void**;

## json2raw

Convert a JSON object to a raw string that can be passed to the editor.
This will convert JSON to key value pairs (format key=value).
This is only used at first mount when there is no raw data.

#### Parameters

-   `json` **string** The template json to convert

Returns **[string][9]** The raw string

### Templates.vue

This component is used to create a complete  settings form with all modes (advanced, raw, easy).

#### Parameters

-   `templates` **object** List of advanced templates that contains settings. Must be a dict with mode as key, then the template name as key with a list of data (different for each modes).
-   `operation` **string** Operation type (edit, new, delete). (optional, default `"edit"`)
-   `oldServerName` **string** Old server name. This is a server name before any changes. (optional, default `""`)

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

## getFirstTemplateName

Get the first template name from the first mode.

Returns **[string][7]** The first template name

## getFirstTemplateName

Get the first mode name from the first key in props.templates dict.

Returns **[string][7]** The first mode name

##  Forms

###  Error

#### Dropdown.vue

This component is used to display a feedback message on a dropdown field.
It is used with /Forms/Field components.

##### Parameters

-   `isValid` **boolean** Check if the field is valid (optional, default `false`)
-   `isValue` **boolean** Check if the field has a value, display a different message if the field is empty or not (optional, default `false`)
-   `isValueTaken` **boolean** Check if input is already taken. Use with list input. (optional, default `false`)
-   `errorClass` **string** Additional class (optional, default `""`)

##### Examples

```javascript
{
   isValid: false,
   isValue: false,
 }
```

#### Field.vue

This component is an alert type to send feedback to the user.
We can used it as a fixed alert or we can use it in a container as a list.

##### Parameters

-   `title` **string** The title of the alert. Can be a translation key or by default raw text.
-   `message` **string** The message of the alert. Can be a translation key or by default raw text.
-   `canClose` **boolean** Determine if the alert can be closed by user (add a close button), by default it is closable (optional, default `true`)
-   `id` **string**  (optional, default `` `feedback-alert-${message.substring(0,10)}` ``)
-   `isFixed` **string** Determine if the alert is fixed (visible bottom right of page) or relative (inside a container) (optional, default `false`)
-   `type` **string** The type of the alert, can be success, error, warning or info (optional, default `"info"`)
-   `delayToClose` **number** The delay to auto close alert in ms, by default always visible (optional, default `0`)
-   `tabId` **string** The tabindex of the alert (optional, default `"-1"`)

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

-   `id` **id** Unique id (optional, default `uuidv4()`)
-   `isClipboard` **isClipboard** Display a clipboard button to copy a value (optional, default `false`)
-   `valueToCopy` **valueToCopy** The value to copy (optional, default `""`)
-   `clipboadClass` **clipboadClass** Additional class for the clipboard container. Useful to fit the component in a specific container. (optional, default `""`)
-   `copyClass` **copyClass** The class of the copy message. Useful to fit the component in a specific container. (optional, default `""`)

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

-   `id` **string** Unique id (optional, default `uuidv4()`)
-   `label` **string** The label of the field. Can be a translation key or by default raw text.
-   `name` **string** The name of the field. Case no label, this is the fallback. Can be a translation key or by default raw text.
-   `value` **string**;
-   `attrs` **object** Additional attributes to add to the field (optional, default `{}`)
-   `popovers` **array?** List of popovers to display more information
-   `inpType` **string** The type of the field, useful when we have multiple fields in the same container to display the right field (optional, default `"checkbox"`)
-   `disabled` **boolean**  (optional, default `false`)
-   `required` **boolean**  (optional, default `false`)
-   `columns` **object** Field has a grid system. This allow to get multiple field in the same row if needed. (optional, default `{"pc":"12","tablet":"12","mobile":"12"}`)
-   `hideLabel` **boolean**  (optional, default `false`)
-   `containerClass` **string**  (optional, default `""`)
-   `headerClass` **string**  (optional, default `""`)
-   `inpClass` **string**  (optional, default `""`)
-   `tabId` **(string | number)** The tabindex of the field, by default it is the contentIndex (optional, default `contentIndex`)

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

## updateValue

This will convert the boolean checkbox value to a "yes" or "no" string value.
We will check the validity of the checkbox too.

Returns **[string][5]** The new string value of the checkbox 'yes' or 'no'

#### Combobox.vue

This component is used to create a complete combobox field input with error handling and label.
We can be more precise by adding values that need to be selected to be valid.
We can also add popover to display more information.

##### Parameters

-   `id` **string** Unique id (optional, default `uuidv4()`)
-   `label` **string** The label of the field. Can be a translation key or by default raw text.
-   `name` **string** The name of the field. Case no label, this is the fallback. Can be a translation key or by default raw text.
-   `value` **string**;
-   `values` **array**;
-   `attrs` **object** Additional attributes to add to the field (optional, default `{}`)
-   `maxBtnChars` **string** Max char to display in the dropdown button handler. (optional, default `""`)
-   `popovers` **array?** List of popovers to display more information
-   `inpType` **string** The type of the field, useful when we have multiple fields in the same container to display the right field (optional, default `"select"`)
-   `disabled` **boolean**  (optional, default `false`)
-   `required` **boolean**  (optional, default `false`)
-   `requiredValues` **array** values that need to be selected to be valid, works only if required is true (optional, default `[]`)
-   `columns` **object** Field has a grid system. This allow to get multiple field in the same row if needed. (optional, default `{"pc":"12","tablet":"12","mobile":"12"}`)
-   `hideLabel` **boolean**  (optional, default `false`)
-   `onlyDown` **boolean** If the dropdown should check the bottom of the (optional, default `false`)
-   `overflowAttrEl` **boolean** Attribute to select the container the element has to check for overflow (optional, default `""`)
-   `containerClass` **string**  (optional, default `""`)
-   `inpClass` **string**  (optional, default `""`)
-   `headerClass` **string**  (optional, default `""`)
-   `tabId` **(string | number)** The tabindex of the field, by default it is the contentIndex (optional, default `contentIndex`)

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

## toggleSelect

This will toggle the custom select dropdown component.

Returns **void**;

## closeSelect

This will close the custom select dropdown component.

Returns **void**;

## changeValue

This will change the value of the select when a new value is selected from dropdown button.
Check the validity of the select too. Close select after it.

##### Parameters

-   `newValue` **string** The new value to set to the select.

Returns **[string][16]** The new value of the select

## closeOutside

This function is linked to a click event and will check if the target is part of the select component.
Case not and select is open, will close the select.

##### Parameters

-   `e` **event** The event object.

Returns **void**;

## closeScroll

This function is linked to a scroll event and will close the select in case a scroll is detected and the scroll is not the dropdown.

##### Parameters

-   `e` **event** The event object.

Returns **void**;

## closeEscape

This function is linked to a key event and will close the select in case "Escape" key is pressed.

##### Parameters

-   `e` **event** The event object.

Returns **void**;

## closeTab

This function is linked to a key event and will listen to tabindex change.
In case the new tabindex is not part of the select component, will close the select.

##### Parameters

-   `e` **event** The event object.

Returns **void**;

#### Datepicker.vue

This component is used to create a complete datepicker field input with error handling and label.
You can define a default date, a min and max date, and a format.
We can also add popover to display more information.
It is mainly use in forms.

##### Parameters

-   `id` **string** Unique id (optional, default `uuidv4()`)
-   `label` **string** The label of the field. Can be a translation key or by default raw text.
-   `name` **string** The name of the field. Case no label, this is the fallback. Can be a translation key or by default raw text.
-   `popovers` **array** List of popovers to display more information
-   `attrs` **object** Additional attributes to add to the field (optional, default `{}`)
-   `inpType` **string** The type of the field, useful when we have multiple fields in the same container to display the right field (optional, default `"datepicker"`)
-   `value` **number\<timestamp>** Default date when instantiate (optional, default `""`)
-   `minDate` **number\<timestamp>** Impossible to pick a date before this date. (optional, default `""`)
-   `maxDate` **number\<timestamp>** Impossible to pick a date after this date. (optional, default `""`)
-   `isClipboard` **boolean** allow to copy the timestamp value (optional, default `true`)
-   `hideLabel` **boolean**  (optional, default `false`)
-   `columns` **object** Field has a grid system. This allow to get multiple field in the same row if needed. (optional, default `{"pc":"12","tablet":"12","mobile":"12"}`)
-   `disabled` **boolean**  (optional, default `false`)
-   `required` **boolean**  (optional, default `false`)
-   `headerClass` **string**  (optional, default `""`)
-   `containerClass` **string**  (optional, default `""`)
-   `tabId` **(string | number)** The tabindex of the field, by default it is the contentIndex (optional, default `contentIndex`)

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

## setMonthSelect

Create a custom select for month dropdown and hide default one.

##### Parameters

-   `calendarEl` **element** The calendar element.
-   `id` **string** The id of the datepicker.

Returns **void**;

## setPickerAtt

Set attributes to the calendar element to make it more accessible.

##### Parameters

-   `calendarEl` **element** The calendar element.
-   `id` **(string | boolean)** The id of the datepicker. (optional, default `false`)

Returns **void**;

## handleEvents

Handle events on the calendar element, like tabindex.
This will update the tabindex and focus on the right element.
This will update the custom select and options.

##### Parameters

-   `calendarEl` **element** The calendar element.
-   `id` **string** The id of the datepicker.
-   `datepicker` **object** The datepicker instance.

Returns **void**;

## toggleSelect

Toggle the custom select dropdown.

##### Parameters

-   `calendarEl` **element** The calendar element.
-   `id` **string** The id of the datepicker.
-   `e` **event** The event.

Returns **void**;

## closeSelectByDefault

Close the custom select dropdown by default.

##### Parameters

-   `calendarEl` **element** The calendar element.
-   `id` **string** The id of the datepicker.
-   `e` **event** The event.

Returns **void**;

## updateMonth

Update the month when click on custom select option.

##### Parameters

-   `calendarEl` **element** The calendar element.
-   `id` **string** The id of the datepicker.
-   `e` **event** The event.
-   `datepicker` **object** The datepicker instance.

Returns **void**;

## updateIndex

Update the tabindex on the calendar element.

##### Parameters

-   `calendarEl` **element** The calendar element.
-   `target` **string** The event target.

Returns **void**;

## setIndex

Set the tabindex on the calendar element to work with keyboard.

##### Parameters

-   `calendarEl` **element** The calendar element.
-   `tabindex` **string** the tabindex to set.

Returns **void**;

#### Editor.vue

This component is used to create a complete editor field  with error handling and label.
We can also add popover to display more information.
It is mainly use in forms.

##### Parameters

-   `id` **string** Unique id (optional, default `uuidv4()`)
-   `label` **string** The label of the field. Can be a translation key or by default raw text.
-   `name` **string** The name of the field. Case no label, this is the fallback. Can be a translation key or by default raw text.\*  @param {string} label
-   `value` **string**;
-   `attrs` **object** Additional attributes to add to the field (optional, default `{}`)
-   `popovers` **array?** List of popovers to display more information
-   `inpType` **string** The type of the field, useful when we have multiple fields in the same container to display the right field (optional, default `"editor"`)
-   `columns` **object** Field has a grid system. This allow to get multiple field in the same row if needed. (optional, default `{"pc":"12","tablet":"12","mobile":"12"}`)
-   `pattern` **string**  (optional, default `""`)
-   `disabled` **boolean**  (optional, default `false`)
-   `required` **boolean**  (optional, default `false`)
-   `isClipboard` **boolean** allow to copy the input value (optional, default `true`)
-   `hideLabel` **boolean**  (optional, default `false`)
-   `containerClass` **string**  (optional, default `""`)
-   `editorClass` **string**  (optional, default `""`)
-   `headerClass` **string**  (optional, default `""`)
-   `tabId` **(string | number)** The tabindex of the field, by default it is the contentIndex (optional, default `contentIndex`)

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

## removeErrCSS

Remove useless CSS from the editor to avoid accessibility issues.

Returns **void**;

## setEditorAttrs

Override editor attributes by adding or deleting some for better accessibility.

Returns **void**;

#### Input.vue

This component is used to create a complete input field input with error handling and label.
We can add a clipboard button to copy the input value.
We can also add a password button to show the password.
We can also add popover to display more information.
It is mainly use in forms.

##### Parameters

-   `id` **string** Unique id (optional, default `uuidv4()`)
-   `type` **string** text, email, password, number, tel, url
-   `label` **string** The label of the field. Can be a translation key or by default raw text.
-   `name` **string** The name of the field. Case no label, this is the fallback. Can be a translation key or by default raw text.\*  @param {string} label
-   `value` **string**;
-   `attrs` **object** Additional attributes to add to the field (optional, default `{}`)
-   `popovers` **array?** List of popovers to display more information
-   `inpType` **string** The type of the field, useful when we have multiple fields in the same container to display the right field (optional, default `"input"`)
-   `columns` **object** Field has a grid system. This allow to get multiple field in the same row if needed. (optional, default `{"pc":"12","tablet":"12","mobile":"12"}`)
-   `disabled` **boolean**  (optional, default `false`)
-   `required` **boolean**  (optional, default `false`)
-   `placeholder` **string**  (optional, default `""`)
-   `pattern` **string**  (optional, default `"(?.*)"`)
-   `isClipboard` **boolean** allow to copy the input value (optional, default `true`)
-   `readonly` **boolean** allow to read only the input value (optional, default `false`)
-   `hideLabel` **boolean**  (optional, default `false`)
-   `containerClass` **string**  (optional, default `""`)
-   `inpClass` **string**  (optional, default `""`)
-   `headerClass` **string**  (optional, default `""`)
-   `tabId` **(string | number)** The tabindex of the field, by default it is the contentIndex (optional, default `contentIndex`)

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

-   `id` **string** Unique id (optional, default `uuidv4()`)
-   `label` **string** The label of the field. Can be a translation key or by default raw text.
-   `name` **string** The name of the field. Case no label, this is the fallback. Can be a translation key or by default raw text.
-   `value` **string**;
-   `values` **array**;
-   `attrs` **object** Additional attributes to add to the field (optional, default `{}`)
-   `popovers` **array?** List of popovers to display more information
-   `inpType` **string** The type of the field, useful when we have multiple fields in the same container to display the right field (optional, default `"select"`)
-   `maxBtnChars` **string** Max char to display in the dropdown button handler. (optional, default `""`)
-   `disabled` **boolean**  (optional, default `false`)
-   `required` **boolean**  (optional, default `false`)
-   `requiredValues` **array** values that need to be selected to be valid, works only if required is true (optional, default `[]`)
-   `columns` **object** Field has a grid system. This allow to get multiple field in the same row if needed. (optional, default `{"pc":"12","tablet":"12","mobile":"12"}`)
-   `hideLabel` **boolean**  (optional, default `false`)
-   `onlyDown` **boolean** If the dropdown should check the bottom of the container (optional, default `false`)
-   `overflowAttrEl` **boolean** Attribute to select the container the element has to check for overflow (optional, default `""`)
-   `containerClass` **string**  (optional, default `""`)
-   `inpClass` **string**  (optional, default `""`)
-   `headerClass` **string**  (optional, default `""`)
-   `tabId` **(string | number)** The tabindex of the field, by default it is the contentIndex (optional, default `contentIndex`)

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

## toggleSelect

This will toggle the custom select dropdown component.

Returns **void**;

## closeSelect

This will close the custom select dropdown component.

Returns **void**;

## changeValue

This will change the value of the select when a new value is selected from dropdown button.
Check the validity of the select too. Close select after it.

##### Parameters

-   `newValue` **string** The new value to set to the select.

Returns **[string][16]** The new value of the select

## closeOutside

This function is linked to a click event and will check if the target is part of the select component.
Case not and select is open, will close the select.

##### Parameters

-   `e` **event** The event object.

Returns **void**;

## closeScroll

This function is linked to a scroll event and will close the select in case a scroll is detected and the scroll is not the dropdown.

##### Parameters

-   `e` **event** The event object.

Returns **void**;

## closeEscape

This function is linked to a key event and will close the select in case "Escape" key is pressed.

##### Parameters

-   `e` **event** The event object.

Returns **void**;

## closeTab

This function is linked to a key event and will listen to tabindex change.
In case the new tabindex is not part of the select component, will close the select.

##### Parameters

-   `e` **event** The event object.

Returns **void**;

###  Group

#### Multiple.vue

This Will regroup all multiples settings with add and remove logic.
This component under the hood is rendering default fields but by group with possibility to add or remove a multiple group.

##### Parameters

-   `multiples` **object<object>** The multiples settings to display. This needs to be a dict of settings using default field format.
-   `columns` **object** Field has a grid system. This allow to get multiple field in the same row if needed. (optional, default `{"pc":"12","tablet":"12","mobile":"12"}`)
-   `containerClass` **string** Additionnal class to add to the container (optional, default `""`)
-   `tadId` **string** The tabindex of the field, by default it is the contentIndex (optional, default `contentIndex`)

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
                 "REVERSE_PROXY_AUTH_REQUEST": {
                     "context": "multisite",
                     "default": "",
                     "help": "Enable authentication using an external provider (value of auth_request directive).",
                     "id": "reverse-proxy-auth-request",
                     "label": "Reverse proxy auth request",
                     "regex": "^(\\/[\\w\\].~:\\/?#\\[@!$\\&'\\(\\)*+,;=\\-]*|off)?$",
                     "type": "text",
                     "multiple": "reverse-proxy",
                     "pattern": "^(\\/[\\w\\].~:\\/?#\\[@!$\\&'\\(\\)*+,;=\\-]*|off)?$",
                     "inpType": "input",
                     "name": "Reverse proxy auth request",
                     "columns": {
                         "pc": 4,
                         "tablet": 6,
                         "mobile": 12
                     },
                     "disabled": false,
                     "value": "",
                     "popovers": [
                         {
                             "iconName": "disk",
                             "text": "inp_popover_multisite"
                         },
                         {
                             "iconName": "info",
                             "text": "Enable authentication using an external provider (value of auth_request directive)."
                         }
                     ],
                     "containerClass": "z-19"
                 },
                 "REVERSE_PROXY_AUTH_REQUEST_SIGNIN_URL": {
                     "context": "multisite",
                     "default": "",
                     "help": "Redirect clients to sign-in URL when using REVERSE_PROXY_AUTH_REQUEST (used when auth_request call returned 401).",
                     "id": "reverse-proxy-auth-request-signin-url",
                     "label": "Auth request signin URL",
                     "regex": "^(https?:\\/\\/[\\-\\w@:%.+~#=]+[\\-\\w\\(\\)!@:%+.~#?&\\/=$]*)?$",
                     "type": "text",
                     "multiple": "reverse-proxy",
                     "pattern": "^(https?:\\/\\/[\\-\\w@:%.+~#=]+[\\-\\w\\(\\)!@:%+.~#?&\\/=$]*)?$",
                     "inpType": "input",
                     "name": "Auth request signin URL",
                     "columns": {
                         "pc": 4,
                         "tablet": 6,
                         "mobile": 12
                     },
                     "disabled": false,
                     "value": "",
                     "popovers": [
                         {
                             "iconName": "disk",
                             "text": "inp_popover_multisite"
                         },
                         {
                             "iconName": "info",
                             "text": "Redirect clients to sign-in URL when using REVERSE_PROXY_AUTH_REQUEST (used when auth_request call returned 401)."
                         }
                     ],
                     "containerClass": "z-18"
                   },
                 },
             }
         }
       }
   },
```

## setDeleteState

Will determine if the group can be deleted. If at least one input is disabled, the delete button will be disabled.

##### Parameters

-   `group` **object** The multiple group with all settings

Returns **[object][14]** Return delete button data

## setInvisible

Will set a multiple group as invisible.

##### Parameters

-   `id` **(string | number)** The multiple group with all settings

Returns **void**;

## delInvisible

Will remove a multiple group from invisible list.

##### Parameters

-   `id` **(string | number)** The multiple group with all settings

Returns **void**;

## toggleVisible

Will toggle a multiple group visibility.

##### Parameters

-   `id` **(string | number)** The multiple group with all settings

Returns **void**;

## delGroup

Will emit a delete event to the parent component. The parent will update the template and multiples, then the component will rerender.

##### Parameters

-   `multName` **string** The multiple group name
-   `groupName` **string** The multiple group id

Returns **void**;

###  Header

#### Field.vue

This component is used with field in order to link a label to field type.
We can add popover to display more information.
Always use with field component.

##### Parameters

-   `label` **string** The label of the field. Can be a translation key or by default raw text.
-   `id` **string** The id of the field. This is used to link the label to the field.
-   `name` **string** The name of the field. Case no label, this is the fallback. Can be a translation key or by default raw text.
-   `popovers` **array?** List of popovers to display more information
-   `required` **boolean**  (optional, default `false`)
-   `hideLabel` **boolean**  (optional, default `false`)
-   `headerClass` **string**  (optional, default `""`)

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

-   `id` **string** The id of the status icon.
-   `status` **string** The color of the icon between error, success, warning, info (optional, default `"info"`)
-   `statusClass` **string** Additional class, for example to use with grid system. (optional, default `""`)

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

-   `iconClass` **string** The class of the icon. (optional, default `"icon-default"`)
-   `color` **string** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"dark"`)
-   `disabled` **boolean** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
   color: 'info',
 }
```

### Carton.vue

This component is a svg icon representing carton box.

#### Parameters

-   `iconClass` **string** The class of the icon. (optional, default `"icon-default"`)
-   `color` **string** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"orange-darker"`)
-   `disabled` **boolean** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
   color: 'info',
 }
```

### Check.vue

This component is a svg icon representing a check mark.

#### Parameters

-   `iconClass` **string** The class of the icon. (optional, default `"icon-default"`)
-   `color` **string** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"success"`)
-   `disabled` **boolean** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
   color: 'info',
 }
```

### Close.vue

This component is a svg icon representing a close mark.

#### Parameters

-   `iconClass` **string** The class of the icon. (optional, default `"icon-default"`)
-   `color` **string** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"dark"`)
-   `disabled` **boolean** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
   color: 'info',
 }
```

### Core.vue

This component is a svg icon representing core plugin.

#### Parameters

-   `iconClass` **string** The class of the icon. (optional, default `"icon-default"`)
-   `color` **string** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"cyan-darker"`)
-   `disabled` **boolean** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
   color: 'info',
 }
```

### Core.vue

This component is a svg icon representing core plugin.

#### Parameters

-   `iconClass` **string** The class of the icon. (optional, default `"icon-default"`)
-   `color` **string** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"blue"`)
-   `disabled` **boolean** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
   color: 'info',
 }
```

### Cross.vue

This component is a svg icon representing a cross mark.

#### Parameters

-   `iconClass` **string** The class of the icon. (optional, default `"icon-default"`)
-   `color` **string** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"red"`)
-   `disabled` **boolean** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
   color: 'info',
 }
```

### Crown.vue

This component is a svg icon representing crown.

#### Parameters

-   `iconClass` **string** The class of the icon. (optional, default `"icon-default"`)
-   `color` **string** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"amber"`)
-   `disabled` **boolean** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
   color: 'info',
 }
```

### Discord.vue

This component is a svg icon representing Discord.

#### Parameters

-   `iconClass` **string** The class of the icon. (optional, default `"icon-default"`)
-   `color` **string**  (optional, default `"discord"`)
-   `disabled` **boolean** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
   color: 'info',
 }
```

### Disk.vue

This component is a svg icon representing disk.

#### Parameters

-   `iconClass` **string** The class of the icon. (optional, default `"icon-default"`)
-   `color` **string** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"orange"`)
-   `disabled` **boolean** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
   color: 'info',
 }
```

### Disks.vue

This component is a svg icon representing disks.

#### Parameters

-   `iconClass` **string** The class of the icon. (optional, default `"icon-default"`)
-   `color` **string** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"orange"`)
-   `disabled` **boolean** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
   color: 'info',
 }
```

### Document.vue

This component is a svg icon representing document.

#### Parameters

-   `iconClass` **string** The class of the icon. (optional, default `"icon-default"`)
-   `color` **string** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"cyan"`)
-   `disabled` **boolean** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
   color: 'orange',
 }
```

### Exclamation.vue

This component is a svg icon representing exclamation.

#### Parameters

-   `iconClass` **string** The class of the icon. (optional, default `"icon-default"`)
-   `color` **string** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"red"`)
-   `disabled` **boolean** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
   color: 'info',
 }
```

### Eye.vue

This component is a svg icon representing eye.

#### Parameters

-   `iconClass` **string** The class of the icon. (optional, default `"icon-default"`)
-   `color` **string** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"cyan"`)
-   `disabled` **boolean** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
   color: 'green',
 }
```

### Flag.vue

This component is a svg icon representing flag.

#### Parameters

-   `iconClass` **string** The class of the icon. (optional, default `"icon-default"`)
-   `color` **string** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"amber-dark"`)
-   `disabled` **boolean** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
   color: 'info',
 }
```

### Funnel.vue

This component is a svg icon representing funnel.

#### Parameters

-   `iconClass` **string** The class of the icon. (optional, default `"icon-default"`)
-   `color` **string** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"red"`)
-   `disabled` **boolean** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
   color: 'info',
 }
```

### Gear.vue

This component is a svg icon representing gear.

#### Parameters

-   `iconClass` **string** The class of the icon. (optional, default `"icon-default"`)
-   `color` **string** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"dark"`)
-   `disabled` **boolean** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
   color: 'info',
 }
```

### Github.vue

This component is a svg icon representing Github.

#### Parameters

-   `iconClass` **string** The class of the icon. (optional, default `"icon-default"`)
-   `color` **string**  (optional, default `"github"`)
-   `disabled` **boolean** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
   color: 'info',
 }
```

### Globe.vue

This component is a svg icon representing globe.

#### Parameters

-   `iconClass` **string** The class of the icon. (optional, default `"icon-default"`)
-   `color` **string** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"blue"`)
-   `disabled` **boolean** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
   color: 'info',
 }
```

### House.vue

This component is a svg icon representing house.

#### Parameters

-   `iconClass` **string** The class of the icon. (optional, default `"icon-default"`)
-   `color` **string** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"cyan-darker"`)
-   `disabled` **boolean** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
   color: 'info',
 }
```

### Info.vue

This component is a svg icon representing info.

#### Parameters

-   `iconClass` **string** The class of the icon. (optional, default `"icon-default"`)
-   `color` **string** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"info"`)
-   `disabled` **boolean** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
   color: 'info',
 }
```

### Key.vue

This component is a svg icon representing key.

#### Parameters

-   `iconClass` **string** The class of the icon. (optional, default `"icon-default"`)
-   `color` **string** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `""`)
-   `disabled` **boolean** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
   color: 'info',
 }
```

### Linkedin.vue

This component is a svg icon representing Linkedin.

#### Parameters

-   `iconClass` **string** The class of the icon. (optional, default `"icon-default"`)
-   `color` **string**  (optional, default `"linkedin"`)
-   `disabled` **boolean** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
   color: 'info',
 }
```

### List.vue

This component is a svg icon representing list.

#### Parameters

-   `iconClass` **string** The class of the icon. (optional, default `"icon-default"`)
-   `color` **string** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"dark"`)
-   `disabled` **boolean** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
   color: 'info',
 }
```

### Lock.vue

This component is a svg icon representing lock.

#### Parameters

-   `iconClass` **string** The class of the icon. (optional, default `"icon-default"`)
-   `color` **string** The color of the icon between some tailwind css available colors (purple, green, red, yellow, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"yellow"`)
-   `disabled` **boolean** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
   color: 'info',
 }
```

### Pen.vue

This component is a svg icon representing pen.

#### Parameters

-   `iconClass` **string** The class of the icon. (optional, default `"icon-default"`)
-   `color` **string** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"orange"`)
-   `disabled` **boolean** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
  color: 'orange',
}
```

### Plus.vue

This component is a svg icon representing addition (+).

#### Parameters

-   `iconClass` **string** The class of the icon. (optional, default `"icon-default"`)
-   `color` **string** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"success"`)
-   `disabled` **boolean** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
   color: 'info',
 }
```

### Puzzle.vue

This component is a svg icon representing puzzle.

#### Parameters

-   `iconClass` **string** The class of the icon. (optional, default `"icon-default"`)
-   `color` **string** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"yellow"`)
-   `disabled` **boolean** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
   color: 'info',
 }
```

### Redirect.vue

This component is a svg icon representing redirect.

#### Parameters

-   `iconClass` **string** The class of the icon. (optional, default `"icon-default"`)
-   `color` **string** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"blue"`)
-   `disabled` **boolean** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
   color: 'info',
 }
```

### Search.vue

This component is a svg icon representing search.

#### Parameters

-   `iconClass` **string** The class of the icon. (optional, default `"icon-default"`)
-   `color` **string** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"info"`)
-   `disabled` **boolean** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
   color: 'info',
 }
```

### Settings.vue

This component is a svg icon representing settings.

#### Parameters

-   `iconClass` **string** The class of the icon. (optional, default `"icon-default"`)
-   `color` **string** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"blue-darker"`)
-   `disabled` **boolean** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
   color: 'info',
 }
```

### Task.vue

This component is a svg icon representing task.

#### Parameters

-   `iconClass` **string** The class of the icon. (optional, default `"icon-default"`)
-   `color` **string** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"success"`)
-   `disabled` **boolean** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
   color: 'info',
 }
```

### Trash.vue

This component is a svg icon representing trash.

#### Parameters

-   `iconClass` **string** The class of the icon. (optional, default `"icon-default"`)
-   `color` **string** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"red"`)
-   `disabled` **boolean** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
   color: 'info',
 }
```

### Trespass.vue

This component is a svg icon representing no trespassing.

#### Parameters

-   `iconClass` **string** The class of the icon. (optional, default `"icon-default"`)
-   `color` **string** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"error"`)
-   `disabled` **boolean** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
   color: 'info',
 }
```

### Twitter.vue

This component is a svg icon representing Twitter.

#### Parameters

-   `iconClass` **string** The class of the icon. (optional, default `"icon-default"`)
-   `color` **string**  (optional, default `"twitter"`)
-   `disabled` **boolean** If true, the icon will be disabled. (optional, default `false`)

#### Examples

```javascript
{
   color: 'info',
 }
```

### Wire.vue

This component is a svg icon representing wire.

#### Parameters

-   `iconClass` **string** The class of the icon. (optional, default `"icon-default"`)
-   `color` **string** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, green, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `"green"`)
-   `disabled` **boolean** If true, the icon will be disabled. (optional, default `false`)

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
}]
```

## indexUp

When we focus or pointerover an item, we will add a higher z-index than others items in order to avoid to crop popovers.
In case we leave the item, for few moments the item will get an higher z-index than this in order to get a smooth transition.

#### Parameters

-   `id` **(string | number)** The id of the item.

Returns **void**;

## indexPending

This will add a higher z-index for 100ms when cursor is out of the item in order to avoid to crop popovers.

#### Parameters

-   `id` **(string | number)** The id of the item.

Returns **void**;

### Pairs.vue

This component is used to display key value information in a list.

#### Parameters

-   `pairs` **array** The list of key value information. The key and value can be a translation key or a raw text.
-   `columns` **object** Determine the  position of the items in the grid system. (optional, default `{"pc":"12","tablet":"12","mobile":"12"}`)

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

-   `text` **string** The text to display
-   `unmatchClass` **string** The class to apply to the message. If not provided, the class will be based on the parent component. (optional, default `""`)

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

-   `id` **string** Unique id of the button (optional, default `uuidv4()`)
-   `text` **string** Content of the button. Can be a translation key or by default raw text.
-   `type` **string** Can be of type button || submit (optional, default `"button"`)
-   `disabled` **boolean**  (optional, default `false`)
-   `hideText` **boolean** Hide text to only display icon (optional, default `false`)
-   `color` **string**  (optional, default `"primary"`)
-   `iconColor` **string** Color we want to apply to the icon. If falsy value, default icon color is applied. (optional, default `""`)
-   `size` **string** Can be of size sm || normal || lg || xl (optional, default `"normal"`)
-   `iconName` **string** Name in lowercase of icons store on /Icons. If falsy value, no icon displayed. (optional, default `""`)
-   `attrs` **Object** List of attributes to add to the button. Some attributes will conduct to additional script (optional, default `{}`)
-   `modal` **(Object | boolean)** We can link the button to a Modal component. We need to pass the widgets inside the modal. Button click will open the modal. (optional, default `false`)
-   `tabId` **(string | number)** The tabindex of the field, by default it is the contentIndex (optional, default `contentIndex`)
-   `containerClass` **string** Additional class to the container (optional, default `""`)

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

-   `buttons` **array** List of buttons to display. Button component is used.
-   `boutonGroupClass` **string** Additional class for the flex container (optional, default `""`)

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

-   `containerClass` **string** Additional class (optional, default `""`)
-   `columns` **(object | boolean)** Work with grid system { pc: 12, tablet: 12, mobile: 12} (optional, default `false`)
-   `tag` **string** The tag for the container (optional, default `"div"`)

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

-   `filters` **array** Fields with additional data to be used as filters. (optional, default `[]`)
-   `data` **(object | array)** Data object or array to filter. Emit a filter event with the filtered data. (optional, default `{}`)
-   `containerClass` **string** Additional class for the container. (optional, default `""`)

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

## startFilter

Filter the given data using the available filters from a filter object.

#### Parameters

-   `filter` **object** Filter object to apply.
-   `value` **string** Value to filter.

Returns **emits** Emit a filter event with the filtered data.

## filterData

Add a buffer to wait for multiple inputs before filtering the data.
Then filter data with the given filter and value.

#### Parameters

-   `filter` **object** Filter object to apply.
-   `value` **string** Value to filter.

Returns **void**;

## filterRegularSettings

Allow to filter plugin settings from a regular template.

#### Parameters

-   `filterSettings` **object** Filters to apply
-   `template` **object** Template to filter

Returns **void**;

## filterMultiplesSettings

Allow to filter plugin multiples settings from a regular template.

#### Parameters

-   `filterSettings` **object** Filters to apply
-   `template` **object** Template to filter

Returns **void**;

### Grid.vue

This component is a basic container that can be used to wrap other components.
This container is based on a grid system and will return a grid container with 12 columns.
We can define additional class too.
This component is mainly use as widget container or as a child of a GridLayout.

#### Parameters

-   `gridClass` **string** Additional class (optional, default `"items-start"`)

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

-   `type` **string** Type of layout component, we can have "card" (optional, default `"card"`)
-   `id` **string** Id of the layout component, will be used to identify the component. (optional, default `uuidv4()`)
-   `title` **string** Title of the layout component, will be displayed at the top if exists. Type of layout component will determine the style of the title. (optional, default `""`)
-   `link` **string** Will transform the container tag from a div to an a tag with the link as href. Useful with card type. (optional, default `""`)
-   `columns` **object** Work with grid system { pc: 12, tablet: 12, mobile: 12} (optional, default `{"pc":12,"tablet":12,"mobile":12}`)
-   `gridLayoutClass` **string** Additional class (optional, default `"items-start"`)
-   `tabId` **string** Case the container is converted to an anchor with a link, we can define the tabId, by default it is the contentIndex (optional, default `contentIndex`)

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

-   `iconName` **string** The name of the icon to display. The icon name is the name of the file without the extension on lowercase.
-   `iconClass` **string** Class to apply to the icon. In case the icon is related to a widget, the widget will set the right class automatically. (optional, default `"base"`)
-   `color` **string** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `""`)
-   `isStick` **boolean** If true, the icon will be stick to the top right of the parent container. (optional, default `false`)
-   `disabled` **boolean** If true, the icon will be disabled. (optional, default `false`)

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

-   `title` **string**;
-   `status` **string**;
-   `details` **array** List of details to display
-   `buttons` **array** List of buttons to display

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

-   `text` **string** Content of the popover. Can be a translation key or by default raw text.
-   `href` **string** Link of the anchor. By default it is a # link. (optional, default `"#"`)
-   `color` **string** Color of the icon between tailwind colors
-   `attrs` **object** List of attributs to add to the text. (optional, default `{}`)
-   `tag` **string** By default it is a anchor tag, but we can use other tag like div in case of popover on another anchor (optional, default `"a"`)
-   `iconClass` **string**  (optional, default `"icon-default"`)
-   `tabId` **(string | number)** The tabindex of the field, by default it is the contentIndex (optional, default `contentIndex`)

#### Examples

```javascript
{
   text: "This is a popover text",
   href: "#",
   iconName: "info",
   attrs: { "data-popover": "test" },
 }
```

## showPopover

Show the popover and set the position of the popover relative to the container.

Returns **void**;

## hidePopover

Hide the popover.

Returns **void**;

### PopoverGroup.vue

This component allow to display multiple popovers in the same row using flex.
We can define additional class too for the flex container.
We need a list of popovers to display.

#### Parameters

-   `popovers` **array** List of popovers to display. Popover component is used.
-   `groupClasss` **string** Additional class for the flex container (optional, default `""`)

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

-   `title` **string** The title of the stat. Can be a translation key or by default raw text.
-   `value` **(string | number)** The value of the stat
-   `subtitle` **string** The subtitle of the stat. Can be a translation key or by default raw text. (optional, default `""`)
-   `iconName` **string** A top-right icon to display between icon available in Icons/Stat. Case falsy value, no icon displayed. The icon name is the name of the file without the extension on lowercase. (optional, default `""`)
-   `subtitleColor` **string** The color of the subtitle between error, success, warning, info (optional, default `"info"`)
-   `statClass` **string** Additional class (optional, default `""`)

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

-   `subtitle` **string** Can be a translation key or by default raw text.
-   `type` **string** The type of title between "container", "card", "content", "min" or "stat" (optional, default `"card"`)
-   `tag` **string** The tag of the subtitle. Can be h1, h2, h3, h4, h5, h6 or p. If empty, will be determine by the type of subtitle. (optional, default `""`)
-   `color` **string** The color of the subtitle between error, success, warning, info or tailwind color (optional, default `""`)
-   `bold` **boolean** If the subtitle should be bold or not. (optional, default `false`)
-   `uppercase` **boolean** If the subtitle should be uppercase or not. (optional, default `false`)
-   `lowercase` **boolean** If the subtitle should be lowercase or not. (optional, default `false`)
-   `subtitleClass` **string** Additional class, useful when component is used directly on a grid system (optional, default `""`)

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

-   `title` **string** Determine the title of the table.
-   `header` **array** Determine the header of the table.
-   `positions` **array** Determine the position of each item in the table in a list of number based on 12 columns grid.
-   `items` **array** items to render in the table. This need to be an array (row) of array (cols) with a cell being a regular widget.
-   `filters` **array** Determine the filters of the table. (optional, default `[]`)
-   `minWidth` **string** Determine the minimum size of the table. Can be "base", "sm", "md", "lg", "xl". (optional, default `"base"`)
-   `containerClass` **string** Container additional class. (optional, default `""`)
-   `containerWrapClass` **string** Container wrap additional class. (optional, default `""`)
-   `tableClass` **string** Table additional class. (optional, default `""`)

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

## setUnmatchWidth

Determine the width of the unmatch element based on the parent container.

Returns **void**;

## getOverflow

Handle the overflow of the table and update padding in consequence.

Returns **void**;

### Text.vue

This component is used for regular paragraph.

#### Parameters

-   `text` **string** The text value. Can be a translation key or by default raw text.
-   `textClass` **string** Style of text. Can be replace by any class starting by 'text-' like 'text-stat'. (optional, default `""`)
-   `color` **string** The color of the text between error, success, warning, info or tailwind color (optional, default `""`)
-   `bold` **boolean** If the text should be bold or not. (optional, default `false`)
-   `uppercase` **boolean** If the text should be uppercase or not. (optional, default `false`)
-   `tag` **string** The tag of the text. Can be p, span, div, h1, h2, h3, h4, h5, h6 (optional, default `"p"`)
-   `icon` **(boolean | object)** The icon to add before the text. If true, will add a default icon. If object, will add the icon with the name and the color. (optional, default `false`)
-   `attrs` **object** List of attributes to add to the text. (optional, default `{}`)

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

-   `title` **string** Can be a translation key or by default raw text.
-   `type` **string** The type of title between "container", "card", "content", "min" or "stat" (optional, default `"card"`)
-   `tag` **string** The tag of the title. Can be h1, h2, h3, h4, h5, h6 or p. If empty, will be determine by the type of title. (optional, default `""`)
-   `color` **string** The color of the title between error, success, warning, info or tailwind color (optional, default `""`)
-   `uppercase` **boolean** If the title should be uppercase or not. (optional, default `false`)
-   `lowercase` **boolean** If the title should be lowercase or not. (optional, default `false`)
-   `titleClass` **string** Additional class, useful when component is used directly on a grid system (optional, default `""`)

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

## props

This component is lightweight builder containing only the necessary components to create the jobs page.

#### Parameters

-   `builder` **array** Array of containers and widgets

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

## props

This component is lightweight builder containing only the necessary components to create the logs page.

#### Parameters

-   `builder` **array** Array of containers and widgets

