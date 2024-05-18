## Widget/Button.vue

This component is a standard button.
You can link this button to the event store on click with eventAttr.
This will allow you to share a value with other components, for example switching form on a click.
The eventAttr object must contain the store name and the value to send on click at least.
It can also contain the target id element and the expanded value, this will add additionnal accessibility attributs to the button.

### Parameters

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

### Examples

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

