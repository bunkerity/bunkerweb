## Widget/Grid.vue

This component is a basic container that can be used to wrap other components.
This container is based on a grid system and will return a grid container with 12 columns.
In case we are working with grid system, we can add columns to position the container.
We can define additional class too.
This component is mainly use as widget container or as a child of a GridLayout.

### Parameters

*   `gridClass` **[string][4]** Additional class (optional, default `"items-start"`)
*   `columns` **([object][5] | [boolean][6])** Work with grid system { pc: 12, tablet: 12, mobile: 12} (optional, default `false`)

### Examples

```javascript
{
columns: { pc: 12, tablet: 12, mobile: 12},
gridClass: "items-start"
}
```

