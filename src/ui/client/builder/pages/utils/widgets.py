
from typing import Union, Optional

# Add params to data dict only if value is not the default one
def add_key_value(data, key, value, default):
    if value == default:
        return
    data[key] = value
        
def advanced_widget(
    template: dict,
    containerClass: str = "",
    operation: str = "edit",
    endpoint: str = "",
    method: str = "POST",
    oldServerName: str = "",
    columns: dict = {"pc":"12","tablet":"12","mobile":"12"},
    display: Optional[list] = None
    ):
    """    
    This component is used to create a complete advanced form with plugin selection.
    
    PARAMETERS
    
    -   `template` **Object** Template object with plugin and settings data.
    -   `containerClass` **String** Container additional class (optional, default `""`)
    -   `operation` **String** Operation type (edit, new, delete). (optional, default `"edit"`)
    -   `endpoint` **String** Form endpoint. Case none, will be ignored. (optional, default `""`)
    -   `method` **String** Http method to be used on form submit. (optional, default `"POST"`)
    -   `oldServerName` **String** Old server name. This is a server name before any changes. (optional, default `""`)
    -   `columns` **Object** Columns object. (optional, default `{"pc":"12","tablet":"12","mobile":"12"}`)
    -   `display` **Array** Array need two values : "groupName" in index 0 and "compId" in index 1 in order to be displayed using the display store. More info on the display store itslef. (optional, default `[]`)
    
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
       }


    # List of params that will be add only if not default value
    list_params = [("containerClass", containerClass, ""),("operation", operation, "edit"),("endpoint", endpoint, ""),("method", method, "POST"),("oldServerName", oldServerName, ""),("columns", columns, {"pc":"12","tablet":"12","mobile":"12"}),("display", display, None)]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Advanced", "data" : data }
        

def button_widget(
    text: str,
    id: str = "",
    display: Optional[list] = None,
    type: str = "button",
    disabled: bool = False,
    hideText: bool = False,
    color: str = "primary",
    iconColor: str = "",
    size: str = "normal",
    iconName: str = "",
    attrs: Optional[dict] = None,
    modal: Union[dict, bool] = False,
    tabId: Union[str, int] = "",
    containerClass: str = ""
    ):
    """    
    This component is a standard button.
    
    PARAMETERS
    
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
    list_params = [("id", id, ""),("display", display, None),("type", type, "button"),("disabled", disabled, False),("hideText", hideText, False),("color", color, "primary"),("iconColor", iconColor, ""),("size", size, "normal"),("iconName", iconName, ""),("attrs", attrs, None),("modal", modal, False),("tabId", tabId, ""),("containerClass", containerClass, "")]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Button", "data" : data }
        

def button_group_widget(
    buttons: list,
    buttonGroupClass: str = ""
    ):
    """    
    This component allow to display multiple buttons in the same row using flex.
    We can define additional class too for the flex container.
    We need a list of buttons to display.
    
    PARAMETERS
    
    -   `buttons` **Array** List of buttons to display. Button component is used.
    -   `buttonGroupClass` **String** Additional class for the flex container (optional, default `""`)
    
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
    list_params = [("buttonGroupClass", buttonGroupClass, "")]
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
    
    -   `type` **String** The type of the cell. This needs to be a Vue component.
    -   `data` **Object** The data to display in the cell. This needs to be the props of the Vue component.
    
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
    label: str,
    name: str,
    value: str,
    id: str = "",
    attrs: Optional[dict] = None,
    popovers: Optional[list] = None,
    inpType: str = "checkbox",
    disabled: bool = False,
    required: bool = False,
    columns: dict = {"pc":"12","tablet":"12","mobile":"12"},
    hideLabel: bool = False,
    containerClass: str = "",
    headerClass: str = "",
    inpClass: str = "",
    fieldSize: str = "normal",
    tabId: Union[str, int] = "",
    showErrMsg: bool = False
    ):
    """    
    This component is used to create a complete checkbox field input with error handling and label.
    We can also add popover to display more information.
    It is mainly use in forms.
    
    PARAMETERS
    
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
        "label" : label,
        "name" : name,
        "value" : value,
       }


    # List of params that will be add only if not default value
    list_params = [("id", id, ""),("attrs", attrs, None),("popovers", popovers, None),("inpType", inpType, "checkbox"),("disabled", disabled, False),("required", required, False),("columns", columns, {"pc":"12","tablet":"12","mobile":"12"}),("hideLabel", hideLabel, False),("containerClass", containerClass, ""),("headerClass", headerClass, ""),("inpClass", inpClass, ""),("fieldSize", fieldSize, "normal"),("tabId", tabId, ""),("showErrMsg", showErrMsg, False)]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Checkbox", "data" : data }
        

