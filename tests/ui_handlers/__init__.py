# UI Handlers package for splitting UI test logic by step type.

from .setup import handle as setup_handle
from .login import handle as login_handle
from .access import handle as access_handle
from .find_and_data import handle_find as find_handle, handle_save_data as save_data_handle
from .actions import (
    handle_click as click_handle,
    handle_access_page as access_page_handle,
    handle_send_keys as send_keys_handle,
    handle_refresh as refresh_handle,
)
from .tabs import handle_switch_tab as switch_tab_handle, handle_close_tab as close_tab_handle
from .configs import handle_config_flow as config_flow_handle
from .instances import handle_instance_create as instance_create_handle, handle_instance_delete as instance_delete_handle
from .services import handle_service_flow as service_flow_handle

__all__ = [
    "setup_handle",
    "login_handle",
    "access_handle",
    "find_handle",
    "save_data_handle",
    "click_handle",
    "access_page_handle",
    "send_keys_handle",
    "refresh_handle",
    "switch_tab_handle",
    "close_tab_handle",
    "config_flow_handle",
    "instance_create_handle",
    "instance_delete_handle",
    "service_flow_handle",
]
