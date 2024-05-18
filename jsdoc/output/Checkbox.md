## Forms/Field/Checkbox.vue

This component is used to create a complete checkbox field input with error handling and label.
We can also add popover to display more information.
It is mainly use in forms.

### Parameters

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

### Examples

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