def clipboard_widget(
    id: str = "",
    isClipboard: bool = False,
    valueToCopy: str = "",
    clipboadClass: str = "",
    copyClass: str = "",
    fieldSize: str = "normal"
    ):
    """    
    This component can be add to some fields to allow to copy the value of the field.
    Additional clipboardClass and copyClass can be added to fit the parent container.
    
    PARAMETERS
    
    -   `id` **String** Unique id (optional, default `uuidv4()`)
    -   `isClipboard` **Boolean** Display a clipboard button to copy a value (optional, default `false`)
    -   `valueToCopy` **String** The value to copy (optional, default `""`)
    -   `clipboadClass` **String** Additional class for the clipboard container. Useful to fit the component in a specific container. (optional, default `""`)
    -   `copyClass` **String** The class of the copy message. Useful to fit the component in a specific container. (optional, default `""`)
    -   `fieldSize` **String** Size between "normal" or "sm" (optional, default `"normal"`)
    
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
    list_params = [("id", id, ""),("isClipboard", isClipboard, False),("valueToCopy", valueToCopy, ""),("clipboadClass", clipboadClass, ""),("copyClass", copyClass, ""),("fieldSize", fieldSize, "normal")]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Clipboard", "data" : data }
        

def combobox_widget(
    label: str,
    name: str,
    value: str,
    values: list,
    id: str = "",
    attrs: Optional[dict] = None,
    maxBtnChars: str = "",
    popovers: Optional[list] = None,
    inpType: str = "select",
    disabled: bool = False,
    required: bool = False,
    requiredValues: Optional[list] = None,
    columns: dict = {"pc":"12","tablet":"12","mobile":"12"},
    hideLabel: bool = False,
    onlyDown: bool = False,
    overflowAttrEl: bool = "",
    containerClass: str = "",
    inpClass: str = "",
    fieldSize: str = "normal",
    headerClass: str = "",
    tabId: Union[str, int] = "",
    showErrMsg: bool = False
    ):
    """    
    This component is used to create a complete combobox field input with error handling and label.
    We can be more precise by adding values that need to be selected to be valid.
    We can also add popover to display more information.
    
    PARAMETERS
    
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
        "label" : label,
        "name" : name,
        "value" : value,
        "values" : values,
       }


    # List of params that will be add only if not default value
    list_params = [("id", id, ""),("attrs", attrs, None),("maxBtnChars", maxBtnChars, ""),("popovers", popovers, None),("inpType", inpType, "select"),("disabled", disabled, False),("required", required, False),("requiredValues", requiredValues, None),("columns", columns, {"pc":"12","tablet":"12","mobile":"12"}),("hideLabel", hideLabel, False),("onlyDown", onlyDown, False),("overflowAttrEl", overflowAttrEl, ""),("containerClass", containerClass, ""),("inpClass", inpClass, ""),("fieldSize", fieldSize, "normal"),("headerClass", headerClass, ""),("tabId", tabId, ""),("showErrMsg", showErrMsg, False)]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Combobox", "data" : data }
        

def container_widget(
    containerClass: str = "",
    columns: Union[dict, bool] = {"pc":"12","tablet":"12","mobile":"12"},
    tag: str = "div",
    display: Optional[list] = None
    ):
    """    
    This component is a basic container that can be used to wrap other components.
    In case we are working with grid system, we can add columns to position the container.
    We can define additional class too.
    This component is mainly use as widget container.
    
    PARAMETERS
    
    -   `containerClass` **String** Additional class (optional, default `""`)
    -   `columns` **(Object | boolean)** Work with grid system { pc: 12, tablet: 12, mobile: 12} (optional, default `{"pc":"12","tablet":"12","mobile":"12"}`)
    -   `tag` **String** The tag for the container (optional, default `"div"`)
    -   `display` **Array** Array need two values : "groupName" in index 0 and "compId" in index 1 in order to be displayed using the display store. More info on the display store itslef. (optional, default `[]`)
    
    EXAMPLE
    
    {
       containerClass: "w-full h-full bg-white rounded shadow-md",
       columns: { pc: 12, tablet: 12, mobile: 12}
     }
    
    """

    data = {
       }


    # List of params that will be add only if not default value
    list_params = [("containerClass", containerClass, ""),("columns", columns, {"pc":"12","tablet":"12","mobile":"12"}),("tag", tag, "div"),("display", display, None)]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Container", "data" : data }
        

