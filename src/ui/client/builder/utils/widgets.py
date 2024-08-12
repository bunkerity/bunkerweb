
from typing import Union

# Add params to data dict only if value is not the default one
def add_key_value(data, key, value, default):
    if value == default:
        return
    data[key] = value
        
def advanced_widget(
    template: dict,
    containerClass: str,
    columns: dict,
    operation: str = "edit",
    oldServerName: str = ""
    ):
    """    
    This component is used to create a complete advanced form with plugin selection.
    
    PARAMETERS
    
    -   `template` **object** Template object with plugin and settings data.
    -   `containerClass` **string** Container
    -   `operation` **string** Operation type (edit, new, delete). (optional, default `"edit"`)
    -   `oldServerName` **string** Old server name. This is a server name before any changes. (optional, default `""`)
    -   `columns` **object** Columns object.
    
    EXAMPLE
    
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
    
    """

    data = {
        "template" : template,
        "containerClass" : containerClass,
        "columns" : columns,
       }


    # List of params that will be add only if not default value
    list_params = [("operation", operation, "edit"),("oldServerName", oldServerName, "")]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Advanced", "data" : data }
        

def button_widget(
    text: str,
    id: str = "",
    type: str = "button",
    disabled: bool = False,
    hideText: bool = False,
    color: str = "primary",
    iconColor: str = "",
    size: str = "normal",
    iconName: str = "",
    attrs: dict = {},
    modal: Union[dict, bool] = False,
    tabId: Union[str, int] = "",
    containerClass: str = ""
    ):
    """    
    This component is a standard button.
    
    PARAMETERS
    
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
    
    EXAMPLE
    
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
    
    """

    data = {
        "text" : text,
       }


    # List of params that will be add only if not default value
    list_params = [("id", id, ""),("type", type, "button"),("disabled", disabled, False),("hideText", hideText, False),("color", color, "primary"),("iconColor", iconColor, ""),("size", size, "normal"),("iconName", iconName, ""),("attrs", attrs, {}),("modal", modal, False),("tabId", tabId, ""),("containerClass", containerClass, "")]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Button", "data" : data }
        

def button_group_widget(
    buttons: list,
    boutonGroupClass: str = ""
    ):
    """    
    This component allow to display multiple buttons in the same row using flex.
    We can define additional class too for the flex container.
    We need a list of buttons to display.
    
    PARAMETERS
    
    -   `buttons` **array** List of buttons to display. Button component is used.
    -   `boutonGroupClass` **string** Additional class for the flex container (optional, default `""`)
    
    EXAMPLE
    
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
    
    """

    data = {
        "buttons" : buttons,
       }


    # List of params that will be add only if not default value
    list_params = [("boutonGroupClass", boutonGroupClass, "")]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Buttongroup", "data" : data }
        

def cell_widget(
    type: str,
    data: dict
    ):
    """    
    This component includes all elements that can be shown in a table cell.
    
    PARAMETERS
    
    -   `type` **string** The type of the cell. This needs to be a Vue component.
    -   `data` **object** The data to display in the cell. This needs to be the props of the Vue component.
    
    EXAMPLE
    
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
    
    """

    data = {
        "type" : type,
        "data" : data,
       }


    return { "type" : "Cell", "data" : data }
        

def checkbox_widget(
    popovers,
    label: str,
    name: str,
    value: str,
    id: str = "",
    attrs: dict = {},
    inpType: str = "checkbox",
    disabled: bool = False,
    required: bool = False,
    columns: dict = {"pc":"12","tablet":"12","mobile":"12"},
    hideLabel: bool = False,
    containerClass: str = "",
    headerClass: str = "",
    inpClass: str = "",
    tabId: Union[str, int] = ""
    ):
    """    
    This component is used to create a complete checkbox field input with error handling and label.
    We can also add popover to display more information.
    It is mainly use in forms.
    
    PARAMETERS
    
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
    
    EXAMPLE
    
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
    
    """

    data = {
        "popovers" : popovers,
        "label" : label,
        "name" : name,
        "value" : value,
       }


    # List of params that will be add only if not default value
    list_params = [("id", id, ""),("attrs", attrs, {}),("inpType", inpType, "checkbox"),("disabled", disabled, False),("required", required, False),("columns", columns, {"pc":"12","tablet":"12","mobile":"12"}),("hideLabel", hideLabel, False),("containerClass", containerClass, ""),("headerClass", headerClass, ""),("inpClass", inpClass, ""),("tabId", tabId, "")]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Checkbox", "data" : data }
        

def clipboard_widget(
    id,
    isClipboard,
    valueToCopy,
    clipboadClass,
    copyClass
    ):
    """    
    This component can be add to some fields to allow to copy the value of the field.
    Additional clipboardClass and copyClass can be added to fit the parent container.
    
    PARAMETERS
    
    -   `id` **id** Unique id (optional, default `uuidv4()`)
    -   `isClipboard` **isClipboard** Display a clipboard button to copy a value (optional, default `false`)
    -   `valueToCopy` **valueToCopy** The value to copy (optional, default `""`)
    -   `clipboadClass` **clipboadClass** Additional class for the clipboard container. Useful to fit the component in a specific container. (optional, default `""`)
    -   `copyClass` **copyClass** The class of the copy message. Useful to fit the component in a specific container. (optional, default `""`)
    
    EXAMPLE
    
    {
       id: 'test-input',
       isClipboard: true,
       valueToCopy: 'yes',
       clipboadClass: 'mx-2',
       copyClass: 'mt-2',
     }
    
    """

    data = {
       }


    # List of params that will be add only if not default value
    list_params = [("id", id, ""),("isClipboard", isClipboard, False),("valueToCopy", valueToCopy, ""),("clipboadClass", clipboadClass, ""),("copyClass", copyClass, "")]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Clipboard", "data" : data }
        

