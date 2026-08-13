#!/usr/bin/python3
# -*- coding: utf-8 -*-

from contextlib import suppress
from datetime import datetime, timedelta
from logging import Logger
from time import sleep
from typing import Any

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.select import Select
from selenium.common.exceptions import ElementNotInteractableException, JavascriptException, TimeoutException

from utils.ui import assert_button_click, safe_get_element


def handle(LOGGER: Logger, ctx, step_data: Any) -> str:
    """Executes the 'setup' step. Returns the computed base_url."""
    driver = ctx.driver

    LOGGER.info(f"🦊 Navigating to https://{step_data.server_name} ...")
    driver.get(f"https://{step_data.server_name}")
    base_url = f"https://{step_data.server_name}"

    LOGGER.info("🦊 setting up the integration with the setup wizard")

    card_tile = safe_get_element(LOGGER, driver, By.CLASS_NAME, "card-title")
    assert isinstance(card_tile, WebElement), "card title not found"

    if card_tile.text.casefold() != "setup wizard":
        LOGGER.error("The page isn't the wizard page, only the wizard page is compatible with a 'setup' step type.")

    LOGGER.info("🦊 Filling admin user details ...")

    username_input = safe_get_element(LOGGER, driver, By.ID, "username")
    assert isinstance(username_input, WebElement), "username input not found"
    username_input.send_keys(step_data.admin_username)

    if step_data.admin_email:
        sleep(0.3)
        admin_input = safe_get_element(LOGGER, driver, By.ID, "email")
        assert isinstance(admin_input, WebElement), "email input not found"
        admin_input.send_keys(step_data.admin_email)

    sleep(0.3)

    password_input = safe_get_element(LOGGER, driver, By.ID, "password")
    assert isinstance(password_input, WebElement), "password input not found"
    password_input.send_keys(step_data.admin_password)

    sleep(0.3)

    confirm_password_input = safe_get_element(LOGGER, driver, By.ID, "confirm_password")
    assert isinstance(confirm_password_input, WebElement), "confirm_password input not found"
    confirm_password_input.send_keys(step_data.admin_password)

    LOGGER.info("🦊 Navigating to the next step")

    assert_button_click(LOGGER, driver, "next-step", By.ID)

    LOGGER.info("🦊 Filling reverse proxy settings ...")

    sleep(0.3)

    server_name_input = safe_get_element(LOGGER, driver, By.ID, "SERVER_NAME")
    assert isinstance(server_name_input, WebElement), "SERVER_NAME input not found"
    server_name_input.clear()
    server_name_input.send_keys(step_data.server_name)

    auto_lets_encrypt_checkbox = safe_get_element(LOGGER, driver, By.ID, "AUTO_LETS_ENCRYPT")
    assert isinstance(auto_lets_encrypt_checkbox, WebElement), "AUTO_LETS_ENCRYPT checkbox not found"
    auto_lets_encrypt = driver.execute_script("return arguments[0].checked", auto_lets_encrypt_checkbox)
    if auto_lets_encrypt != step_data.auto_lets_encrypt:
        sleep(0.3)
        assert_button_click(LOGGER, driver, auto_lets_encrypt_checkbox)
    LOGGER.info(f"🦊 Let's Encrypt is {'activated' if step_data.auto_lets_encrypt else 'deactivated'}")

    lets_encrypt_staging_checkbox = safe_get_element(LOGGER, driver, By.ID, "USE_LETS_ENCRYPT_STAGING")
    assert isinstance(lets_encrypt_staging_checkbox, WebElement), "USE_LETS_ENCRYPT_STAGING checkbox not found"
    lets_encrypt_staging = driver.execute_script("return arguments[0].checked", lets_encrypt_staging_checkbox)
    if lets_encrypt_staging != step_data.lets_encrypt_staging:
        sleep(0.3)
        assert_button_click(LOGGER, driver, lets_encrypt_staging_checkbox)
    LOGGER.info(f"🦊 Let's Encrypt Staging is {'activated' if step_data.lets_encrypt_staging else 'deactivated'}")

    lets_encrypt_disable_psl_checkbox = safe_get_element(LOGGER, driver, By.ID, "LETS_ENCRYPT_DISABLE_PUBLIC_SUFFIXES")
    assert isinstance(lets_encrypt_disable_psl_checkbox, WebElement), "LETS_ENCRYPT_DISABLE_PUBLIC_SUFFIXES checkbox not found"
    lets_encrypt_disable_psl = driver.execute_script("return arguments[0].checked", lets_encrypt_disable_psl_checkbox)
    if lets_encrypt_disable_psl != step_data.lets_encrypt_disable_psl:
        sleep(0.3)
        assert_button_click(LOGGER, driver, lets_encrypt_disable_psl_checkbox)
    LOGGER.info(f"🦊 Let's Encrypt Public Suffix List check is {'deactivated' if step_data.lets_encrypt_disable_psl else 'activated'}")

    email_lets_encrypt_input = safe_get_element(LOGGER, driver, By.ID, "EMAIL_LETS_ENCRYPT")
    assert isinstance(email_lets_encrypt_input, WebElement), "EMAIL_LETS_ENCRYPT input not found"
    if email_lets_encrypt_input.get_attribute("value") != step_data.email_lets_encrypt:
        sleep(0.3)
        email_lets_encrypt_input.clear()
        email_lets_encrypt_input.send_keys(step_data.email_lets_encrypt)
    LOGGER.info(f"🦊 Using Let's Encrypt email: {'no email' if not step_data.email_lets_encrypt else step_data.email_lets_encrypt}")

    if step_data.lets_encrypt_challenge == "dns":
        LOGGER.info("🦊 Using Let's Encrypt DNS challenge")

        lets_encrypt_challenge_select = safe_get_element(LOGGER, driver, By.ID, "LETS_ENCRYPT_CHALLENGE")
        assert isinstance(lets_encrypt_challenge_select, WebElement), "LETS_ENCRYPT_CHALLENGE select not found"
        lets_encrypt_challenge = Select(lets_encrypt_challenge_select).first_selected_option.get_attribute("value")
        if lets_encrypt_challenge != step_data.lets_encrypt_challenge:
            sleep(0.3)
            assert_button_click(LOGGER, driver, lets_encrypt_challenge_select)
            assert_button_click(LOGGER, lets_encrypt_challenge_select, "./option[@value='dns']")

        lets_encrypt_wildcard_checkbox = safe_get_element(LOGGER, driver, By.ID, "USE_LETS_ENCRYPT_WILDCARD")
        assert isinstance(lets_encrypt_wildcard_checkbox, WebElement), "USE_LETS_ENCRYPT_WILDCARD checkbox not found"
        lets_encrypt_wildcard = driver.execute_script("return arguments[0].checked", lets_encrypt_wildcard_checkbox)
        if lets_encrypt_wildcard != step_data.lets_encrypt_wildcard:
            sleep(0.3)
            assert_button_click(LOGGER, driver, lets_encrypt_wildcard_checkbox)
        LOGGER.info("🦊 Using Let's Encrypt DNS wildcard feature")

        lets_encrypt_dns_provider_select = safe_get_element(LOGGER, driver, By.ID, "LETS_ENCRYPT_DNS_PROVIDER")
        assert isinstance(lets_encrypt_dns_provider_select, WebElement), "LETS_ENCRYPT_DNS_PROVIDER select not found"
        lets_encrypt_dns_provider = Select(lets_encrypt_dns_provider_select).first_selected_option.get_attribute("value")
        if lets_encrypt_dns_provider != step_data.lets_encrypt_dns_provider:
            sleep(0.3)
            assert_button_click(LOGGER, driver, lets_encrypt_dns_provider_select)
            assert_button_click(LOGGER, lets_encrypt_dns_provider_select, f"./option[@value='{step_data.lets_encrypt_dns_provider}']")
        LOGGER.info(f"🦊 Using Let's Encrypt DNS provider: {step_data.lets_encrypt_dns_provider}")

        lets_encrypt_dns_propagation_input = safe_get_element(LOGGER, driver, By.ID, "LETS_ENCRYPT_DNS_PROPAGATION")
        assert isinstance(lets_encrypt_dns_propagation_input, WebElement), "LETS_ENCRYPT_DNS_PROPAGATION input not found"
        if lets_encrypt_dns_propagation_input.get_attribute("value") != step_data.lets_encrypt_dns_propagation:
            sleep(0.3)
            lets_encrypt_dns_propagation_input.clear()
            lets_encrypt_dns_propagation_input.send_keys(step_data.lets_encrypt_dns_propagation)
        LOGGER.info(f"🦊 Using Let's Encrypt DNS custom propagation: {step_data.lets_encrypt_dns_propagation}")

        lets_encrypt_dns_credential_items_textarea = safe_get_element(LOGGER, driver, By.ID, "LETS_ENCRYPT_DNS_CREDENTIAL_ITEMS")
        assert isinstance(lets_encrypt_dns_credential_items_textarea, WebElement), "LETS_ENCRYPT_DNS_CREDENTIAL_ITEMS textarea not found"
        lets_encrypt_dns_credential_items_textarea.clear()
        for credential_item, credential_value in step_data.lets_encrypt_dns_credential_items:
            lets_encrypt_dns_credential_items_textarea.send_keys(f"{credential_item} {credential_value}")
            lets_encrypt_dns_credential_items_textarea.send_keys(Keys.RETURN)
    elif step_data.auto_lets_encrypt:
        LOGGER.info("🦊 Using Let's Encrypt HTTP challenge")

    lets_encrypt_profile_select = safe_get_element(LOGGER, driver, By.ID, "LETS_ENCRYPT_PROFILE")
    assert isinstance(lets_encrypt_profile_select, WebElement), "LETS_ENCRYPT_PROFILE select not found"
    lets_encrypt_profile = Select(lets_encrypt_profile_select).first_selected_option.get_attribute("value")
    if lets_encrypt_profile != step_data.lets_encrypt_profile:
        sleep(0.3)
        assert_button_click(LOGGER, driver, lets_encrypt_profile_select)
        assert_button_click(LOGGER, lets_encrypt_profile_select, f"./option[@value='{step_data.lets_encrypt_profile}']")
    LOGGER.info(f"🦊 Using Let's Encrypt profile: {step_data.lets_encrypt_profile}")

    lets_encrypt_custom_profile_input = safe_get_element(LOGGER, driver, By.ID, "LETS_ENCRYPT_CUSTOM_PROFILE")
    assert isinstance(lets_encrypt_custom_profile_input, WebElement), "LETS_ENCRYPT_CUSTOM_PROFILE input not found"
    if lets_encrypt_custom_profile_input.get_attribute("value") != step_data.lets_encrypt_custom_profile:
        sleep(0.3)
        lets_encrypt_custom_profile_input.clear()
        lets_encrypt_custom_profile_input.send_keys(step_data.lets_encrypt_custom_profile)
    LOGGER.info(f"🦊 Using Let's Encrypt custom profile: {step_data.lets_encrypt_custom_profile}")

    assert_button_click(LOGGER, driver, "advanced-settings-toggle", By.ID)
    sleep(2)

    if step_data.ui_host is not None:
        ui_host_input = safe_get_element(LOGGER, driver, By.ID, "REVERSE_PROXY_HOST")
        assert isinstance(ui_host_input, WebElement), "REVERSE_PROXY_HOST input not found"
        if ui_host_input.get_attribute("value") != step_data.ui_host:
            sleep(0.3)
            ui_host_input.clear()
            ui_host_input.send_keys(step_data.ui_host)
            sleep(0.3)
        LOGGER.info(f"🦊 Using a custom UI Host: {step_data.ui_host}")

    ui_url_input = safe_get_element(LOGGER, driver, By.ID, "REVERSE_PROXY_URL")
    assert isinstance(ui_url_input, WebElement), "REVERSE_PROXY_URL input not found"
    if ui_url_input.get_attribute("value") != step_data.ui_url:
        sleep(0.3)
        ui_url_input.clear()
        ui_url_input.send_keys(step_data.ui_url)
    LOGGER.info(f"🦊 Using a custom UI URL: {step_data.ui_url}")

    use_real_ip_checkbox = safe_get_element(LOGGER, driver, By.ID, "USE_REAL_IP")
    assert isinstance(use_real_ip_checkbox, WebElement), "USE_REAL_IP checkbox not found"
    use_real_ip = driver.execute_script("return arguments[0].checked", use_real_ip_checkbox)
    if use_real_ip != step_data.use_real_ip:
        sleep(0.3)
        assert_button_click(LOGGER, driver, use_real_ip_checkbox)
    LOGGER.info(f"🦊 Use Real IP: {'activated' if step_data.use_real_ip else 'deactivated'}")

    use_proxy_protocol_checkbox = safe_get_element(LOGGER, driver, By.ID, "USE_PROXY_PROTOCOL")
    assert isinstance(use_proxy_protocol_checkbox, WebElement), "USE_PROXY_PROTOCOL checkbox not found"
    use_proxy_protocol = driver.execute_script("return arguments[0].checked", use_proxy_protocol_checkbox)
    if use_proxy_protocol != step_data.use_proxy_protocol:
        sleep(0.3)
        assert_button_click(LOGGER, driver, use_proxy_protocol_checkbox)
    LOGGER.info(f"🦊 Use Proxy Protocol: {'activated' if step_data.use_proxy_protocol else 'deactivated'}")

    real_ip_recursive_checkbox = safe_get_element(LOGGER, driver, By.ID, "REAL_IP_RECURSIVE")
    assert isinstance(real_ip_recursive_checkbox, WebElement), "REAL_IP_RECURSIVE checkbox not found"
    real_ip_recursive = driver.execute_script("return arguments[0].checked", real_ip_recursive_checkbox)
    if real_ip_recursive != step_data.real_ip_recursive:
        sleep(0.3)
        assert_button_click(LOGGER, driver, real_ip_recursive_checkbox)
    LOGGER.info(f"🦊 Real IP Recursive: {'activated' if step_data.real_ip_recursive else 'deactivated'}")

    real_ip_header_input = safe_get_element(LOGGER, driver, By.ID, "REAL_IP_HEADER")
    assert isinstance(real_ip_header_input, WebElement), "REAL_IP_HEADER input not found"
    if real_ip_header_input.get_attribute("value") != step_data.real_ip_header:
        sleep(0.3)
        real_ip_header_input.clear()
        real_ip_header_input.send_keys(step_data.real_ip_header)
    LOGGER.info(f"🦊 Using Real IP Header: {step_data.real_ip_header}")

    real_ip_from_input = safe_get_element(LOGGER, driver, By.ID, "REAL_IP_FROM")
    assert isinstance(real_ip_from_input, WebElement), "REAL_IP_FROM input not found"
    if real_ip_from_input.get_attribute("value") != step_data.real_ip_from:
        sleep(0.3)
        real_ip_from_input.clear()
        real_ip_from_input.send_keys(step_data.real_ip_from)
    LOGGER.info(f"🦊 Using Real IP From: {step_data.real_ip_from}")

    real_ip_from_urls = safe_get_element(LOGGER, driver, By.ID, "REAL_IP_FROM_URLS")
    assert isinstance(real_ip_from_urls, WebElement), "REAL_IP_FROM_URLS input not found"
    if real_ip_from_urls.get_attribute("value") != step_data.real_ip_from_urls:
        sleep(0.3)
        real_ip_from_urls.clear()
        real_ip_from_urls.send_keys(step_data.real_ip_from_urls)
    LOGGER.info(f"🦊 Using Real IP From URLs: {step_data.real_ip_from_urls}")

    use_custom_ssl_checkbox = safe_get_element(LOGGER, driver, By.ID, "USE_CUSTOM_SSL")
    assert isinstance(use_custom_ssl_checkbox, WebElement), "USE_CUSTOM_SSL checkbox not found"
    use_custom_ssl = driver.execute_script("return arguments[0].checked", use_custom_ssl_checkbox)
    if use_custom_ssl != step_data.use_custom_ssl:
        assert_button_click(LOGGER, driver, use_custom_ssl_checkbox)
        sleep(0.3)
    LOGGER.info(f"🦊 Use Custom SSL: {'activated' if step_data.use_custom_ssl else 'deactivated'}")

    custom_ssl_cert_priority_select = safe_get_element(LOGGER, driver, By.ID, "CUSTOM_SSL_CERT_PRIORITY")
    assert isinstance(custom_ssl_cert_priority_select, WebElement), "CUSTOM_SSL_CERT_PRIORITY select not found"
    custom_ssl_cert_priority = Select(custom_ssl_cert_priority_select).first_selected_option.get_attribute("value")
    if custom_ssl_cert_priority != step_data.custom_ssl_cert_priority:
        sleep(0.3)
        assert_button_click(LOGGER, driver, custom_ssl_cert_priority_select)
        assert_button_click(LOGGER, custom_ssl_cert_priority_select, f"./option[@value='{step_data.custom_ssl_cert_priority}']")
    LOGGER.info(f"🦊 Custom SSL Cert Priority: {step_data.custom_ssl_cert_priority}")

    custom_ssl_cert_input = safe_get_element(LOGGER, driver, By.ID, "CUSTOM_SSL_CERT")
    assert isinstance(custom_ssl_cert_input, WebElement), "CUSTOM_SSL_CERT input not found"
    if custom_ssl_cert_input.get_attribute("value") != step_data.custom_ssl_cert:
        sleep(0.3)
        custom_ssl_cert_input.clear()
        custom_ssl_cert_input.send_keys(step_data.custom_ssl_cert)
    LOGGER.info(f"🦊 Custom SSL Cert: {step_data.custom_ssl_cert}")

    custom_ssl_key_input = safe_get_element(LOGGER, driver, By.ID, "CUSTOM_SSL_KEY")
    assert isinstance(custom_ssl_key_input, WebElement), "CUSTOM_SSL_KEY input not found"
    if custom_ssl_key_input.get_attribute("value") != step_data.custom_ssl_key:
        sleep(0.3)
        custom_ssl_key_input.clear()
        custom_ssl_key_input.send_keys(step_data.custom_ssl_key)
    LOGGER.info(f"🦊 Custom SSL Key: {step_data.custom_ssl_key}")

    custom_ssl_cert_data_input = safe_get_element(LOGGER, driver, By.ID, "CUSTOM_SSL_CERT_DATA")
    assert isinstance(custom_ssl_cert_data_input, WebElement), "CUSTOM_SSL_CERT_DATA input not found"
    if custom_ssl_cert_data_input.get_attribute("value") != step_data.custom_ssl_cert_data:
        sleep(0.3)
        custom_ssl_cert_data_input.clear()
        custom_ssl_cert_data_input.send_keys(step_data.custom_ssl_cert_data)
    LOGGER.info(f"🦊 Custom SSL Cert Data: {'no data' if not step_data.custom_ssl_cert_data else 'data provided'}")

    custom_ssl_key_data_input = safe_get_element(LOGGER, driver, By.ID, "CUSTOM_SSL_KEY_DATA")
    assert isinstance(custom_ssl_key_data_input, WebElement), "CUSTOM_SSL_KEY_DATA input not found"
    if custom_ssl_key_data_input.get_attribute("value") != step_data.custom_ssl_key_data:
        sleep(0.3)
        custom_ssl_key_data_input.clear()
        custom_ssl_key_data_input.send_keys(step_data.custom_ssl_key_data)
    LOGGER.info(f"🦊 Custom SSL Key Data: {'no data' if not step_data.custom_ssl_key_data else 'data provided'}")

    LOGGER.info("🦊 Navigating to the next step")
    assert_button_click(LOGGER, driver, "next-step", By.ID)

    sleep(2)

    with suppress((TimeoutException, ElementNotInteractableException)):  # type: ignore
        confirm_dns_button = safe_get_element(LOGGER, driver, By.ID, "confirm-dns", error=True)
        assert isinstance(confirm_dns_button, WebElement), "confirm-dns button not found"
        assert_button_click(LOGGER, driver, confirm_dns_button)

    LOGGER.info("🦊 Navigating to the next step (ignoring PRO step)")
    assert_button_click(LOGGER, driver, "next-step", By.ID)

    LOGGER.info("🦊 Saving setup wizard settings")
    assert_button_click(LOGGER, driver, "save-settings", By.CLASS_NAME)

    LOGGER.info("🦊 Submitted the form, waiting for the wizard to finish ...")

    current_time = datetime.now()

    try:
        # wait for the loadingModal id to be hidden
        while (
            current_time + timedelta(minutes=5) > datetime.now()
            and driver.execute_script("return document.getElementById('loadingModal').style.display") != "none"
        ):
            sleep(1)

        if driver.execute_script("return document.getElementById('loadingModal').style.display") != "none":
            LOGGER.error("🦊 The setup didn't finish, exiting ...")
            driver.save_screenshot("error.png")
            exit(1)
    except JavascriptException:
        sleep(3)

    while current_time + timedelta(minutes=5) > datetime.now() and not driver.current_url.endswith("/login"):
        sleep(1)

    if not driver.current_url.endswith("/login"):
        LOGGER.error(f"Didn't get redirected to login page: {driver.current_url}, exiting ...")
        driver.save_screenshot("error.png")
        exit(1)

    if step_data.server_name not in driver.current_url:
        LOGGER.error(f"The server name is wrong: {driver.current_url}, exiting ...")
        driver.save_screenshot("error.png")
        exit(1)

    base_url = driver.current_url.removesuffix("/login")
    LOGGER.info("🦊 Got redirected to the login page, setup succeeded ✅")
    return base_url