def datepicker_widget(
    label: str,
    name: str,
    id: str = "",
    popovers: Optional[list] = None,
    attrs: Optional[dict] = None,
    inpType: str = "datepicker",
    value: int = "",
    minDate: int = "",
    maxDate: int = "",
    isClipboard: bool = True,
    hideLabel: bool = False,
    columns: dict = {"pc":"12","tablet":"12","mobile":"12"},
    disabled: bool = False,
    required: bool = False,
    headerClass: str = "",
    containerClass: str = "",
    fieldSize: str = "normal",
    tabId: Union[str, int] = "",
    showErrMsg: bool = False
    ):
    """    
    This component is used to create a complete datepicker field input with error handling and label.
    You can define a default date, a min and max date, and a format.
    We can also add popover to display more information.
    It is mainly use in forms.
    
    PARAMETERS
    
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
       }


    # List of params that will be add only if not default value
    list_params = [("id", id, ""),("popovers", popovers, None),("attrs", attrs, None),("inpType", inpType, "datepicker"),("value", value, ""),("minDate", minDate, ""),("maxDate", maxDate, ""),("isClipboard", isClipboard, True),("hideLabel", hideLabel, False),("columns", columns, {"pc":"12","tablet":"12","mobile":"12"}),("disabled", disabled, False),("required", required, False),("headerClass", headerClass, ""),("containerClass", containerClass, ""),("fieldSize", fieldSize, "normal"),("tabId", tabId, ""),("showErrMsg", showErrMsg, False)]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Datepicker", "data" : data }
        

def details_widget(
    columns,
    details: str,
    filters: Optional[list] = None
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
    list_params = [("columns", columns, {"pc":"4","tablet":"6","mobile":"12"}),("filters", filters, None)]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Details", "data" : data }
        

def easy_widget(
    template: dict,
    containerClass: str = "",
    operation: str = "edit",
    endpoint: str = "",
    method: str = "POST",
    oldServerName: str = "",
    columns: dict = {"pc":"12","tablet":"12","mobile":"12"},
    display: Optional[list] = None
    ):
    """    
    This component is used to create a complete easy form with plugin selection.
    
    PARAMETERS
    
    -   `template` **Object** Template object with plugin and settings data.
    -   `containerClass` **String** Container additional class (optional, default `""`)
    -   `operation` **String** Operation type (edit, new, delete). (optional, default `"edit"`)
    -   `endpoint` **String** Form endpoint. Case none, will be ignored. (optional, default `""`)
    -   `method` **String** Http method to be used on form submit. (optional, default `"POST"`)
    -   `oldServerName` **String** Old server name. This is a server name before any changes. (optional, default `""`)
    -   `columns` **Object** Columns object. (optional, default `{"pc":"12","tablet":"12","mobile":"12"}`)
    -   `display` **Array** Array need two values : "groupName" in index 0 and "compId" in index 1 in order to be displayed using the display store. More info on the display store itslef. (optional, default `[]`)
    
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
       }


    # List of params that will be add only if not default value
    list_params = [("containerClass", containerClass, ""),("operation", operation, "edit"),("endpoint", endpoint, ""),("method", method, "POST"),("oldServerName", oldServerName, ""),("columns", columns, {"pc":"12","tablet":"12","mobile":"12"}),("display", display, None)]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Easy", "data" : data }
        

def editor_widget(
    label: str,
    name: str,
    value: str,
    id: str = "",
    attrs: Optional[dict] = None,
    popovers: Optional[list] = None,
    inpType: str = "editor",
    columns: dict = {"pc":"12","tablet":"12","mobile":"12"},
    pattern: str = "",
    disabled: bool = False,
    required: bool = False,
    isClipboard: bool = True,
    hideLabel: bool = False,
    containerClass: str = "",
    inpClass: str = "",
    headerClass: str = "",
    tabId: Union[str, int] = "",
    fieldSize: str = "normal",
    showErrMsg: bool = False
    ):
    """    
    This component is used to create a complete editor field  with error handling and label.
    We can also add popover to display more information.
    It is mainly use in forms.
    
    PARAMETERS
    
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
        "label" : label,
        "name" : name,
        "value" : value,
       }


    # List of params that will be add only if not default value
    list_params = [("id", id, ""),("attrs", attrs, None),("popovers", popovers, None),("inpType", inpType, "editor"),("columns", columns, {"pc":"12","tablet":"12","mobile":"12"}),("pattern", pattern, ""),("disabled", disabled, False),("required", required, False),("isClipboard", isClipboard, True),("hideLabel", hideLabel, False),("containerClass", containerClass, ""),("inpClass", inpClass, ""),("headerClass", headerClass, ""),("tabId", tabId, ""),("fieldSize", fieldSize, "normal"),("showErrMsg", showErrMsg, False)]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Editor", "data" : data }
        

def field_widget(
    label: str,
    id: str,
    name: str,
    popovers: Optional[list] = None,
    required: bool = False,
    hideLabel: bool = False,
    headerClass: str = "",
    fieldSize: str = "normal"
    ):
    """    
    This component is used with field in order to link a label to field type.
    We can add popover to display more information.
    Always use with field component.
    
    PARAMETERS
    
    -   `label` **String** The label of the field. Can be a translation key or by default raw text.
    -   `id` **String** The id of the field. This is used to link the label to the field.
    -   `name` **String** The name of the field. Case no label, this is the fallback. Can be a translation key or by default raw text.
    -   `popovers` **Array** List of popovers to display more information (optional, default `[]`)
    -   `required` **Boolean**  (optional, default `false`)
    -   `hideLabel` **Boolean**  (optional, default `false`)
    -   `headerClass` **String**  (optional, default `""`)
    -   `fieldSize` **String** Size between "normal" or "sm" inherit from field (optional, default `"normal"`)
    
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
        "label" : label,
        "id" : id,
        "name" : name,
       }


    # List of params that will be add only if not default value
    list_params = [("popovers", popovers, None),("required", required, False),("hideLabel", hideLabel, False),("headerClass", headerClass, ""),("fieldSize", fieldSize, "normal")]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Field", "data" : data }
        