def combobox_widget(
    popovers,
    label: str,
    name: str,
    value: str,
    values: list,
    id: str = "",
    attrs: dict = {},
    maxBtnChars: str = "",
    inpType: str = "select",
    disabled: bool = False,
    required: bool = False,
    requiredValues: list = [],
    columns: dict = {"pc":"12","tablet":"12","mobile":"12"},
    hideLabel: bool = False,
    onlyDown: bool = False,
    overflowAttrEl: bool = "",
    containerClass: str = "",
    inpClass: str = "",
    headerClass: str = "",
    tabId: Union[str, int] = ""
    ):
    """    
    This component is used to create a complete combobox field input with error handling and label.
    We can be more precise by adding values that need to be selected to be valid.
    We can also add popover to display more information.
    
    PARAMETERS
    
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
    
    EXAMPLE
    
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
    
    """

    data = {
        "popovers" : popovers,
        "label" : label,
        "name" : name,
        "value" : value,
        "values" : values,
       }


    # List of params that will be add only if not default value
    list_params = [("id", id, ""),("attrs", attrs, {}),("maxBtnChars", maxBtnChars, ""),("inpType", inpType, "select"),("disabled", disabled, False),("required", required, False),("requiredValues", requiredValues, []),("columns", columns, {"pc":"12","tablet":"12","mobile":"12"}),("hideLabel", hideLabel, False),("onlyDown", onlyDown, False),("overflowAttrEl", overflowAttrEl, ""),("containerClass", containerClass, ""),("inpClass", inpClass, ""),("headerClass", headerClass, ""),("tabId", tabId, "")]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Combobox", "data" : data }
        

def container_widget(
    containerClass: str = "",
    columns: Union[dict, bool] = False,
    tag: str = "div",
    display: list = []
    ):
    """    
    This component is a basic container that can be used to wrap other components.
    In case we are working with grid system, we can add columns to position the container.
    We can define additional class too.
    This component is mainly use as widget container.
    
    PARAMETERS
    
    -   `containerClass` **string** Additional class (optional, default `""`)
    -   `columns` **(object | boolean)** Work with grid system { pc: 12, tablet: 12, mobile: 12} (optional, default `false`)
    -   `tag` **string** The tag for the container (optional, default `"div"`)
    -   `display` **array** Array need to be of format \["groupName", "compId"] in order to be displayed using the display store. More info on the display store itslef. (optional, default `[]`)
    
    EXAMPLE
    
    {
       containerClass: "w-full h-full bg-white rounded shadow-md",
       columns: { pc: 12, tablet: 12, mobile: 12}
     }
    
    """

    data = {
       }


    # List of params that will be add only if not default value
    list_params = [("containerClass", containerClass, ""),("columns", columns, False),("tag", tag, "div"),("display", display, [])]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Container", "data" : data }
        

def datepicker_widget(
    value,
    minDate,
    maxDate,
    label: str,
    name: str,
    popovers: list,
    id: str = "",
    attrs: dict = {},
    inpType: str = "datepicker",
    isClipboard: bool = True,
    hideLabel: bool = False,
    columns: dict = {"pc":"12","tablet":"12","mobile":"12"},
    disabled: bool = False,
    required: bool = False,
    headerClass: str = "",
    containerClass: str = "",
    tabId: Union[str, int] = ""
    ):
    """    
    This component is used to create a complete datepicker field input with error handling and label.
    You can define a default date, a min and max date, and a format.
    We can also add popover to display more information.
    It is mainly use in forms.
    
    PARAMETERS
    
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
    
    EXAMPLE
    
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
    
    """

    data = {
        "label" : label,
        "name" : name,
        "popovers" : popovers,
       }


    # List of params that will be add only if not default value
    list_params = [("value", value, ""),("minDate", minDate, ""),("maxDate", maxDate, ""),("id", id, ""),("attrs", attrs, {}),("inpType", inpType, "datepicker"),("isClipboard", isClipboard, True),("hideLabel", hideLabel, False),("columns", columns, {"pc":"12","tablet":"12","mobile":"12"}),("disabled", disabled, False),("required", required, False),("headerClass", headerClass, ""),("containerClass", containerClass, ""),("tabId", tabId, "")]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Datepicker", "data" : data }
        

def details_widget(
    columns,
    details: str,
    filters: list = []
    ):
    """    
    This component is a list of items separate on two columns : one for the title, and other for a list of popovers related to the plugin (type, link...)
    
    PARAMETERS
    
    -   `details` **string** List of details item that contains a text, disabled state, attrs and list of popovers. We can also add a disabled key to disable the item.
    -   `filters` **array** List of filters to apply on the list of items. (optional, default `[]`)
    -   `columns` **columns** Determine the position of the items in the grid system. (optional, default `{"pc":"4","tablet":"6","mobile":"12"}`)
    
    EXAMPLE
    
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
    
    """

    data = {
        "details" : details,
       }


    # List of params that will be add only if not default value
    list_params = [("columns", columns, {"pc":"4","tablet":"6","mobile":"12"}),("filters", filters, [])]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Details", "data" : data }
        

