## Forms/Field/Input.vue

This component is used to create a complete input field input with error handling and label.
We can add a clipboard button to copy the input value.
We can also add a password button to show the password.
We can also add popover to display more information.
It is mainly use in forms.

### Parameters

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

### Examples

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

