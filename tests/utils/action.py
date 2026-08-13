from logging import Logger
from typing import Iterable, Literal

from pydantic import ValidationError, BaseModel

from models.selenium_action import SeleniumActionBase


def is_derived_from_selenium_action(cls):
    """Check if the given class is derived from SeleniumActionBase"""
    if SeleniumActionBase in cls.__bases__:
        return True
    for base in cls.__bases__:
        if is_derived_from_selenium_action(base):
            return True
    return False


def parse_action(
    logger: Logger,
    integrations: Iterable[Literal["Docker", "Linux", "Autoconf", "Kubernetes", "All-in-one"]],
    integration: Literal["Docker", "Linux", "Autoconf", "Kubernetes", "All-in-one"],
    action_str: str,
    action_data: dict,
    _type: Literal["core", "ui", "api"] = "core",
) -> BaseModel:
    integration_specs = {}
    for spec_integration in integrations:
        integration_specs[spec_integration] = action_data.pop(spec_integration, {})

    logger.debug(f"Integration specs: {integration_specs}")

    integration_action_data = action_data.copy()
    for key, value in integration_specs[integration].copy().items():
        if value is None:
            integration_action_data.pop(key, None)
            continue

        if isinstance(value, dict):
            integration_action_data[key] = action_data.get(key, {}) | value
            continue
        integration_action_data[key] = value

    logger.debug(f"Integration action data: {integration_action_data}")

    models_module = __import__("models")

    if _type == "ui":
        ui_module = getattr(models_module, "ui")
        setup_step = False

        for step, step_data in action_data["steps"].copy().items():
            # Apply integration specific overrides for each step

            if "integrations" in step_data and integration not in step_data["integrations"]:
                del action_data["steps"][step]
                continue

            step_integration_data = step_data.copy()
            for key, value in step_data.get(integration, {}).items():
                if value is None:
                    step_integration_data.pop(key, None)
                    continue

                if isinstance(value, dict):
                    step_integration_data[key] = step_integration_data.get(key, {}) | value
                    continue
                step_integration_data[key] = value

            try:
                if step_integration_data["type"] in ("create", "delete", "update", "read"):
                    ui_type_module = getattr(ui_module, step_integration_data["type"])
                    ui_item_module = getattr(ui_type_module, step_integration_data["item"])
                    class_ = getattr(ui_item_module, f"{step_integration_data['type'].title()}{step_integration_data['item'].title()}")
                else:
                    try:
                        class_ = getattr(ui_module, step_integration_data["type"].title())
                    except AttributeError:
                        ui_type_module = getattr(ui_module, step_integration_data["type"])
                        class_ = getattr(ui_type_module, step_integration_data["type"].title())

                action_data["steps"][step] = class_(**step_integration_data)
                if step_integration_data["type"] == "setup":
                    if setup_step:
                        logger.error(f"Action {action_str} have multiple 'setup' steps, there can only be one.")
                        exit(1)
                    setup_step = True
            except ValidationError:
                logger.exception(f"Action {action_str} step {step} has invalid data")
                exit(1)

        logger.debug(f"Translated action data: {action_data}")

    try:
        class_ = getattr(models_module, action_data["type"].title())
        action = class_(**integration_action_data)
    except ValidationError:
        logger.exception(f"Action {action_str} has invalid data")
        exit(1)

    logger.debug(f"Action: {action}")

    return action