def easy_widget(
    template: dict,
    containerClass: str,
    columns: dict,
    operation: str = "edit",
    oldServerName: str = ""
    ):
    """    
    This component is used to create a complete easy form with plugin selection.
    
    PARAMETERS
    
    -   `template` **object** Template object with plugin and settings data.
    -   `containerClass` **string** Container
    -   `operation` **string** Operation type (edit, new, delete). (optional, default `"edit"`)
    -   `oldServerName` **string** Old server name. This is a server name before any changes. (optional, default `""`)
    -   `columns` **object** Columns object.
    
    EXAMPLE
    
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
    
    """

    data = {
        "template" : template,
        "containerClass" : containerClass,
        "columns" : columns,
       }


    # List of params that will be add only if not default value
    list_params = [("operation", operation, "edit"),("oldServerName", oldServerName, "")]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Easy", "data" : data }
        

def editor_widget(
    popovers,
    label: str,
    name: str,
    value: str,
    id: str = "",
    attrs: dict = {},
    inpType: str = "editor",
    columns: dict = {"pc":"12","tablet":"12","mobile":"12"},
    pattern: str = "",
    disabled: bool = False,
    required: bool = False,
    isClipboard: bool = True,
    hideLabel: bool = False,
    containerClass: str = "",
    editorClass: str = "",
    headerClass: str = "",
    tabId: Union[str, int] = ""
    ):
    """    
    This component is used to create a complete editor field  with error handling and label.
    We can also add popover to display more information.
    It is mainly use in forms.
    
    PARAMETERS
    
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
    
    EXAMPLE
    
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
    
    """

    data = {
        "popovers" : popovers,
        "label" : label,
        "name" : name,
        "value" : value,
       }


    # List of params that will be add only if not default value
    list_params = [("id", id, ""),("attrs", attrs, {}),("inpType", inpType, "editor"),("columns", columns, {"pc":"12","tablet":"12","mobile":"12"}),("pattern", pattern, ""),("disabled", disabled, False),("required", required, False),("isClipboard", isClipboard, True),("hideLabel", hideLabel, False),("containerClass", containerClass, ""),("editorClass", editorClass, ""),("headerClass", headerClass, ""),("tabId", tabId, "")]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Editor", "data" : data }
        

def field_widget(
    popovers,
    label: str,
    id: str,
    name: str,
    required: bool = False,
    hideLabel: bool = False,
    headerClass: str = ""
    ):
    """    
    This component is used with field in order to link a label to field type.
    We can add popover to display more information.
    Always use with field component.
    
    PARAMETERS
    
    -   `label` **string** The label of the field. Can be a translation key or by default raw text.
    -   `id` **string** The id of the field. This is used to link the label to the field.
    -   `name` **string** The name of the field. Case no label, this is the fallback. Can be a translation key or by default raw text.
    -   `popovers` **array?** List of popovers to display more information
    -   `required` **boolean**  (optional, default `false`)
    -   `hideLabel` **boolean**  (optional, default `false`)
    -   `headerClass` **string**  (optional, default `""`)
    
    EXAMPLE
    
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
    
    """

    data = {
        "popovers" : popovers,
        "label" : label,
        "id" : id,
        "name" : name,
       }


    # List of params that will be add only if not default value
    list_params = [("required", required, False),("hideLabel", hideLabel, False),("headerClass", headerClass, "")]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Field", "data" : data }
        

def fields_widget(
    setting: dict
    ):
    """    
    This component wraps all available fields for a form.
    
    PARAMETERS
    
    -   `setting` **object** Setting needed to render a field.
    
    EXAMPLE
    
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
    
    """

    data = {
        "setting" : setting,
       }


    return { "type" : "Fields", "data" : data }
        

def filter_widget(
    filters: list = [],
    data: Union[dict, list] = {},
    containerClass: str = ""
    ):
    """    
    This component allow to filter any data object or array with a list of filters.
    For the moment, we have 2 types of filters: select and keyword.
    We have default values that avoid filter ("all" for select and "" for keyword).
    Filters are fields so we need to provide a "field" key with same structure as a Field.
    We have to define "keys" that will be the keys the filter value will check.
    We can set filter "default" in order to filter the base keys of an object.
    We can set filter "settings" in order to filter settings, data must be an advanced template.
    We can set filter "table" in order to filter table items.
    Check example for more details.
    
    PARAMETERS
    
    -   `filters` **array** Fields with additional data to be used as filters. (optional, default `[]`)
    -   `data` **(object | array)** Data object or array to filter. Emit a filter event with the filtered data. (optional, default `{}`)
    -   `containerClass` **string** Additional class for the container. (optional, default `""`)
    
    EXAMPLE
    
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
    
    """

    data = {
       }


    # List of params that will be add only if not default value
    list_params = [("filters", filters, []),("data", data, {}),("containerClass", containerClass, "")]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Filter", "data" : data }
        

def format_columns_widget(
    columns: list
    ):
    """    
    This will add some key to columns that can be passed from props like minWidth or maxWidth.
    Case key already exists, this will override it.
    
    PARAMETERS
    
    -   `columns` **array** The columns are the list of columns that we want to check.
    
    Returns **[array][3]** Return the columns with the custom sort added.
    
    """

    data = {
        "columns" : columns,
       }


    return { "type" : "Formatcolumns", "data" : data }
        

