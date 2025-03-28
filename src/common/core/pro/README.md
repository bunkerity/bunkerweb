The Pro plugin provides access to premium features and enhancements for BunkerWeb users with an active Pro license. This feature unlocks additional capabilities, premium plugins, and extended functionality that complement the core BunkerWeb platform, delivering enhanced security, performance, and management options for enterprise-grade deployments.

**How it works:**

1. With a valid Pro license key, BunkerWeb connects to the Pro API server to validate your subscription.
2. Once authenticated, the plugin automatically downloads and installs Pro-exclusive plugins and extensions.
3. Your Pro status is periodically verified to ensure continued access to premium features.
4. Premium plugins are seamlessly integrated with your existing BunkerWeb configuration.
5. All Pro features work harmoniously with the open-source core, enhancing rather than replacing functionality.

!!! success "Key benefits"

      1. **Premium Extensions:** Access to exclusive plugins and features not available in the community edition.
      2. **Enhanced Performance:** Optimized configurations and advanced caching mechanisms.
      3. **Enterprise Support:** Priority assistance and dedicated support channels.
      4. **Seamless Integration:** Pro features work alongside community features without configuration conflicts.
      5. **Automatic Updates:** Premium plugins are automatically downloaded and kept current.

### How to Use

Follow these steps to configure and use the Pro features:

1. **Obtain a license key:** Purchase a Pro license from the [BunkerWeb Panel](https://panel.bunkerweb.io/order/bunkerweb-pro?utm_campaign=self&utm_source=doc).
2. **Configure the license key:** Set your license key using the `PRO_LICENSE_KEY` setting.
3. **Let BunkerWeb handle the rest:** Once configured with a valid license, Pro plugins will be automatically downloaded and activated.
4. **Monitor your Pro status:** Check the health indicators in the [web UI](web-ui.md) to confirm your Pro subscription status.

### Configuration Settings

| Setting           | Default | Context | Multiple | Description                                                             |
| ----------------- | ------- | ------- | -------- | ----------------------------------------------------------------------- |
| `PRO_LICENSE_KEY` |         | global  | no       | **Pro License Key:** Your BunkerWeb Pro license key for authentication. |

!!! tip "License Management"
    Your Pro license is tied to your specific deployment environment. If you need to transfer your license or have questions about your subscription, please contact support through the [BunkerWeb Panel](https://panel.bunkerweb.io/contact.php?utm_campaign=self&utm_source=doc).

!!! info "Pro Features"
    The specific Pro features available may evolve over time as new capabilities are added. The Pro plugin automatically handles the installation and configuration of all available features.

!!! warning "Network Requirements"
    The Pro plugin requires outbound internet access to connect to the BunkerWeb API for license verification and to download premium plugins. Ensure your firewall allows connections to `api.bunkerweb.io` on port 443 (HTTPS).

### Frequently Asked Questions

**Q: What happens if my Pro license expires?**

A: If your Pro license expires, access to premium features and plugins will be disabled. However, your BunkerWeb installation will continue to operate with all community edition features intact. To regain access to Pro features, simply renew your license.

**Q: Will Pro features disrupt my existing configuration?**

A: No, Pro features are designed to integrate seamlessly with your current BunkerWeb setup. They enhance functionality without altering or interfering with your existing configuration, ensuring a smooth and reliable experience.

**Q: Can I try Pro features before committing to a purchase?**

A: Absolutely! BunkerWeb offers two Pro plans to suit your needs:

- **BunkerWeb PRO Standard:** Full access to Pro features without technical support.
- **BunkerWeb PRO Enterprise:** Full access to Pro features with dedicated technical support.

You can explore Pro features with a free 1-month trial by using the promo code `freetrial`. Visit the [BunkerWeb Panel](https://panel.bunkerweb.io/?utm_campaign=self&utm_source=doc) to activate your trial and learn more about flexible pricing options based on the number of services protected by BunkerWeb PRO.
