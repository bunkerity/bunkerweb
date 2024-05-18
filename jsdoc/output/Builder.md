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

