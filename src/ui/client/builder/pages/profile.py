# Define data to put in profile widgets
# - username
# - email
# - created_method
# - is_superadmin
# - role
# - role_description
# - permissions (liste of permissions [])
# - creation_date
# - last_update (last time update user info)

# Define data to put in profile form widgets
# - update password
# - update email

# Define data to put in totp widgets
# if want to enable totp (currently disabled):
# text with state
# show QRcode SVG
# - form (endpoint /totp-enable) : totp secret (type password), totp code, password
# Case currently enabled :
# text with state
# after first totp setup, show recovery codes
# form refresh recovery codes button that will redisplay recovery (endpoint /totp-refresh) : password (warning that will remove previous)
# form disabled (endpoint /totp-disable) : totp code || recovery code, password

from .utils.widgets import (
    button_widget,
    button_group_widget,
    title_widget,
    subtitle_widget,
    text_widget,
    input_widget,
    regular_widget,
    unmatch_widget,
    pairs_widget,
    image_widget,
)
from .utils.format import get_fields_from_field
from typing import Optional


def fallback_message(msg: str, display: Optional[list] = None) -> dict:

    return {
        "type": "void",
        "display": display if display else [],
        "widgets": [
            unmatch_widget(text=msg),
        ],
    }


def profile_info(user_profile: Optional[list] = None) -> dict:

    if user_profile is None or (isinstance(user_profile, list) and len(user_profile) == 0):
        return fallback_message("profile_info_not_found", display=["main", 0])

    return {
        "type": "card",
        "maxWidthScreen": "md",
        "display": ["main", 0],
        "widgets": [
            title_widget(
                title="profile_info_title",  # keep it (a18n)
            ),
            subtitle_widget(
                subtitle="profile_info_subtitle",  # keep it (a18n)
            ),
            pairs_widget(
                pairs=user_profile,
                columns={"pc": 6, "tablet": 12, "mobile": 12},
            ),
        ],
    }


def profile_account_form(email: str) -> dict:
    return {
        "type": "card",
        "maxWidthScreen": "md",
        "display": ["main", 1],
        "widgets": [
            title_widget(
                title="profile_account_title",  # keep it (a18n)
            ),
            subtitle_widget(
                subtitle="profile_account_subtitle",  # keep it (a18n)
            ),
            button_group_widget(
                buttons=[
                    button_widget(
                        text="profile_account_tab_email",
                        display=["account", 0],
                        size="normal",
                        color="back",
                    ),
                    button_widget(
                        text="profile_account_tab_password",
                        display=["account", 1],
                        size="normal",
                        color="back",
                    ),
                ],
                buttonGroupClass="bouton-group-card mt-2",
            ),
            regular_widget(
                display=["account", 0],
                title="profile_account_form_email_title",
                maxWidthScreen="xs",
                endpoint="/edit/email",
                method="POST",
                fields=[
                    get_fields_from_field(
                        input_widget(
                            id="profile-email",
                            name="email",
                            label="profile_email",  # keep it (a18n)
                            value=email,
                            pattern="",  # add your pattern if needed
                            columns={"pc": 12, "tablet": 12, "mobile": 12},
                            placeholder="profile_email_placeholder",  # keep it (a18n)
                            popovers=[
                                {
                                    "iconName": "info",
                                    "text": "profile_email_desc",
                                }
                            ],
                        )
                    ),
                    get_fields_from_field(
                        input_widget(
                            id="profile-password-email",
                            name="current_password",
                            label="profile_current_password",  # keep it (a18n)
                            value="",
                            required=True,
                            type="password",
                            pattern="",  # add your pattern if needed
                            columns={"pc": 12, "tablet": 12, "mobile": 12},
                            placeholder="profile_current_password_placeholder",  # keep it (a18n)
                            popovers=[
                                {
                                    "iconName": "info",
                                    "text": "profile_current_password_desc",
                                },
                            ],
                        )
                    ),
                ],
                buttons=[
                    button_widget(
                        id="profile-account-submit",
                        text="action_edit",
                        iconName="pen",
                        iconColor="white",
                        color="edit",
                        size="normal",
                        type="submit",
                    )
                ],
            ),
            regular_widget(
                display=["account", 1],
                title="profile_account_form_password_title",
                maxWidthScreen="xs",
                endpoint="/edit/password",
                method="POST",
                fields=[
                    get_fields_from_field(
                        input_widget(
                            id="profile-password-account",
                            name="new_password",
                            label="profile_new_password",  # keep it (a18n)
                            value="",
                            type="password",
                            pattern="",  # add your pattern if needed
                            columns={"pc": 12, "tablet": 12, "mobile": 12},
                            placeholder="profile_new_password_placeholder",  # keep it (a18n)
                            popovers=[
                                {
                                    "iconName": "info",
                                    "text": "profile_new_password_desc",
                                },
                            ],
                        )
                    ),
                    get_fields_from_field(
                        input_widget(
                            id="profile-password-confirm",
                            name="new_password_confirm",
                            type="password",
                            label="profile_new_password_confirm",  # keep it (a18n)
                            value="",
                            pattern="",  # add your pattern if needed
                            columns={"pc": 12, "tablet": 12, "mobile": 12},
                            placeholder="profile_new_password_confirm_placeholder",  # keep it (a18n)
                            popovers=[
                                {
                                    "iconName": "info",
                                    "text": "profile_new_password_confirm_desc",
                                },
                            ],
                        )
                    ),
                    get_fields_from_field(
                        input_widget(
                            id="profile-password-update",
                            name="current_password",
                            label="profile_current_password",  # keep it (a18n)
                            value="",
                            type="password",
                            required=True,
                            pattern="",  # add your pattern if needed
                            columns={"pc": 12, "tablet": 12, "mobile": 12},
                            placeholder="profile_current_password_placeholder",  # keep it (a18n)
                            popovers=[
                                {
                                    "iconName": "info",
                                    "text": "profile_current_password_desc",
                                },
                            ],
                        )
                    ),
                ],
                buttons=[
                    button_widget(
                        id="profile-account-submit",
                        text="action_edit",
                        iconName="pen",
                        iconColor="white",
                        color="edit",
                        size="normal",
                        type="submit",
                    )
                ],
            ),
        ],
    }