def fields_widget(
    setting: dict
    ):
    """    
    This component wraps all available fields for a form.
    
    PARAMETERS
    
    -   `setting` **Object** Setting needed to render a field.
    
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
        

def file_manager_widget(
    data: dict,
    baseFolder: str = "base",
    columns: dict = {"pc":"12","tablet":"12","mobile":"12"},
    containerClass: str = ""
    ):
    """    
    File manager component. Useful with cache page.
    
    PARAMETERS
    
    -   `data` **Object** Can be a translation key or by default raw text.
    -   `baseFolder` **String** The base folder to display by default (optional, default `"base"`)
    -   `columns` **Object** Work with grid system { pc: 12, tablet: 12, mobile: 12} (optional, default `{"pc":"12","tablet":"12","mobile":"12"}`)
    -   `containerClass` **String** Additional class (optional, default `""`)
    
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
        "data" : data,
       }


    # List of params that will be add only if not default value
    list_params = [("baseFolder", baseFolder, "base"),("columns", columns, {"pc":"12","tablet":"12","mobile":"12"}),("containerClass", containerClass, "")]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Filemanager", "data" : data }
        

def filter_widget(
    filters: Optional[list] = None,
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
    
    -   `filters` **Array** Fields with additional data to be used as filters. (optional, default `[]`)
    -   `data` **(Object | Array)** Data object or array to filter. Emit a filter event with the filtered data. (optional, default `{}`)
    -   `containerClass` **String** Additional class for the container. (optional, default `""`)
    
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
    list_params = [("filters", filters, None),("data", data, {}),("containerClass", containerClass, "")]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Filter", "data" : data }
        

def grid_widget(
    gridClass: str = "items-start",
    display: Optional[list] = None
    ):
    """    
    This component is a basic container that can be used to wrap other components.
    This container is based on a grid system and will return a grid container with 12 columns.
    We can define additional class too.
    This component is mainly use as widget container or as a child of a GridLayout.
    
    PARAMETERS
    
    -   `gridClass` **String** Additional class (optional, default `"items-start"`)
    -   `display` **Array** Array need two values : "groupName" in index 0 and "compId" in index 1 in order to be displayed using the display store. More info on the display store itslef. (optional, default `[]`)
    
    EXAMPLE
    
    {
       columns: { pc: 12, tablet: 12, mobile: 12},
       gridClass: "items-start"
     }
    
    """

    data = {
       }


    # List of params that will be add only if not default value
    list_params = [("gridClass", gridClass, "items-start"),("display", display, None)]
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
    display: Optional[list] = None,
    tabId: str = "",
    maxWidthScreen: str = "2xl"
    ):
    """    
    This component is used for top level page layout.
    This will determine the position of layout components based on the grid system.
    We can create card, modal, table and others top level layout using this component.
    This component is mainly use as Grid parent component.
    
    PARAMETERS
    
    -   `type` **String** Type of layout component, we can have "card" (optional, default `"card"`)
    -   `id` **String** Id of the layout component, will be used to identify the component. (optional, default `uuidv4()`)
    -   `title` **String** Title of the layout component, will be displayed at the top if exists. Type of layout component will determine the style of the title. (optional, default `""`)
    -   `link` **String** Will transform the container tag from a div to an a tag with the link as href. Useful with card type. (optional, default `""`)
    -   `columns` **Object** Work with grid system { pc: 12, tablet: 12, mobile: 12} (optional, default `{"pc":12,"tablet":12,"mobile":12}`)
    -   `gridLayoutClass` **String** Additional class (optional, default `"items-start"`)
    -   `display` **Array** Array need two values : "groupName" in index 0 and "compId" in index 1 in order to be displayed using the display store. More info on the display store itslef. (optional, default `[]`)
    -   `tabId` **String** Case the container is converted to an anchor with a link, we can define the tabId, by default it is the contentIndex (optional, default `contentIndex`)
    -   `maxWidthScreen` **String** Max screen width for the settings based on the breakpoint (xs, sm, md, lg, xl, 2xl, 3xl) (optional, default `"2xl"`)
    
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
    list_params = [("type", type, "card"),("id", id, ""),("title", title, ""),("link", link, ""),("columns", columns, {"pc":12,"tablet":12,"mobile":12}),("gridLayoutClass", gridLayoutClass, "items-start"),("display", display, None),("tabId", tabId, ""),("maxWidthScreen", maxWidthScreen, "2xl")]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Gridlayout", "data" : data }
        

def icons_widget(
    value,
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
    
    -   `iconName` **String** The name of the icon to display. The icon name is the name of the file without the extension on lowercase.
    -   `iconClass` **String** Class to apply to the icon. In case the icon is related to a widget, the widget will set the right class automatically. (optional, default `"base"`)
    -   `color` **String** The color of the icon between some tailwind css available colors (purple, green, red, orange, blue, yellow, gray, dark, amber, emerald, teal, indigo, cyan, sky, pink...). Darker colors are also available using the base color and adding '-darker' (e.g. 'red-darker'). (optional, default `""`)
    -   `isStick` **Boolean** If true, the icon will be stick to the top right of the parent container. (optional, default `false`)
    -   `disabled` **Boolean** If true, the icon will be disabled. (optional, default `false`)
    -   `value` **Any** Attach a value to icon. Useful on some cases like table filtering using icons. (optional, default `""`)
    
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
    list_params = [("value", value, ""),("iconClass", iconClass, "base"),("color", color, ""),("isStick", isStick, False),("disabled", disabled, False)]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Icons", "data" : data }
        

def image_widget(
    src: str,
    alt: str = "",
    imgClass: str = "",
    imgContainerClass: str = "",
    attrs: Optional[dict] = None
    ):
    """    
    This component is used for regular paragraph.
    
    PARAMETERS
    
    -   `src` **String** The src value of the image.
    -   `alt` **String** The alt value of the image.  Can be a translation key or by default raw text. (optional, default `""`)
    -   `imgClass` **String**  (optional, default `""`)
    -   `imgContainerClass` **String**  (optional, default `""`)
    -   `attrs` **Object** List of attributes to add to the image. (optional, default `{}`)
    
    EXAMPLE
    
    {
       src: "https://via.placeholder.com/150",
       alt: "My image",
       attrs: { id: "paragraph" },
     }
    
    """

    data = {
        "src" : src,
       }


    # List of params that will be add only if not default value
    list_params = [("alt", alt, ""),("imgClass", imgClass, ""),("imgContainerClass", imgContainerClass, ""),("attrs", attrs, None)]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Image", "data" : data }
        

def input_widget(
    label: str,
    name: str,
    value: str,
    id: str = "",
    type: str = "text",
    attrs: Optional[dict] = None,
    popovers: Optional[list] = None,
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
    fieldSize: str = "normal",
    tabId: Union[str, int] = "",
    showErrMsg: bool = False
    ):
    """    
    This component is used to create a complete input field input with error handling and label.
    We can add a clipboard button to copy the input value.
    We can also add a password button to show the password.
    We can also add popover to display more information.
    It is mainly use in forms.
    
    PARAMETERS
    
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
        "label" : label,
        "name" : name,
        "value" : value,
       }


    # List of params that will be add only if not default value
    list_params = [("id", id, ""),("type", type, "text"),("attrs", attrs, None),("popovers", popovers, None),("inpType", inpType, "input"),("columns", columns, {"pc":"12","tablet":"12","mobile":"12"}),("disabled", disabled, False),("required", required, False),("placeholder", placeholder, ""),("pattern", pattern, "(?.*)"),("isClipboard", isClipboard, True),("readonly", readonly, False),("hideLabel", hideLabel, False),("containerClass", containerClass, ""),("inpClass", inpClass, ""),("headerClass", headerClass, ""),("fieldSize", fieldSize, "normal"),("tabId", tabId, ""),("showErrMsg", showErrMsg, False)]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Input", "data" : data }
        

