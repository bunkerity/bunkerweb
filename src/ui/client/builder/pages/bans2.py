from builder.utils.widgets import button_widget, button_group_widget, title_widget, text_widget, tabulator_widget, datepicker_widget
from builder.utils.table import add_column, format_field

bans_columns = [
    add_column(title="IP", field="ip", formatter="text"),
    add_column(title="Reason", field="reason", formatter="text"),
    add_column(title="Ban start date", field="ban_start_date", formatter="fields"),
    add_column(title="Ban end date", field="ban_end_date", formatter="fields"),
    add_column(title="Remain", field="remain", formatter="text"),
]


def bans_filters(reasons: list = [], remains: list = []) -> list:

    filters = [
        {
            "type": "like",
            "fields": ["ip"],
            "setting": {
                "id": "input-search-ip",
                "name": "input-search-ip",
                "label": "bans_search_ip",  # keep it (a18n)
                "value": "",
                "inpType": "input",
                "columns": {"pc": 3, "tablet": 4, " mobile": 12},
            },
        },
    ]

    # Case  "all" ans
    if len(reasons) >= 2:
        filters.append(
            {
                "type": "=",
                "fields": ["reason"],
                "setting": {
                    "id": "select-ban-reason",
                    "name": "select-ban-reason",
                    "label": "bans_select_reason",  # keep it (a18n)
                    "value": "all",  # keep "all"
                    "values": ["all"] + reasons,  # keep "all" and add your reasons dynamically
                    "inpType": "select",
                    "onlyDown": True,
                    "columns": {"pc": 3, "tablet": 4, " mobile": 12},
                },
            },
        )

        if len(reasons) >= 2:
            filters.append(
                {
                    "type": "=",
                    "fields": ["remain"],
                    "setting": {
                        "id": "select-ban-remain",
                        "name": "select-ban-remain",
                        "label": "bans_select_remain",  # keep it (a18n)
                        "value": "all",  # keep "all"
                        "values": ["all"] + remains,  # keep everything and format bans to fit in one remain category
                        "inpType": "select",
                        "onlyDown": True,
                        "columns": {"pc": 3, "tablet": 4, " mobile": 12},
                    },
                },
            )

    return filters


def ban_item(id: str, ip: str, reason: str, ban_start_date: int, ban_end_date: int, remain: str) -> dict:
    return (
        {
            "ip": text_widget(text=ip)["data"],
            "reason": text_widget(text=reason)["data"],
            "ban_start_date": format_field(
                datepicker_widget(
                    id=f"datepicker-ban-start-{id}",
                    name=f"datepicker-ban-start-{id}",
                    label="bans_ban_start_date",  # keep it (a18n)
                    hideLabel=True,
                    inputType="datepicker",
                    value=ban_start_date,
                    disabled=True,  # Readonly
                    columns={"pc": 12, "tablet": 12, " mobile": 12},
                )
            ),
            "ban_end_date": format_field(
                datepicker_widget(
                    id=f"datepicker-ban-end-{id}",
                    name=f"datepicker-ban-end-{id}",
                    label="bans_ban_end_date",  # keep it (a18n)
                    hideLabel=True,
                    inputType="datepicker",
                    value=ban_end_date,
                    disabled=True,  # Readonly
                )
            ),
            "remain": text_widget(text=remain)["data"],
        },
    )


def bans_items(items: list) -> list:
    items = []
    for item in items:
        items.append(
            ban_item(
                id=item.get("id"),
                ip=item.get("ip"),
                reason=item.get("reason"),
                ban_start_date=item.get("ban_start_date"),
                ban_end_date=item.get("ban_end_date"),
                remain=item.get("remain"),
            )
        )

    return items


bans_add_columns = [
    add_column(title="IP", field="ip", formatter="fields"),
    add_column(title="Ban end", field="ban_end", formatter="fields"),
]