def totp_enable(
    totp_recovery_codes: Optional[list] = None,
    is_recovery_refreshed: bool = False,
) -> dict:

    recovery_widgets = []

    if is_recovery_refreshed and (totp_recovery_codes is not None and totp_recovery_codes):
        recovery_widgets.append(pairs_widget(pairs=totp_recovery_codes))

    if is_recovery_refreshed and not totp_recovery_codes:
        recovery_widgets.append(text_widget(text="profile_recovery_codes_refresh_but_not_found", iconName="", iconColor="error"))

    if not is_recovery_refreshed and not totp_recovery_codes:
        recovery_widgets.append(text_widget(text="profile_no_recovery_codes", iconName="", iconColor="error"))

    recovery_widgets.append(
        button_group_widget(
            buttons=[
                button_widget(
                    id="profile-disable-submit",
                    text="profile_refresh_recovery_codes",
                    iconName="refresh",
                    iconColor="white",
                    color="success",
                    size="normal",
                    attrs={
                        "data-submit-form": "{}",
                        "data-submit-endpoint": "/totp-refresh",
                        "data-submit-method": "POST",
                    },
                )
            ]
        )
    )

    return {
        "type": "card",
        "maxWidthScreen": "md",
        "display": ["main", 2],
        "widgets": [
            title_widget(
                title="profile_totp_title",  # keep it (a18n)
            ),
            subtitle_widget(
                subtitle="profile_totp_subtitle",  # keep it (a18n)
            ),
            text_widget(
                text="profile_totp_enable_state",  # keep it (a18n)
                iconName="check",
                iconColor="success",
                textIconContainerClass="col-span-12 flex justify-center items-center mt-2",
            ),
            # totp secret (type password), totp code, password
            regular_widget(
                title="profile_totp_disable_form_title",
                maxWidthScreen="xs",
                endpoint="/totp-disable",
                method="POST",
                fields=[
                    get_fields_from_field(
                        input_widget(
                            id="profile-totp-code-enable",
                            name="totp_code",
                            label="profile_totp_code",  # keep it (a18n)
                            value="",
                            required=True,
                            pattern="",  # add your pattern if needed
                            columns={"pc": 12, "tablet": 12, "mobile": 12},
                            placeholder="profile_totp_code_placeholder",  # keep it (a18n)
                            popovers=[
                                {
                                    "iconName": "info",
                                    "text": "profile_totp_code_desc",
                                }
                            ],
                        )
                    ),
                    get_fields_from_field(
                        input_widget(
                            type="password",
                            id="profile-totp-current-password",
                            name="current_password",
                            label="profile_current_password",  # keep it (a18n)
                            value="",
                            pattern="",  # add your pattern if needed
                            columns={"pc": 12, "tablet": 12, "mobile": 12},
                            placeholder="profile_current_password_placeholder",  # keep it (a18n)
                            popovers=[
                                {
                                    "iconName": "info",
                                    "text": "profile_current_password_desc",
                                }
                            ],
                        )
                    ),
                ],
                buttons=[
                    button_widget(
                        id="profile-disable-submit",
                        text="action_disable",
                        iconName="cross",
                        iconColor="white",
                        color="success",
                        size="normal",
                        type="submit",
                    )
                ],
            ),
        ],
    }