def list_widget(
    label: str,
    name: str,
    value: str,
    id: str = "",
    attrs: Optional[dict] = None,
    separator: str = " ",
    maxBtnChars: str = "",
    popovers: Optional[list] = None,
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
    fieldSize: str = "normal",
    tabId: Union[str, int] = "",
    showErrMsg: bool = False
    ):
    """    
    This component is used display list of values in a dropdown, remove or add an item in an easy way.
    We can also add popover to display more information.
    
    PARAMETERS
    
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
        "label" : label,
        "name" : name,
        "value" : value,
       }


    # List of params that will be add only if not default value
    list_params = [("id", id, ""),("attrs", attrs, None),("separator", separator, " "),("maxBtnChars", maxBtnChars, ""),("popovers", popovers, None),("inpType", inpType, "list"),("disabled", disabled, False),("required", required, False),("columns", columns, {"pc":"12","tablet":"12","mobile":"12"}),("hideLabel", hideLabel, False),("onlyDown", onlyDown, False),("overflowAttrEl", overflowAttrEl, ""),("containerClass", containerClass, ""),("inpClass", inpClass, ""),("headerClass", headerClass, ""),("fieldSize", fieldSize, "normal"),("tabId", tabId, ""),("showErrMsg", showErrMsg, False)]
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
    
    -   `widgets` **Array** Array of containers and widgets
    
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
    
    -   `multiples` **Object** The multiples settings to display. This needs to be a dict of settings using default field format.
    -   `columns` **Object** Field has a grid system. This allow to get multiple field in the same row if needed. (optional, default `{"pc":"12","tablet":"12","mobile":"12"}`)
    -   `containerClass` **String** Additionnal class to add to the container (optional, default `""`)
    -   `tadId` **String** The tabindex of the field, by default it is the contentIndex (optional, default `contentIndex`)
    
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
    
    -   `pairs` **Array** The list of key value information. The key and value can be a translation key or a raw text.
    -   `columns` **Object** Determine the  position of the items in the grid system. (optional, default `{"pc":"12","tablet":"12","mobile":"12"}`)
    
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
    attrs: Optional[dict] = None,
    tag: str = "a",
    iconClass: str = "icon-default",
    tabId: Union[str, int] = ""
    ):
    """    
    This component is a standard popover.
    
    PARAMETERS
    
    -   `text` **String** Content of the popover. Can be a translation key or by default raw text.
    -   `href` **String** Link of the anchor. By default it is a # link. (optional, default `"#"`)
    -   `color` **String** Color of the icon between tailwind colors
    -   `attrs` **Object** List of attributs to add to the text. (optional, default `{}`)
    -   `tag` **String** By default it is a anchor tag, but we can use other tag like div in case of popover on another anchor (optional, default `"a"`)
    -   `iconClass` **String**  (optional, default `"icon-default"`)
    -   `tabId` **(String | Number)** The tabindex of the field, by default it is the contentIndex (optional, default `contentIndex`)
    
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
    list_params = [("href", href, "#"),("attrs", attrs, None),("tag", tag, "a"),("iconClass", iconClass, "icon-default"),("tabId", tabId, "")]
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
    
    -   `popovers` **Array** List of popovers to display. Popover component is used.
    -   `groupClasss` **String** Additional class for the flex container (optional, default `""`)
    
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
    operation: str = "edit",
    oldServerName: str = "",
    containerClass: str = "",
    endpoint: str = "",
    method: str = "POST",
    columns: dict = {"pc":"12","tablet":"12","mobile":"12"},
    display: Optional[list] = None
    ):
    """    
    This component is used to create a complete raw form with settings as JSON format.
    
    PARAMETERS
    
    -   `template` **Object** Template object with plugin and settings data.
    -   `operation` **String** Operation type (edit, new, delete). (optional, default `"edit"`)
    -   `oldServerName` **String** Old server name. This is a server name before any changes. (optional, default `""`)
    -   `containerClass` **String** Container additional class (optional, default `""`)
    -   `endpoint` **String** Form endpoint. Case none, will be ignored. (optional, default `""`)
    -   `method` **String** Http method to be used on form submit. (optional, default `"POST"`)
    -   `columns` **Object** Columns object. (optional, default `{"pc":"12","tablet":"12","mobile":"12"}`)
    -   `display` **Array** Array need two values : "groupName" in index 0 and "compId" in index 1 in order to be displayed using the display store. More info on the display store itslef. (optional, default `[]`)
    
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
       }


    # List of params that will be add only if not default value
    list_params = [("operation", operation, "edit"),("oldServerName", oldServerName, ""),("containerClass", containerClass, ""),("endpoint", endpoint, ""),("method", method, "POST"),("columns", columns, {"pc":"12","tablet":"12","mobile":"12"}),("display", display, None)]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Raw", "data" : data }
        

def regular_widget(
    fields: dict,
    buttons: dict,
    title: str = "",
    subtitle: str = "",
    containerClass: str = "",
    endpoint: str = "",
    method: str = "POST",
    display: Optional[list] = None,
    maxWidthScreen: str = "lg",
    columns: dict = {"pc":"12","tablet":"12","mobile":"12"}
    ):
    """    
    This component is used to create a basic form with fields.
    
    PARAMETERS
    
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
    
    EXAMPLE
    
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
    
    """

    data = {
        "fields" : fields,
        "buttons" : buttons,
       }


    # List of params that will be add only if not default value
    list_params = [("title", title, ""),("subtitle", subtitle, ""),("containerClass", containerClass, ""),("endpoint", endpoint, ""),("method", method, "POST"),("display", display, None),("maxWidthScreen", maxWidthScreen, "lg"),("columns", columns, {"pc":"12","tablet":"12","mobile":"12"})]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Regular", "data" : data }
        

def select_widget(
    label: str,
    name: str,
    value: str,
    values: list,
    id: str = "",
    attrs: Optional[dict] = None,
    popovers: Optional[list] = None,
    inpType: str = "select",
    maxBtnChars: str = "",
    disabled: bool = False,
    required: bool = False,
    requiredValues: Optional[list] = None,
    columns: dict = {"pc":"12","tablet":"12","mobile":"12"},
    hideLabel: bool = False,
    onlyDown: bool = False,
    overflowAttrEl: bool = "",
    containerClass: str = "",
    inpClass: str = "",
    headerClass: str = "",
    fieldSize: str = "normal",
    tabId: Union[str, int] = "",
    hideValidation: bool = False
    ):
    """    
    This component is used to create a complete select field input with error handling and label.
    We can be more precise by adding values that need to be selected to be valid.
    We can also add popover to display more information.
    It is mainly use in forms.
    
    PARAMETERS
    
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
        "label" : label,
        "name" : name,
        "value" : value,
        "values" : values,
       }


    # List of params that will be add only if not default value
    list_params = [("id", id, ""),("attrs", attrs, None),("popovers", popovers, None),("inpType", inpType, "select"),("maxBtnChars", maxBtnChars, ""),("disabled", disabled, False),("required", required, False),("requiredValues", requiredValues, None),("columns", columns, {"pc":"12","tablet":"12","mobile":"12"}),("hideLabel", hideLabel, False),("onlyDown", onlyDown, False),("overflowAttrEl", overflowAttrEl, ""),("containerClass", containerClass, ""),("inpClass", inpClass, ""),("headerClass", headerClass, ""),("fieldSize", fieldSize, "normal"),("tabId", tabId, ""),("hideValidation", hideValidation, False)]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Select", "data" : data }
        