def grid_widget(
    gridClass: str = "items-start",
    display: list = []
    ):
    """    
    This component is a basic container that can be used to wrap other components.
    This container is based on a grid system and will return a grid container with 12 columns.
    We can define additional class too.
    This component is mainly use as widget container or as a child of a GridLayout.
    
    PARAMETERS
    
    -   `gridClass` **string** Additional class (optional, default `"items-start"`)
    -   `display` **array** Array need to be of format \["groupName", "compId"] in order to be displayed using the display store. More info on the display store itslef. (optional, default `[]`)
    
    EXAMPLE
    
    {
       columns: { pc: 12, tablet: 12, mobile: 12},
       gridClass: "items-start"
     }
    
    """

    data = {
       }


    # List of params that will be add only if not default value
    list_params = [("gridClass", gridClass, "items-start"),("display", display, [])]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Grid", "data" : data }
        

def grid_layout_widget(
    type: str = "card",
    id: str = "",
    title: str = "",
    link: str = "",
    columns: dict = {"pc":12,"tablet":12,"mobile":12},
    gridLayoutClass: str = "items-start",
    display: list = [],
    tabId: str = ""
    ):
    """    
    This component is used for top level page layout.
    This will determine the position of layout components based on the grid system.
    We can create card, modal, table and others top level layout using this component.
    This component is mainly use as Grid parent component.
    
    PARAMETERS
    
    -   `type` **string** Type of layout component, we can have "card" (optional, default `"card"`)
    -   `id` **string** Id of the layout component, will be used to identify the component. (optional, default `uuidv4()`)
    -   `title` **string** Title of the layout component, will be displayed at the top if exists. Type of layout component will determine the style of the title. (optional, default `""`)
    -   `link` **string** Will transform the container tag from a div to an a tag with the link as href. Useful with card type. (optional, default `""`)
    -   `columns` **object** Work with grid system { pc: 12, tablet: 12, mobile: 12} (optional, default `{"pc":12,"tablet":12,"mobile":12}`)
    -   `gridLayoutClass` **string** Additional class (optional, default `"items-start"`)
    -   `display` **array** Array need to be of format \["groupName", "compId"] in order to be displayed using the display store. More info on the display store itslef. (optional, default `[]`)
    -   `tabId` **string** Case the container is converted to an anchor with a link, we can define the tabId, by default it is the contentIndex (optional, default `contentIndex`)
    
    EXAMPLE
    
    {
       type: "card",
       title: "Test",
       columns: { pc: 12, tablet: 12, mobile: 12},
       gridLayoutClass: "items-start",
      display: ["main", 1],
     }
    
    """

    data = {
       }


    # List of params that will be add only if not default value
    list_params = [("type", type, "card"),("id", id, ""),("title", title, ""),("link", link, ""),("columns", columns, {"pc":12,"tablet":12,"mobile":12}),("gridLayoutClass", gridLayoutClass, "items-start"),("display", display, []),("tabId", tabId, "")]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Gridlayout", "data" : data }
        

def icons_widget(
    iconName: str,
    iconClass: str = "base",
    color: str = "",
    isStick: bool = False,
    disabled: bool = False
    ):
    """    
    This component is a wrapper that contains all the icons available in the application (Icons folder).
    This component is used to display the icon based on the icon name.
    This component is mainly use inside others widgets.
    
    PARAMETERS
    
    -   `iconName` **string** The name of the icon to display. The icon name is the name of the file without the extension on lowercase.
    -   `iconClass` **string** Class to apply to the icon. In case the icon is related to a widget, the widget will set the right class automatically. (optional, default `"base"`)
    -   `color` **string** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `""`)
    -   `isStick` **boolean** If true, the icon will be stick to the top right of the parent container. (optional, default `false`)
    -   `disabled` **boolean** If true, the icon will be disabled. (optional, default `false`)
    
    EXAMPLE
    
    {
       iconName: 'box',
       iconClass: 'base',
       color: 'amber',
     }
    
    """

    data = {
        "iconName" : iconName,
       }


    # List of params that will be add only if not default value
    list_params = [("iconClass", iconClass, "base"),("color", color, ""),("isStick", isStick, False),("disabled", disabled, False)]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Icons", "data" : data }
        

def input_widget(
    popovers,
    label: str,
    name: str,
    value: str,
    id: str = "",
    type: str = "text",
    attrs: dict = {},
    inpType: str = "input",
    columns: dict = {"pc":"12","tablet":"12","mobile":"12"},
    disabled: bool = False,
    required: bool = False,
    placeholder: str = "",
    pattern: str = "(?.*)",
    isClipboard: bool = True,
    readonly: bool = False,
    hideLabel: bool = False,
    containerClass: str = "",
    inpClass: str = "",
    headerClass: str = "",
    tabId: Union[str, int] = ""
    ):
    """    
    This component is used to create a complete input field input with error handling and label.
    We can add a clipboard button to copy the input value.
    We can also add a password button to show the password.
    We can also add popover to display more information.
    It is mainly use in forms.
    
    PARAMETERS
    
    -   `id` **string** Unique id (optional, default `uuidv4()`)
    -   `type` **string** text, email, password, number, tel, url (optional, default `"text"`)
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
    
    EXAMPLE
    
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
    
    """

    data = {
        "popovers" : popovers,
        "label" : label,
        "name" : name,
        "value" : value,
       }


    # List of params that will be add only if not default value
    list_params = [("id", id, ""),("type", type, "text"),("attrs", attrs, {}),("inpType", inpType, "input"),("columns", columns, {"pc":"12","tablet":"12","mobile":"12"}),("disabled", disabled, False),("required", required, False),("placeholder", placeholder, ""),("pattern", pattern, "(?.*)"),("isClipboard", isClipboard, True),("readonly", readonly, False),("hideLabel", hideLabel, False),("containerClass", containerClass, ""),("inpClass", inpClass, ""),("headerClass", headerClass, ""),("tabId", tabId, "")]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Input", "data" : data }
        