def totp_disable(totp_img: str = "", totp_secret: str = "") -> dict:
    return {
        "type": "card",
        "maxWidthScreen": "md",
        "display": ["main", 2],
        "widgets": [
            title_widget(
                title="profile_totp_title",  # keep it (a18n)
            ),
            subtitle_widget(
                subtitle="profile_totp_subtitle",  # keep it (a18n)
            ),
            text_widget(
                text="profile_totp_disable_state",  # keep it (a18n)
                iconName="uncheck",
                iconColor="error",
                textIconContainerClass="col-span-12 flex justify-center items-center mt-2",
            ),
            image_widget(
                src=totp_img,
                alt="profile_totp_qr_code",  # keep it (a18n)
            ),
            # totp secret (type password), totp code, password
            regular_widget(
                title="profile_totp_enable_form_title",
                maxWidthScreen="xs",
                endpoint="/totp-enable",
                method="POST",
                fields=[
                    get_fields_from_field(
                        input_widget(
                            id="profile-totp-secret",
                            name="totp_secret",
                            label="profile_totp_secret",  # keep it (a18n)
                            value=totp_secret,
                            type="password",
                            isClipboard=True,
                            pattern="",  # add your pattern if needed
                            columns={"pc": 12, "tablet": 12, "mobile": 12},
                            placeholder="profile_totp_secret_placeholder",  # keep it (a18n)
                            popovers=[
                                {
                                    "iconName": "info",
                                    "text": "profile_totp_secret_desc",
                                }
                            ],
                        )
                    ),
                    get_fields_from_field(
                        input_widget(
                            id="profile-totp-code-disabled",
                            name="totp_code",
                            label="profile_totp_code",  # keep it (a18n)
                            value="",
                            required=True,
                            pattern="",  # add your pattern if needed
                            columns={"pc": 12, "tablet": 12, "mobile": 12},
                            placeholder="profile_totp_code_placeholder",  # keep it (a18n)
                            popovers=[
                                {
                                    "iconName": "info",
                                    "text": "profile_totp_code_desc",
                                }
                            ],
                        )
                    ),
                    get_fields_from_field(
                        input_widget(
                            id="profile-totp-code",
                            name="current_password",
                            label="profile_current_password",  # keep it (a18n)
                            value="",
                            required=True,
                            type="password",
                            pattern="",  # add your pattern if needed
                            columns={"pc": 12, "tablet": 12, "mobile": 12},
                            placeholder="profile_current_password_placeholder",  # keep it (a18n)
                            popovers=[
                                {
                                    "iconName": "info",
                                    "text": "profile_current_password_desc",
                                }
                            ],
                        )
                    ),
                ],
                buttons=[
                    button_widget(
                        id="profile-disable-submit",
                        text="action_enable",
                        iconName="plus",
                        iconColor="white",
                        color="success",
                        size="normal",
                        type="submit",
                    )
                ],
            ),
        ],
    }


def profile_tabs():
    return {
        "type": "tabs",
        "widgets": [
            button_group_widget(
                buttons=[
                    button_widget(
                        text="profile_tab_profile",
                        display=["main", 0],
                        size="tab",
                        color="info",
                        iconColor="white",
                        iconName="list",
                    ),
                    button_widget(
                        text="profile_tab_account",
                        color="edit",
                        display=["main", 1],
                        size="tab",
                        iconColor="white",
                        iconName="pen",
                    ),
                    button_widget(
                        text="profile_tab_totp",
                        color="success",
                        display=["main", 2],
                        size="tab",
                        iconColor="white",
                        iconName="lock",
                    ),
                ]
            )
        ],
    }


def fallback_message(msg: str, display: Optional[list] = None) -> dict:

    return {
        "type": "void",
        "display": display if display else [],
        "widgets": [
            unmatch_widget(text=msg),
        ],
    }


def profile_builder(user: Optional[object] = None, totp_data: Optional[dict] = None) -> list:

    if not user:
        return [fallback_message("profile_user_not_found")]

    totp_form = None
    if totp_data is None or totp_data.get("is_totp", None) is None:
        totp_form = fallback_message("profile_totp_data_missing")

    if not totp_data.get("is_totp"):
        totp_form = totp_disable(
            totp_img=totp_data.get("totp_image", ""),
            totp_secret=totp_data.get("totp_secret", ""),
        )

    if totp_data.get("is_totp"):
        totp_form = totp_enable(
            totp_recovery_codes=totp_data.get("totp_recovery_codes", None),
            is_recovery_refreshed=totp_data.get("is_recovery_refreshed", False),
        )

    user_profile = [
        {"key": "profile_username", "value": user.get_id()},
        {"key": "profile_email", "value": user.email or ""},
        {"key": "profile_created_method", "value": user.method},
        {"key": "profile_role", "value": user.list_roles[0]},
        {"key": "profile_permissions", "value": ", ".join(user.list_permissions)},
        {"key": "profile_creation_date", "value": user.creation_date.strftime("%Y-%m-%d at %H:%M:%S %Z")},
        {"key": "profile_last_update", "value": user.update_date.strftime("%Y-%m-%d at %H:%M:%S %Z")},
    ]

    return [
        # Tabs is button group with display value and a size tab inside a tabs container
        profile_tabs(),
        profile_info(user_profile=user_profile),
        profile_account_form(email=user.email or ""),
        totp_form,
    ]