def stat_widget(
    title: str,
    stat: Union[str, int],
    subtitle: str = "",
    iconName: str = "",
    subtitleColor: str = "info"
    ):
    """    
    This component is wrapper of all stat components.
    This component has no grid system and will always get the full width of the parent.
    This component is mainly use inside a blank card.
    
    PARAMETERS
    
    -   `title` **String** The title of the stat. Can be a translation key or by default raw text.
    -   `stat` **(String | Number)** The value
    -   `subtitle` **String** The subtitle of the stat. Can be a translation key or by default raw text. (optional, default `""`)
    -   `iconName` **String** A top-right icon to display between icon available in Icons/Stat. Case falsy value, no icon displayed. The icon name is the name of the file without the extension on lowercase. (optional, default `""`)
    -   `subtitleColor` **String** The color of the subtitle between error, success, warning, info (optional, default `"info"`)
    
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
    list_params = [("subtitle", subtitle, ""),("iconName", iconName, ""),("subtitleColor", subtitleColor, "info")]
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
    
    -   `id` **String** The id of the status icon.
    -   `status` **String** The color of the icon between error, success, warning, info (optional, default `"info"`)
    -   `statusClass` **String** Additional class, for example to use with grid system. (optional, default `""`)
    
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
    
    -   `subtitle` **String** Can be a translation key or by default raw text.
    -   `type` **String** The type of title between "container", "card", "content", "min" or "stat" (optional, default `"card"`)
    -   `tag` **String** The tag of the subtitle. Can be h1, h2, h3, h4, h5, h6 or p. If empty, will be determine by the type of subtitle. (optional, default `""`)
    -   `color` **String** The color of the subtitle between error, success, warning, info or tailwind color (optional, default `""`)
    -   `bold` **Boolean** If the subtitle should be bold or not. (optional, default `false`)
    -   `uppercase` **Boolean** If the subtitle should be uppercase or not. (optional, default `false`)
    -   `lowercase` **Boolean** If the subtitle should be lowercase or not. (optional, default `false`)
    -   `subtitleClass` **String** Additional class, useful when component is used directly on a grid system (optional, default `""`)
    
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
    filters: Optional[list] = None,
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
    
    -   `title` **String** Determine the title of the table.
    -   `header` **Array** Determine the header of the table.
    -   `positions` **Array** Determine the position of each item in the table in a list of number based on 12 columns grid.
    -   `items` **Array** items to render in the table. This need to be an array (row) of array (cols) with a cell being a regular widget.
    -   `filters` **Array** Determine the filters of the table. (optional, default `[]`)
    -   `minWidth` **String** Determine the minimum size of the table. Can be "base", "sm", "md", "lg", "xl". (optional, default `"base"`)
    -   `containerClass` **String** Container additional class. (optional, default `""`)
    -   `containerWrapClass` **String** Container wrap additional class. (optional, default `""`)
    -   `tableClass` **String** Table additional class. (optional, default `""`)
    
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
    list_params = [("filters", filters, None),("minWidth", minWidth, "base"),("containerClass", containerClass, ""),("containerWrapClass", containerWrapClass, ""),("tableClass", tableClass, "")]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Table", "data" : data }
        

def tabulator_widget(
    id: str,
    columns: list,
    items: list,
    isStriped: bool = True,
    filters: Optional[list] = None,
    actionsButtons: Optional[list] = None,
    layout: str = "fitDataTable",
    rowHeight: int = 0,
    colMinWidth: int = 150,
    colMaxWidth: int = 0,
    isPagination: bool = True,
    itemsBeforePagination: int = 10,
    paginationSize: int = 10,
    paginationInitialPage: int = 1,
    paginationButtonCount: int = 3,
    paginationSizeSelector: list = [10,25,50,100]
    ):
    """    
    This component allow to display a table using the Tabulator library with utils and custom components around to work with (like filters).
    Because we can't instantiate Vue component inside the Tabulator cell, I choose to send default component props to the cell and teleport the component inside the cell.
    The created instance is store in the tableStore using the id as key in order to use it in other components.
    UI : I created a formatter for each custom component that will return an empty string.
    Sorting : because we aren't working with primitives but props object, each columns that have a custom component will have a custom sorter to avoid sorting error.
    Filtering : I created isomorphic filters that will get the right data to check for each custom component object.
    To apply a filter, we need to render a field that will be link to the filterTable() function.
    A11y :I created a11yTable(), with sortable header tab index.
    
    PARAMETERS
    
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
    
    EXAMPLE
    
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
    
    Returns **Void**;
    
    """

    data = {
        "id" : id,
        "columns" : columns,
        "items" : items,
       }


    # List of params that will be add only if not default value
    list_params = [("isStriped", isStriped, True),("filters", filters, None),("actionsButtons", actionsButtons, None),("layout", layout, "fitDataTable"),("rowHeight", rowHeight, 0),("colMinWidth", colMinWidth, 150),("colMaxWidth", colMaxWidth, 0),("isPagination", isPagination, True),("itemsBeforePagination", itemsBeforePagination, 10),("paginationSize", paginationSize, 10),("paginationInitialPage", paginationInitialPage, 1),("paginationButtonCount", paginationButtonCount, 3),("paginationSizeSelector", paginationSizeSelector, [10,25,50,100])]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Tabulator", "data" : data }
        

def templates_widget(
    templates: dict,
    operation: str = "edit",
    oldServerName: str = "",
    isDraft: Union[str, bool] = False,
    display: Optional[list] = None
    ):
    """    
    This component is used to create a complete  settings form with all modes (advanced, raw, easy).
    
    PARAMETERS
    
    -   `templates` **Object** List of advanced templates that contains settings. Must be a dict with mode as key, then the template name as key with a list of data (different for each modes).
    -   `operation` **String** Operation type (edit, new, delete). (optional, default `"edit"`)
    -   `oldServerName` **String** Old server name. This is a server name before any changes. (optional, default `""`)
    -   `isDraft` **(String | Boolean)** Is draft mode. "yes" or "no" to set a draft select. Else will be ignored. (optional, default `false`)
    -   `display` **Array** Array need two values : "groupName" in index 0 and "compId" in index 1 in order to be displayed using the display store. More info on the display store itslef. (optional, default `[]`)
    
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
    list_params = [("operation", operation, "edit"),("oldServerName", oldServerName, ""),("isDraft", isDraft, False),("display", display, None)]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Templates", "data" : data }
        

