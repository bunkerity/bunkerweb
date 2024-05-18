## Forms/Field/Select.vue

This component is used to create a complete select field input with error handling and label.
We can be more precise by adding values that need to be selected to be valid.
We can also add popover to display more information.
It is mainly use in forms.

### Parameters

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

### Examples

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

