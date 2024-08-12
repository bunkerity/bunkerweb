import json
import base64

from builder.utils.widgets import button, button_group, title, text, tabulator, fields, upload

bans_columns = [
    {"title": "IP", "field": "ip", "formatter": "text"},
    {"title": "Reason", "field": "reason", "formatter": "text"},
    {"title": "Ban start date", "field": "ban_start_date", "formatter": "fields"},
    {"title": "Ban end date", "field": "ban_end_date", "formatter": "fields"},
    {"title": "Remain", "field": "remain", "formatter": "text"},
]


bans_filters = [
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
    {
        "type": "=",
        "fields": ["reason"],
        "setting": {
            "id": "select-ban-reason",
            "name": "select-ban-reason",
            "label": "bans_select_reason",  # keep it (a18n)
            "value": "all",  # keep "all"
            "values": ["all", "antibot"],  # keep "all" and add your reasons
            "inpType": "select",
            "onlyDown": True,
            "columns": {"pc": 3, "tablet": 4, " mobile": 12},
        },
    },
    {
        "type": "=",
        "fields": ["remain"],
        "setting": {
            "id": "select-ban-remain",
            "name": "select-ban-remain",
            "label": "bans_select_remain",  # keep it (a18n)
            "value": "all",  # keep "all"
            "values": ["all", "hour(s)" "day(s)", "week(s)", "month(s)", "year(s)"],  # keep everything and format bans to fit in one remain category
            "inpType": "select",
            "onlyDown": True,
            "columns": {"pc": 3, "tablet": 4, " mobile": 12},
        },
    },
]

bans_items = [
    {
        "ip": text(text="ban_ip")["data"],  # replace ban_ip by real ip
        "reason": text(text="Reason")["data"],  # replace Reason by real reason
        "ban_start_date": fields(
            id="datepicker-ban-start-id",  # replace id by value to use on a form
            name="datepicker-ban-start-id",  # replace by value to use on a form
            label="bans_ban_start_date",  # keep it (a18n)
            hideLabel=True,
            inputType="datepicker",
            value="ban_start_date",  # replace ban_start_date by timestamp value
            disabled=True,  # Readonly
            columns={"pc": 12, "tablet": 12, " mobile": 12},
        )["data"],
        "ban_end_date": fields(
            id="datepicker-ban-end-id",  # replace id by value to use on a form
            name="datepicker-ban-end-id",  # replace by value to use on a form
            label="bans_ban_end_date",  # keep it (a18n)
            hideLabel=True,
            inputType="datepicker",
            value="ban_end_date",  # replace ban_end_date by timestamp value
            disabled=True,  # Readonly
        )["data"],
        "remain": text(text="Remain")["data"],  # replace Remain by one of the remain categories ["hour(s)" "day(s)", "week(s)", "month(s)", "year(s)"]
    },
]


bans_add_columns = [
    {"title": "ip", "field": "ip", "formatter": "fields"},  # input
    {"title": "Ban end", "field": "ban_end", "formatter": "fields"},
]

# add one default ban
bans_add_items = [
    {
        "id": 1,
        "ip": fields(
            id="datepicker-add-ban-ip-1",
            name="datepicker-add-ban-ip-1",
            label="bans_add_ban_ip",  # keep it (a18n)
            hideLabel=True,
            value="",
            type="text",
            pattern="",  # replace by ip pattern
            inputType="input",
            columns={"pc": 12, "tablet": 12, " mobile": 12},
        )["data"],
        "ban_end": fields(
            id="datepicker-add-ban-end-1",
            name="datepicker-add-ban-end-1",
            label="bans_add_end_date",  # keep it (a18n)
            hideLabel=True,
            inputType="datepicker",
            value="ban_end_date",  # replace ban_end_date by default timestamp value (one week ?)
        )["data"],
        # Need to create a script on Page.vue level to retrive table data and remove by id
        "delete": button_group(
            buttons=[
                button(
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


bans_add_table_actions = button_group(
    buttons=[
        # Need to create a script on Page.vue level to add a row on click
        # + We need to retrieve from the first item a schema to add any new row
        button(
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
        button(
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

builder = [
    {
        "type": "card",
        "display": ["main", 1],
        "widgets": [
            tabulator(
                id="table-core-plugins",
                columns=bans_columns,
                items=bans_items,
                filters=bans_filters,
            ),
            # Need to create a script on Page.vue level to handle the unban form submission
            # Need to retrieve table data, format it to send to the server
            # We need to execute only when modal confirm is click (id="unban-btn-confirm")
            button(
                id="unban-btn",
                type="button",
                text="action_unban",  # keep it (a18n)
                color="success",
                size="normal",
                modal={
                    "widgets": [
                        title(title="bans_unban_title"),  # keep it (a18n)
                        text(text="bans_unban_subtitle"),  # keep it (a18n)
                        button_group(
                            buttons=[
                                button(
                                    id="close-unban-btn",
                                    text="action_close",  # keep it (a18n)
                                    color="close",
                                    size="normal",
                                    attrs={"data-close-modal": ""},  # a11y
                                )["data"],
                                button(
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
        ],
    },
    {
        "type": "card",
        "display": ["main", 2],
        "widgets": [
            bans_add_table_actions,
            tabulator(
                id="table-register-plugins",
                columns=bans_add_columns,
                items=bans_add_items,
            ),
            # Need to create a script on Page.vue level to handle the form submission
            # Need to retrieve table data, format it to send to the server
            button(
                id="add-bans-btn",
                type="button",
                text="action_add_bans",  # keep it (a18n)
                color="success",
                size="normal",
            ),
        ],
    },
]


with open("bans2.json", "w") as f:
    f.write(json.dumps(builder))

output_base64_bytes = base64.b64encode(bytes(json.dumps(builder), "utf-8"))

output_base64_string = output_base64_bytes.decode("ascii")


with open("bans2.txt", "w") as f:
    f.write(output_base64_string)