def instance_widget(
    title: str,
    status: str,
    details: list,
    buttons: list
    ):
    """    
    This component is an instance widget.
    This component is using the Container, TitleCard, IconStatus, ListPairs and ButtonGroup components.
    
    PARAMETERS
    
    -   `title` **string**;
    -   `status` **string**;
    -   `details` **array** List of details to display
    -   `buttons` **array** List of buttons to display
    
    EXAMPLE
    
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
    
    """

    data = {
        "title" : title,
        "status" : status,
        "details" : details,
        "buttons" : buttons,
       }


    return { "type" : "Instance", "data" : data }
        

def list_widget(
    popovers,
    label: str,
    name: str,
    value: str,
    id: str = "",
    attrs: dict = {},
    separator: str = " ",
    maxBtnChars: str = "",
    inpType: str = "list",
    disabled: bool = False,
    required: bool = False,
    columns: dict = {"pc":"12","tablet":"12","mobile":"12"},
    hideLabel: bool = False,
    onlyDown: bool = False,
    overflowAttrEl: bool = "",
    containerClass: str = "",
    inpClass: str = "",
    headerClass: str = "",
    tabId: Union[str, int] = ""
    ):
    """    
    This component is used display list of values in a dropdown, remove or add an item in an easy way.
    We can also add popover to display more information.
    
    PARAMETERS
    
    -   `id` **string** Unique id (optional, default `uuidv4()`)
    -   `label` **string** The label of the field. Can be a translation key or by default raw text.
    -   `name` **string** The name of the field. Case no label, this is the fallback. Can be a translation key or by default raw text.
    -   `value` **string**;
    -   `attrs` **object** Additional attributes to add to the field (optional, default `{}`)
    -   `separator` **string** Separator to split the value, by default it is a space (optional, default `" "`)
    -   `maxBtnChars` **string** Max char to display in the dropdown button handler. (optional, default `""`)
    -   `popovers` **array?** List of popovers to display more information
    -   `inpType` **string** The type of the field, useful when we have multiple fields in the same container to display the right field (optional, default `"list"`)
    -   `disabled` **boolean**  (optional, default `false`)
    -   `required` **boolean**  (optional, default `false`)
    -   `columns` **object** Field has a grid system. This allow to get multiple field in the same row if needed. (optional, default `{"pc":"12","tablet":"12","mobile":"12"}`)
    -   `hideLabel` **boolean**  (optional, default `false`)
    -   `onlyDown` **boolean** If the dropdown should stay down (optional, default `false`)
    -   `overflowAttrEl` **boolean** Attribute the element has to check for overflow (optional, default `""`)
    -   `containerClass` **string**  (optional, default `""`)
    -   `inpClass` **string**  (optional, default `""`)
    -   `headerClass` **string**  (optional, default `""`)
    -   `tabId` **(string | number)** The tabindex of the field, by default it is the contentIndex (optional, default `contentIndex`)
    
    EXAMPLE
    
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
    
    """

    data = {
        "popovers" : popovers,
        "label" : label,
        "name" : name,
        "value" : value,
       }


    # List of params that will be add only if not default value
    list_params = [("id", id, ""),("attrs", attrs, {}),("separator", separator, " "),("maxBtnChars", maxBtnChars, ""),("inpType", inpType, "list"),("disabled", disabled, False),("required", required, False),("columns", columns, {"pc":"12","tablet":"12","mobile":"12"}),("hideLabel", hideLabel, False),("onlyDown", onlyDown, False),("overflowAttrEl", overflowAttrEl, ""),("containerClass", containerClass, ""),("inpClass", inpClass, ""),("headerClass", headerClass, ""),("tabId", tabId, "")]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "List", "data" : data }
        

def modal_widget(
    widgets: list
    ):
    """    
    This component contains all widgets needed on a modal.
    This is different from a page builder as we don't need to define the container and grid layout.
    We can't create multiple grids or containers in a modal.
    
    PARAMETERS
    
    -   `widgets` **array** Array of containers and widgets
    
    EXAMPLE
    
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
    
    """

    data = {
        "widgets" : widgets,
       }


    return { "type" : "Modal", "data" : data }
        

def multiple_widget(
    multiples: dict,
    columns: dict = {"pc":"12","tablet":"12","mobile":"12"},
    containerClass: str = "",
    tadId: str = ""
    ):
    """    
    This Will regroup all multiples settings with add and remove logic.
    This component under the hood is rendering default fields but by group with possibility to add or remove a multiple group.
    
    PARAMETERS
    
    -   `multiples` **object** The multiples settings to display. This needs to be a dict of settings using default field format.
    -   `columns` **object** Field has a grid system. This allow to get multiple field in the same row if needed. (optional, default `{"pc":"12","tablet":"12","mobile":"12"}`)
    -   `containerClass` **string** Additionnal class to add to the container (optional, default `""`)
    -   `tadId` **string** The tabindex of the field, by default it is the contentIndex (optional, default `contentIndex`)
    
    EXAMPLE
    
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
    
    """

    data = {
        "multiples" : multiples,
       }


    # List of params that will be add only if not default value
    list_params = [("columns", columns, {"pc":"12","tablet":"12","mobile":"12"}),("containerClass", containerClass, ""),("tadId", tadId, "")]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Multiple", "data" : data }
        

