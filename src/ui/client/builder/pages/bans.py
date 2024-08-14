from .utils.widgets import (
    button_widget,
    button_group_widget,
    title_widget,
    subtitle_widget,
    text_widget,
    tabulator_widget,
    unmatch_widget,
    datepicker_widget,
    checkbox_widget,
)
from .utils.table import add_column
from .utils.format import get_fields_from_field
from typing import Optional


def bans_tabs():
    return {
        "type": "tabs",
        "widgets": [
            button_group_widget(
                buttons=[
                    button_widget(
                        text="bans_tab_list",
                        display=["main", 1],
                        size="tab",
                        color="info",
                        iconColor="white",
                        iconName="list",
                    ),
                    button_widget(
                        text="bans_tab_add",
                        color="success",
                        display=["main", 2],
                        size="tab",
                        iconColor="white",
                        iconName="plus",
                    ),
                ]
            )
        ],
    }


def ban_item(id: str, ip: str, reason: str, ban_start_date: int, ban_end_date: int, remain: str) -> dict:
    return {
        "check": get_fields_from_field(
            checkbox_widget(
                id=f"check-ban-{id}",
                name=f"check-ban-{id}",
                label="bans_ban_check",  # keep it (a18n)
                hideLabel=True,
                value="no",
                columns={"pc": 12, "tablet": 12, "mobile": 12},
            )
        ),
        "ip": text_widget(text=ip)["data"],
        "reason": text_widget(text=reason)["data"],
        "ban_start_date": get_fields_from_field(
            datepicker_widget(
                id=f"datepicker-ban-start-{id}",
                name=f"datepicker-ban-start-{id}",
                label="bans_ban_start_date",  # keep it (a18n)
                hideLabel=True,
                value=ban_start_date,
                disabled=True,  # Readonly
                columns={"pc": 12, "tablet": 12, "mobile": 12},
            )
        ),
        "ban_end_date": get_fields_from_field(
            datepicker_widget(
                id=f"datepicker-ban-end-{id}",
                name=f"datepicker-ban-end-{id}",
                label="bans_ban_end_date",  # keep it (a18n)
                hideLabel=True,
                value=ban_end_date,
                disabled=True,  # Readonly
            )
        ),
        "remain": text_widget(text=remain)["data"],
    }


def bans_items(bans: Optional[list] = None) -> list:

    if bans is None or len(bans) == 0:
        return []

    items = []
    for index, item in enumerate(bans):
        items.append(
            ban_item(
                id=index,
                ip=item.get("ip"),
                reason=item.get("reason"),
                ban_start_date=item.get("ban_start_date"),
                ban_end_date=item.get("ban_end_date"),
                remain=item.get("remain"),
            )
        )

    return items


def bans_filters(reasons: Optional[list] = None, remains: Optional[list] = None) -> list:

    filters = [
        {
            "type": "like",
            "fields": ["ip"],
            "setting": {
                "id": "input-search-ip",
                "name": "input-search-ip",
                "label": "bans_search_ip",  # keep it (a18n)
                "placeholder": "bans_search_ip_placeholder",  # keep it (a18n)
                "value": "",
                "inpType": "input",
                "columns": {"pc": 3, "tablet": 4, "mobile": 12},
                "isClipboard": True,
                "popovers": [
                    {
                        "iconName": "info",
                        "text": "bans_search_ip_desc",
                    }
                ],
                "fieldSize": "sm",
            },
        },
    ]

    # Case  "all" ans
    if reasons is not None and len(reasons) >= 2:
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
                    "columns": {"pc": 3, "tablet": 4, "mobile": 12},
                    "fieldSize": "sm",
                    "popovers": [
                        {
                            "iconName": "info",
                            "text": "bans_select_reason_desc",
                        }
                    ],
                },
            },
        )

        if remains is not None and len(remains) >= 2:
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
                        "columns": {"pc": 3, "tablet": 4, "mobile": 12},
                        "fieldSize": "sm",
                        "popovers": [
                            {
                                "iconName": "info",
                                "text": "bans_select_remain_desc",
                            }
                        ],
                    },
                },
            )

    return filters


