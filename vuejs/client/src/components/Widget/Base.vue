<script setup>
const builder = [{
    // we are starting with the top level container name
    // this can be a "card", "modal", "table"... etc
    "card" : {
        // a card can have an icon and a color at the top right
        "icon": ["iconName", "iconColor"],
        // grid position for each screen
        "columns" : [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
        // container title
        "title" : "My awesome card",
        // group of widgets will share same columns
        // Case we want a button widget in a one column group and others in like a 3 columns group
        "groups" : [{
            // determine the number of columns for widgets in group for each screen
            "columns" : (1, 2, 3),
            "widgets" : [
                {
                    "position" : "left", // "center" or "right" or "default"
                    "type" : "widgetType", // "widgetType" is the name of the widget, for example "Detail" to render a Detail widget
                    // Need to be a list in case we have multiple widgets in the same group
                    // By default, widgetEls are horizontally aligned with flexbox
                    "widgetEls" : [
                        // data we need for one widget
                        {
                            "id" : "widgetId",
                            "title" : "Widget title",
                            "label" : "Widget label",
                            "values" : ["value1", "value2"],
                        },
                        // ... other widgets
                    ]
                }
            ]
        },
        // ... other groups
        ]
    },
    // ... other containers
}]
</script>

<template>

</template>