default_add_ban = [
    {
        "id": 1,
        "ip": format_field(
            datepicker_widget(
                id="datepicker-add-ban-ip-1",
                name="datepicker-add-ban-ip-1",
                label="bans_add_ban_ip",  # keep it (a18n)
                hideLabel=True,
                value="",
                type="text",
                pattern="",  # replace by ip pattern
                inputType="input",
                columns={"pc": 12, "tablet": 12, " mobile": 12},
            )
        ),
        "ban_end": format_field(
            datepicker_widget(
                id="datepicker-add-ban-end-1",
                name="datepicker-add-ban-end-1",
                label="bans_add_end_date",  # keep it (a18n)
                hideLabel=True,
                inputType="datepicker",
                value="",
            )
        ),
        # Need to create a script on Page.vue level to retrive table data and remove by id
        "delete": button_group_widget(
            buttons=[
                button_widget(
                    id="delete-ban-1",
                    type="button",
                    text="action_delete",  # keep it (a18n)
                    hideLabel=True,
                    iconName="trash",
                    iconColor="white",
                    color="error",
                    size="normal",
                    attrs={"data-delete-row": "1"},  # we will use this attrs to remove the row
                ),
            ]
        ),
    }
]


bans_add_table_actions = button_group_widget(
    buttons=[
        # Need to create a script on Page.vue level to add a row on click
        # + We need to retrieve from the first item a schema to add any new row
        button_widget(
            id="add-bans-entry-btn",
            type="button",
            text="action_entry",  # keep it (a18n)
            color="success",
            iconColor="white",
            iconName="plus",
            size="normal",
            attrs={"data-add-row": ""},  # we will use this attrs to add a new row
        ),
        # Need to create a script on Page.vue level to delete all rows
        button_widget(
            id="add-bans-delete-all-btn",
            type="button",
            text="action_delete_all",  # keep it (a18n)
            color="error",
            iconColor="white",
            iconName="trash",
            size="normal",
            attrs={"data-delete-all": ""},  # we will use this attrs to add a new row
        ),
    ]
)

# Need to create a script on Page.vue level to handle the unban form submission
# Need to retrieve table data, format it to send to the server
# We need to execute only when modal confirm is click (id="unban-btn-confirm")
unban_action = (
    button_widget(
        id="unban-btn",
        type="button",
        text="action_unban",  # keep it (a18n)
        color="success",
        size="normal",
        modal={
            "widgets": [
                title_widget(title="bans_unban_title"),  # keep it (a18n)
                text_widget(text="bans_unban_subtitle"),  # keep it (a18n)
                button_group_widget(
                    buttons=[
                        button_widget(
                            id="close-unban-btn",
                            text="action_close",  # keep it (a18n)
                            color="close",
                            size="normal",
                            attrs={"data-close-modal": ""},  # a11y
                        )["data"],
                        button_widget(
                            id="unban-btn-confirm",
                            text="action_unban",  # keep it (a18n)
                            color="success",
                            size="normal",
                        )["data"],
                    ]
                ),
            ],
        },
    ),
)

# Need to create a script on Page.vue level to handle the form submission
# Need to retrieve table data, format it to send to the serve
add_ban_action = (
    button_widget(
        id="add-bans-btn",
        type="button",
        text="action_add_bans",  # keep it (a18n)
        color="success",
        size="normal",
    ),
)


def bans_builder(bans: list, reasons: list, remains: list) -> list:
    return [
        # Tabs is button group with display value and a size tab inside a tabs container
        {
            type: "tabs",
            "widgets": [
                button_group_widget(
                    buttons=[
                        button_widget(
                            text="bans_tab_list",
                            display=["main", 1],
                            isTab=True,
                            size="tab",
                            iconColor="white",
                            iconName="list",
                        ),
                        button_widget(
                            text="bans_tab_add",
                            display=["main", 2],
                            isTab=True,
                            size="tab",
                            iconColor="white",
                            iconName="plus",
                        ),
                    ]
                )
            ],
        },
        {
            "type": "card",
            "display": ["main", 1],
            "widgets": [
                tabulator_widget(
                    id="table-bans-list",
                    columns=bans_columns,
                    items=bans_items(bans),
                    filters=bans_filters(reasons=reasons, remains=remains),
                ),
                unban_action,
            ],
        },
        {
            "type": "card",
            "display": ["main", 2],
            "widgets": [
                bans_add_table_actions,
                tabulator_widget(
                    id="table-register-plugins",
                    columns=bans_add_columns,
                    items=default_add_ban,
                ),
                add_ban_action,
            ],
        },
    ]