def bans_list(bans: Optional[list] = None, reasons: Optional[list] = None, remains: Optional[list] = None) -> dict:
    if bans is None or len(bans) == 0:
        return {
            "type": "card",
            "gridLayoutClass": "transparent",
            "widgets": [
                unmatch_widget(text="bans_not_found"),
            ],
        }

    actions_table_list = [
        # Need to create a script on Page.vue level to add a row on click
        # + We need to retrieve from the first item a schema to add any new row
        button_widget(
            id="select-all-list",
            type="button",
            text="action_select_all",  # keep it (a18n)
            color="success",
            iconColor="white",
            iconName="check",
            size="sm",
            attrs={"data-select-rows": ""},  # we will use this attrs to add a new row
        ),
        button_widget(
            id="unselect-all-list",
            type="button",
            text="action_unselect_all",  # keep it (a18n)
            color="info",
            iconColor="white",
            iconName="uncheck",
            size="sm",
            attrs={"data-unselect-rows": ""},  # we will use this attrs to add a new row
        ),
    ]

    bans_columns = [
        add_column(title="", field="check", formatter="fields", maxWidth=80),
        add_column(title="IP", field="ip", formatter="text"),
        add_column(title="Reason", field="reason", formatter="text"),
        add_column(title="Ban start date", field="ban_start_date", formatter="fields", minWidth=250),
        add_column(title="Ban end date", field="ban_end_date", formatter="fields", minWidth=250),
        add_column(title="Remain", field="remain", formatter="text"),
    ]

    return {
        "type": "card",
        "display": ["main", 1],
        "widgets": [
            title_widget("bans_list_title"),  # keep it (a18n)
            subtitle_widget("bans_list_subtitle"),  # keep it (a18n)
            tabulator_widget(
                id="table-bans-list",
                actionsButtons=actions_table_list,
                columns=bans_columns,
                items=bans_items(bans),
                itemsBeforePagination=20,
                filters=bans_filters(reasons=reasons, remains=remains),
                layout="fitColumns",
            ),
            button_group_widget(
                buttons=[
                    button_widget(
                        id="unban-btn",
                        type="button",
                        text="action_unban",  # keep it (a18n)
                        color="success",
                        size="normal",
                        iconName="uncheck",
                        iconColor="white",
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
                                        ),
                                        button_widget(
                                            id="unban-btn-confirm",
                                            text="action_unban",  # keep it (a18n)
                                            color="success",
                                            iconName="uncheck",
                                            iconColor="white",
                                            size="normal",
                                            attrs={"data-unban": ""},
                                        ),
                                    ]
                                ),
                            ],
                        },
                    ),
                ]
            ),
        ],
    }


def bans_add() -> dict:

    bans_add_table_actions = [
        # Need to create a script on Page.vue level to add a row on click
        # + We need to retrieve from the first item a schema to add any new row
        button_widget(
            id="add-bans-entry-btn",
            type="button",
            text="action_entry",  # keep it (a18n)
            color="success",
            iconColor="white",
            iconName="plus",
            size="sm",
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
            size="sm",
            attrs={"data-delete-all": ""},  # we will use this attrs to add a new row
        ),
    ]

    bans_add_columns = [
        add_column(title="IP", field="ip", formatter="fields"),
        add_column(title="Ban end", field="ban_end", formatter="fields"),
        add_column(title="delete", field="delete", formatter="buttongroup", maxWidth=100),
    ]

    default_add_ban = [
        {
            "id": 1,
            "ip": get_fields_from_field(
                datepicker_widget(
                    id="datepicker-add-ban-ip-1",
                    name="datepicker-add-ban-ip-1",
                    label="bans_add_ban_ip",  # keep it (a18n)
                    hideLabel=True,
                    value="",
                    columns={"pc": 12, "tablet": 12, "mobile": 12},
                )
            ),
            "ban_end": get_fields_from_field(
                datepicker_widget(
                    id="datepicker-add-ban-end-1",
                    name="datepicker-add-ban-end-1",
                    label="bans_add_end_date",  # keep it (a18n)
                    hideLabel=True,
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
                        hideText=True,
                        iconName="trash",
                        iconColor="white",
                        color="error",
                        size="normal",
                        attrs={"data-delete-row": "1"},  # we will use this attrs to remove the row
                    ),
                ]
            )["data"],
        }
    ]

    add_ban_action = button_group_widget(
        buttons=[
            button_widget(
                id="add-bans-btn",
                type="button",
                text="action_save",  # keep it (a18n)
                color="success",
                iconName="plus",
                iconColor="white",
                size="normal",
            )
        ]
    )

    return {
        "type": "card",
        "display": ["main", 2],
        "widgets": [
            title_widget("bans_add_title"),  # keep it (a18n)
            subtitle_widget("bans_add_subtitle"),  # keep it (a18n)
            tabulator_widget(
                id="table-register-plugins",
                columns=bans_add_columns,
                items=default_add_ban,
                layout="fitColumns",
                actionsButtons=bans_add_table_actions,
                itemsBeforePagination=20,
            ),
            add_ban_action,
        ],
    }


def bans_builder(bans: Optional[list] = None, reasons: Optional[list] = None, remains: Optional[list] = None) -> list:
    return [
        # Tabs is button group with display value and a size tab inside a tabs container
        bans_tabs(),
        bans_list(bans=bans, reasons=reasons, remains=remains),
        bans_add(),
    ]
