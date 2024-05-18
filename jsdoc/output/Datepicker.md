## Forms/Field/Datepicker.vue

This component is used to create a complete datepicker field input with error handling and label.
You can define a default date, a min and max date, and a format.
We can also add popover to display more information.
It is mainly use in forms.

### Parameters

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

### Examples

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

