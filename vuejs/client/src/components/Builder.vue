<script setup>
const builder = [{
        // we are starting with the top level container name
        // this can be a "card", "modal", "table"... etc
        "type": "card",
        // a card can have an icon and a color at the top right
        "icon": ["iconName", "iconColor"],
        // grid position for each screen
        "columns" : [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
        // container title
        "title" : "My awesome card",
        // group of widgets will share same columns
        // Case we want a button widget in a one column group and others in like a 3 columns group
        content: [
	{
		position="left",
		columns={
			pc=4,
			tablet=12,
			..
		},
		widgets=[Input1, Button2, { type="input", data = {...} }]
	},
	...
      ]
    },
    // ... other containers
]
</script>

<template>

</template>