def text_widget(
    text: str,
    textClass: str = "",
    textIconContainerClass: str = "col-span-12 flex justify-center items-center",
    color: str = "",
    iconName: str = "",
    iconColor: str = "",
    bold: bool = False,
    uppercase: bool = False,
    tag: str = "p",
    icon: Union[bool, dict] = False,
    attrs: Optional[dict] = None
    ):
    """    
    This component is used for regular paragraph.
    
    PARAMETERS
    
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
    list_params = [("textClass", textClass, ""),("textIconContainerClass", textIconContainerClass, "col-span-12 flex justify-center items-center"),("color", color, ""),("iconName", iconName, ""),("iconColor", iconColor, ""),("bold", bold, False),("uppercase", uppercase, False),("tag", tag, "p"),("icon", icon, False),("attrs", attrs, None)]
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
    
    -   `title` **String** Can be a translation key or by default raw text.
    -   `type` **String** The type of title between "container", "card", "content", "min" or "stat" (optional, default `"card"`)
    -   `tag` **String** The tag of the title. Can be h1, h2, h3, h4, h5, h6 or p. If empty, will be determine by the type of title. (optional, default `""`)
    -   `color` **String** The color of the title between error, success, warning, info or tailwind color (optional, default `""`)
    -   `uppercase` **Boolean** If the title should be uppercase or not. (optional, default `false`)
    -   `lowercase` **Boolean** If the title should be lowercase or not. (optional, default `false`)
    -   `titleClass` **String** Additional class, useful when component is used directly on a grid system (optional, default `""`)
    
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
    iconName: str = "search",
    iconColor: str = "",
    unmatchClass: str = ""
    ):
    """    
    Display a default message "no match" with dedicated icon.
    The message text can be overridden by passing a text prop.
    
    PARAMETERS
    
    -   `text` **String** The text to display
    -   `iconName` **String** The icon to display (optional, default `"search"`)
    -   `iconColor` **String** The color of the icon (optional, default `""`)
    -   `unmatchClass` **String** The class to apply to the message. If not provided, the class will be based on the parent component. (optional, default `""`)
    
    EXAMPLE
    
    {
       text: "dashboard_no_match",
     }
    
    """

    data = {
        "text" : text,
       }


    # List of params that will be add only if not default value
    list_params = [("iconName", iconName, "search"),("iconColor", iconColor, ""),("unmatchClass", unmatchClass, "")]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Unmatch", "data" : data }
        

def upload_widget(
    disabled: bool = False,
    columns: dict = {"pc":"12","tablet":"12","mobile":"12"},
    containerClass: str = "",
    maxScreenW: str = "2xl"
    ):
    """    
    This component is used to upload files to the server. ATM only used to upload plugins.
    
    PARAMETERS
    
    -   `disabled` **Boolean** If true, the upload will be disabled. (optional, default `False`)
    -   `columns` **Object** Columns object. (optional, default `{"pc":"12","tablet":"12","mobile":"12"}`)
    -   `containerClass` **String** Container additional class (optional, default `""`)
    -   `maxScreenW` **String** Max screen width within sm, md, lg, xl, 2xl, 3xl (optional, default `"2xl"`)
    
    EXAMPLE
    
    {
       disabled : True
     }
    
    """

    data = {
       }


    # List of params that will be add only if not default value
    list_params = [("disabled", disabled, False),("columns", columns, {"pc":"12","tablet":"12","mobile":"12"}),("containerClass", containerClass, ""),("maxScreenW", maxScreenW, "2xl")]
    for param in list_params:
        add_key_value(data, param[0], param[1], param[2])

    return { "type" : "Upload", "data" : data }
        