def pairs_widget(
    pairs: list,
    columns: dict = {"pc":"12","tablet":"12","mobile":"12"}
    ):
    """    
    This component is used to display key value information in a list.
    
    PARAMETERS
    
    -   `pairs` **array** The list of key value information. The key and value can be a translation key or a raw text.
    -   `columns` **object** Determine the  position of the items in the grid system. (optional, default `{"pc":"12","tablet":"12","mobile":"12"}`)
    
    EXAMPLE
    
    {
       pairs : [
                 { key: "Total Users", value: "100" }
               ],
       columns: { pc: 12, tablet: 12, mobile: 12 }
     }
    
    """

    data = {
        "pairs" : pairs,
       }


    # List of params that will be add only if not default value
    list_params = [("columns", columns, {"pc":"12","tablet":"12","mobile":"12"})]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Pairs", "data" : data }
        

def popover_widget(
    text: str,
    color: str,
    href: str = "#",
    attrs: dict = {},
    tag: str = "a",
    iconClass: str = "icon-default",
    tabId: Union[str, int] = ""
    ):
    """    
    This component is a standard popover.
    
    PARAMETERS
    
    -   `text` **string** Content of the popover. Can be a translation key or by default raw text.
    -   `href` **string** Link of the anchor. By default it is a # link. (optional, default `"#"`)
    -   `color` **string** Color of the icon between tailwind colors
    -   `attrs` **object** List of attributs to add to the text. (optional, default `{}`)
    -   `tag` **string** By default it is a anchor tag, but we can use other tag like div in case of popover on another anchor (optional, default `"a"`)
    -   `iconClass` **string**  (optional, default `"icon-default"`)
    -   `tabId` **(string | number)** The tabindex of the field, by default it is the contentIndex (optional, default `contentIndex`)
    
    EXAMPLE
    
    {
       text: "This is a popover text",
       href: "#",
       iconName: "info",
       attrs: { "data-popover": "test" },
     }
    
    """

    data = {
        "text" : text,
        "color" : color,
       }


    # List of params that will be add only if not default value
    list_params = [("href", href, "#"),("attrs", attrs, {}),("tag", tag, "a"),("iconClass", iconClass, "icon-default"),("tabId", tabId, "")]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Popover", "data" : data }
        

def popover_group_widget(
    popovers: list,
    groupClasss: str = ""
    ):
    """    
    This component allow to display multiple popovers in the same row using flex.
    We can define additional class too for the flex container.
    We need a list of popovers to display.
    
    PARAMETERS
    
    -   `popovers` **array** List of popovers to display. Popover component is used.
    -   `groupClasss` **string** Additional class for the flex container (optional, default `""`)
    
    EXAMPLE
    
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
    
    """

    data = {
        "popovers" : popovers,
       }


    # List of params that will be add only if not default value
    list_params = [("groupClasss", groupClasss, "")]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Popovergroup", "data" : data }
        

def raw_widget(
    template: dict,
    containerClass: str,
    columns: dict,
    operation: str = "edit",
    oldServerName: str = ""
    ):
    """    
    This component is used to create a complete raw form with settings as JSON format.
    
    PARAMETERS
    
    -   `template` **object** Template object with plugin and settings data.
    -   `operation` **string** Operation type (edit, new, delete). (optional, default `"edit"`)
    -   `oldServerName` **string** Old server name. This is a server name before any changes. (optional, default `""`)
    -   `containerClass` **string** Container
    -   `columns` **object** Columns object.
    
    EXAMPLE
    
    {
       "IS_LOADING": "no",
       "NGINX_PREFIX": "/etc/nginx/",
       "HTTP_PORT": "8080",
       "HTTPS_PORT": "8443",
       "MULTISITE": "yes"
      }
    
    """

    data = {
        "template" : template,
        "containerClass" : containerClass,
        "columns" : columns,
       }


    # List of params that will be add only if not default value
    list_params = [("operation", operation, "edit"),("oldServerName", oldServerName, "")]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Raw", "data" : data }
        

def select_widget(
    popovers,
    label: str,
    name: str,
    value: str,
    values: list,
    id: str = "",
    attrs: dict = {},
    inpType: str = "select",
    maxBtnChars: str = "",
    disabled: bool = False,
    required: bool = False,
    requiredValues: list = [],
    columns: dict = {"pc":"12","tablet":"12","mobile":"12"},
    hideLabel: bool = False,
    onlyDown: bool = False,
    overflowAttrEl: bool = "",
    containerClass: str = "",
    inpClass: str = "",
    headerClass: str = "",
    tabId: Union[str, int] = ""
    ):
    """    
    This component is used to create a complete select field input with error handling and label.
    We can be more precise by adding values that need to be selected to be valid.
    We can also add popover to display more information.
    It is mainly use in forms.
    
    PARAMETERS
    
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
    
    EXAMPLE
    
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
    
    """

    data = {
        "popovers" : popovers,
        "label" : label,
        "name" : name,
        "value" : value,
        "values" : values,
       }


    # List of params that will be add only if not default value
    list_params = [("id", id, ""),("attrs", attrs, {}),("inpType", inpType, "select"),("maxBtnChars", maxBtnChars, ""),("disabled", disabled, False),("required", required, False),("requiredValues", requiredValues, []),("columns", columns, {"pc":"12","tablet":"12","mobile":"12"}),("hideLabel", hideLabel, False),("onlyDown", onlyDown, False),("overflowAttrEl", overflowAttrEl, ""),("containerClass", containerClass, ""),("inpClass", inpClass, ""),("headerClass", headerClass, ""),("tabId", tabId, "")]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Select", "data" : data }
        

