## Widget/Container.vue

This component is a basic container that can be used to wrap other components.
In case we are working with grid system, we can add columns to position the container.
We can define additional class too.
This component is mainly use as widget container.

### Parameters

*   `containerClass` **[string][4]** Additional class (optional, default `""`)
*   `columns` **([object][5] | [boolean][6])** Work with grid system { pc: 12, tablet: 12, mobile: 12} (optional, default `false`)

### Examples

```javascript
{
containerClass: "w-full h-full bg-white rounded shadow-md",
columns: { pc: 12, tablet: 12, mobile: 12}
}
```

