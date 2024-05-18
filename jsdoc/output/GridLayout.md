## Widget/GridLayout.vue

This component is used for top level page layout.
This will determine the position of layout components based on the grid system.
We can create card, modal, table and others top level layout using this component.
This component is mainly use as Grid parent component.

### Parameters

*   `type` **[string][4]** Type of layout component, we can have : card, table, modal and others (optional, default `"card"`)
*   `title` **[string][4]** Title of the layout component, will be displayed at the top if exists. Type of layout component will determine the style of the title. (optional, default `""`)
*   `columns` **[object][5]** Work with grid system { pc: 12, tablet: 12, mobile: 12} (optional, default `{"pc":12,"tablet":12,"mobile":12}`)
*   `gridLayoutClass` **[string][4]** Additional class (optional, default `"items-start"`)

### Examples

```javascript
{
type: "card",
title: "Test",
columns: { pc: 12, tablet: 12, mobile: 12},
gridLayoutClass: "items-start"
}
```