def stat_widget(
    title: str,
    stat: Union[str, int],
    subtitle: str = "",
    iconName: str = "",
    subtitleColor: str = "info",
    statClass: str = ""
    ):
    """    
    This component is wrapper of all stat components.
    This component has no grid system and will always get the full width of the parent.
    This component is mainly use inside a blank card.
    
    PARAMETERS
    
    -   `title` **string** The title of the stat. Can be a translation key or by default raw text.
    -   `stat` **(string | number)** The value
    -   `subtitle` **string** The subtitle of the stat. Can be a translation key or by default raw text. (optional, default `""`)
    -   `iconName` **string** A top-right icon to display between icon available in Icons/Stat. Case falsy value, no icon displayed. The icon name is the name of the file without the extension on lowercase. (optional, default `""`)
    -   `subtitleColor` **string** The color of the subtitle between error, success, warning, info (optional, default `"info"`)
    -   `statClass` **string** Additional class (optional, default `""`)
    
    EXAMPLE
    
    {
       title: "Total Users",
       value: 100,
       subtitle : "Last 30 days",
       iconName: "user",
       link: "/users",
       subtitleColor: "info",
     }
    
    """

    data = {
        "title" : title,
        "stat" : stat,
       }


    # List of params that will be add only if not default value
    list_params = [("subtitle", subtitle, ""),("iconName", iconName, ""),("subtitleColor", subtitleColor, "info"),("statClass", statClass, "")]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Stat", "data" : data }
        

def status_widget(
    id: str,
    status: str = "info",
    statusClass: str = ""
    ):
    """    
    This component is a icon used with status.
    
    PARAMETERS
    
    -   `id` **string** The id of the status icon.
    -   `status` **string** The color of the icon between error, success, warning, info (optional, default `"info"`)
    -   `statusClass` **string** Additional class, for example to use with grid system. (optional, default `""`)
    
    EXAMPLE
    
    {
       id: "instance-1",
       status: "success",
       statusClass: "col-span-12",
     }
    
    """

    data = {
        "id" : id,
       }


    # List of params that will be add only if not default value
    list_params = [("status", status, "info"),("statusClass", statusClass, "")]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Status", "data" : data }
        

def subtitle_widget(
    subtitle: str,
    type: str = "card",
    tag: str = "",
    color: str = "",
    bold: bool = False,
    uppercase: bool = False,
    lowercase: bool = False,
    subtitleClass: str = ""
    ):
    """    
    This component is a general subtitle wrapper.
    
    PARAMETERS
    
    -   `subtitle` **string** Can be a translation key or by default raw text.
    -   `type` **string** The type of title between "container", "card", "content", "min" or "stat" (optional, default `"card"`)
    -   `tag` **string** The tag of the subtitle. Can be h1, h2, h3, h4, h5, h6 or p. If empty, will be determine by the type of subtitle. (optional, default `""`)
    -   `color` **string** The color of the subtitle between error, success, warning, info or tailwind color (optional, default `""`)
    -   `bold` **boolean** If the subtitle should be bold or not. (optional, default `false`)
    -   `uppercase` **boolean** If the subtitle should be uppercase or not. (optional, default `false`)
    -   `lowercase` **boolean** If the subtitle should be lowercase or not. (optional, default `false`)
    -   `subtitleClass` **string** Additional class, useful when component is used directly on a grid system (optional, default `""`)
    
    EXAMPLE
    
    {
       subtitle: "Total Users",
       type: "card",
       subtitleClass: "text-lg",
       color : "info",
       tag: "h2"
     }
    
    """

    data = {
        "subtitle" : subtitle,
       }


    # List of params that will be add only if not default value
    list_params = [("type", type, "card"),("tag", tag, ""),("color", color, ""),("bold", bold, False),("uppercase", uppercase, False),("lowercase", lowercase, False),("subtitleClass", subtitleClass, "")]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Subtitle", "data" : data }
        

