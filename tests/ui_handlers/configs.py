#!/usr/bin/python3
# -*- coding: utf-8 -*-

from logging import Logger
from time import sleep
from typing import Any, List

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement

from utils.ui import access_page, assert_button_click, safe_get_element


def handle_config_flow(LOGGER: Logger, ctx, step_data: Any) -> None:
    driver = ctx.driver

    if not driver.current_url.endswith("/configs"):
        driver.get(f"{ctx.base_url}/configs")

    if step_data.type == "create":
        # The create action is a link in the page-head band since the 1.7 reskin, not the green
        # button the DataTable toolbar used to carry.
        access_page(
            LOGGER,
            driver,
            '//a[@role="button" and @href="/configs/new"]',
            "new",
        )
    elif step_data.type in ("read", "update"):
        access_page(
            LOGGER,
            driver,
            f'//a[@href="/configs/{step_data.service}/{step_data.config_type}/{step_data.name}"]',
            step_data.name,
        )
    else:
        pass  # TODO: delete

    sleep(1)
    service = safe_get_element(LOGGER, driver, By.ID, "service-display").text.strip().lower()  # type: ignore
    step_service = hasattr(step_data, "new_service") and step_data.new_service or step_data.service

    if service != step_service:
        if step_data.type == "read":
            LOGGER.error(f"🦊 Service for config {step_data.name} is {service}, expected {step_service}, exiting ...")
            driver.save_screenshot("error.png")
            exit(1)

        assert_button_click(LOGGER, driver, "select-service", by=By.ID)
        service_options = safe_get_element(LOGGER, driver, By.XPATH, "//ul[@id='services-dropdown-menu']/li[@class='nav-item']", multiple=True)
        assert isinstance(service_options, list), "Expected list of service options"

        selected = False
        for service_option in service_options:
            if service_option.text.strip().lower() == step_service.lower():
                assert_button_click(LOGGER, driver, service_option)
                selected = True
                break

        if not selected:
            LOGGER.error(f"🦊 Service {step_service} not found, exiting ...")
            driver.save_screenshot("error.png")
            exit(1)

    config_type = safe_get_element(LOGGER, driver, By.ID, "type-display").text.strip().lower().replace("-", "_")  # type: ignore
    step_config_type = hasattr(step_data, "new_config_type") and step_data.new_config_type or step_data.config_type

    if config_type != step_config_type:
        if step_data.type == "read":
            LOGGER.error(f"🦊 Config type for config {step_data.name} is {config_type}, expected {step_config_type}, exiting ...")
            driver.save_screenshot("error.png")
            exit(1)

        assert_button_click(LOGGER, driver, "select-type", by=By.ID)
        type_options: List[WebElement] = safe_get_element(LOGGER, driver, By.XPATH, "//ul[@id='types-dropdown-menu']/li[@class='nav-item']", multiple=True)  # type: ignore
        for type_option in type_options:
            if type_option.text.strip().lower().replace("-", "_") == step_config_type.lower():
                assert_button_click(LOGGER, driver, type_option)
                break

    name_input = safe_get_element(LOGGER, driver, By.ID, "config-name")
    assert isinstance(name_input, WebElement), "Expected WebElement for config name input"

    name_value = name_input.get_attribute("value")
    assert isinstance(name_value, str), "Expected string value for config name input"

    name = name_value.strip()
    step_name = hasattr(step_data, "new_name") and step_data.new_name or step_data.name

    if name != step_name:
        if step_data.type == "read":
            LOGGER.error(f"🦊 Config name for config {step_data.name} is {name}, expected {step_name}, exiting ...")
            driver.save_screenshot("error.png")
            exit(1)

        name_input.clear()
        name_input.send_keys(step_name)

    config_value = driver.execute_script("return ace.edit('config-value').getValue();")
    LOGGER.info(f"🦊 Config value for {step_data.name}: {config_value}")

    if step_data.content.strip() != config_value.strip():
        if step_data.type == "read":
            LOGGER.error(f"🦊 Config content for config {step_data.name} does not match expected content, exiting ...")
            LOGGER.debug(f"🦊 Expected content: {step_data.content}")
            driver.save_screenshot("error.png")
            exit(1)

        driver.execute_script(f"ace.edit('config-value').setValue(`{step_data.content}`);")

    if step_data.type in ("create", "update"):
        assert_button_click(LOGGER, driver, "//button[contains(@class, 'save-config')]")

        LOGGER.info(f"🦊 {step_data.type.title()}d config {step_data.name} ✅")
    else:
        LOGGER.info(f"🦊 Read config {step_data.name} ✅")