def table_widget(
    title: str,
    header: list,
    positions: list,
    items: list,
    filters: list = [],
    minWidth: str = "base",
    containerClass: str = "",
    containerWrapClass: str = "",
    tableClass: str = ""
    ):
    """    
    This component is used to create a table.
    You need to provide a title, a header, a list of positions, and a list of items.
    Items need to be an array of array with a cell being a regular widget. Not all widget are supported. Check this component import list to see which widget are supported.
    For example, Text, Icons, Icons, Buttons and Fields are supported.
    
    PARAMETERS
    
    -   `title` **string** Determine the title of the table.
    -   `header` **array** Determine the header of the table.
    -   `positions` **array** Determine the position of each item in the table in a list of number based on 12 columns grid.
    -   `items` **array** items to render in the table. This need to be an array (row) of array (cols) with a cell being a regular widget.
    -   `filters` **array** Determine the filters of the table. (optional, default `[]`)
    -   `minWidth` **string** Determine the minimum size of the table. Can be "base", "sm", "md", "lg", "xl". (optional, default `"base"`)
    -   `containerClass` **string** Container additional class. (optional, default `""`)
    -   `containerWrapClass` **string** Container wrap additional class. (optional, default `""`)
    -   `tableClass` **string** Table additional class. (optional, default `""`)
    
    EXAMPLE
    
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
    
    """

    data = {
        "title" : title,
        "header" : header,
        "positions" : positions,
        "items" : items,
       }


    # List of params that will be add only if not default value
    list_params = [("filters", filters, []),("minWidth", minWidth, "base"),("containerClass", containerClass, ""),("containerWrapClass", containerWrapClass, ""),("tableClass", tableClass, "")]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Table", "data" : data }
        

def templates_widget(
    templates: dict,
    operation: str = "edit",
    oldServerName: str = ""
    ):
    """    
    This component is used to create a complete  settings form with all modes (advanced, raw, easy).
    
    PARAMETERS
    
    -   `templates` **object** List of advanced templates that contains settings. Must be a dict with mode as key, then the template name as key with a list of data (different for each modes).
    -   `operation` **string** Operation type (edit, new, delete). (optional, default `"edit"`)
    -   `oldServerName` **string** Old server name. This is a server name before any changes. (optional, default `""`)
    
    EXAMPLE
    
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
    
    """

    data = {
        "templates" : templates,
       }


    # List of params that will be add only if not default value
    list_params = [("operation", operation, "edit"),("oldServerName", oldServerName, "")]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Templates", "data" : data }
        

def text_widget(
    text: str,
    textClass: str = "",
    color: str = "",
    bold: bool = False,
    uppercase: bool = False,
    tag: str = "p",
    icon: Union[bool, dict] = False,
    attrs: dict = {}
    ):
    """    
    This component is used for regular paragraph.
    
    PARAMETERS
    
    -   `text` **string** The text value. Can be a translation key or by default raw text.
    -   `textClass` **string** Style of text. Can be replace by any class starting by 'text-' like 'text-stat'. (optional, default `""`)
    -   `color` **string** The color of the text between error, success, warning, info or tailwind color (optional, default `""`)
    -   `bold` **boolean** If the text should be bold or not. (optional, default `false`)
    -   `uppercase` **boolean** If the text should be uppercase or not. (optional, default `false`)
    -   `tag` **string** The tag of the text. Can be p, span, div, h1, h2, h3, h4, h5, h6 (optional, default `"p"`)
    -   `icon` **(boolean | object)** The icon to add before the text. If true, will add a default icon. If object, will add the icon with the name and the color. (optional, default `false`)
    -   `attrs` **object** List of attributes to add to the text. (optional, default `{}`)
    
    EXAMPLE
    
    {
       text: "This is a paragraph",
       textClass: "text-3xl"
       attrs: { id: "paragraph" },
     }
    
    """

    data = {
        "text" : text,
       }


    # List of params that will be add only if not default value
    list_params = [("textClass", textClass, ""),("color", color, ""),("bold", bold, False),("uppercase", uppercase, False),("tag", tag, "p"),("icon", icon, False),("attrs", attrs, {})]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Text", "data" : data }
        

def title_widget(
    title: str,
    type: str = "card",
    tag: str = "",
    color: str = "",
    uppercase: bool = False,
    lowercase: bool = False,
    titleClass: str = ""
    ):
    """    
    This component is a general title wrapper.
    
    PARAMETERS
    
    -   `title` **string** Can be a translation key or by default raw text.
    -   `type` **string** The type of title between "container", "card", "content", "min" or "stat" (optional, default `"card"`)
    -   `tag` **string** The tag of the title. Can be h1, h2, h3, h4, h5, h6 or p. If empty, will be determine by the type of title. (optional, default `""`)
    -   `color` **string** The color of the title between error, success, warning, info or tailwind color (optional, default `""`)
    -   `uppercase` **boolean** If the title should be uppercase or not. (optional, default `false`)
    -   `lowercase` **boolean** If the title should be lowercase or not. (optional, default `false`)
    -   `titleClass` **string** Additional class, useful when component is used directly on a grid system (optional, default `""`)
    
    EXAMPLE
    
    {
       title: "Total Users",
       type: "card",
       titleClass: "text-lg",
       color : "info",
       tag: "h2"
     }
    
    """

    data = {
        "title" : title,
       }


    # List of params that will be add only if not default value
    list_params = [("type", type, "card"),("tag", tag, ""),("color", color, ""),("uppercase", uppercase, False),("lowercase", lowercase, False),("titleClass", titleClass, "")]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Title", "data" : data }
        

def unmatch_widget(
    text: str,
    unmatchClass: str = ""
    ):
    """    
    Display a default message "no match" with dedicated icon.
    The message text can be overridden by passing a text prop.
    
    PARAMETERS
    
    -   `text` **string** The text to display
    -   `unmatchClass` **string** The class to apply to the message. If not provided, the class will be based on the parent component. (optional, default `""`)
    
    EXAMPLE
    
    {
       text: "dashboard_no_match",
     }
    
    """

    data = {
        "text" : text,
       }


    # List of params that will be add only if not default value
    list_params = [("unmatchClass", unmatchClass, "")]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Unmatch", "data" : data }
        
