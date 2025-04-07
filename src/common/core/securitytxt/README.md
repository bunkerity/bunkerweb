The Security.txt plugin implements the [Security.txt](https://securitytxt.org/) standard ([RFC 9116](https://www.rfc-editor.org/rfc/rfc9116)) for your website. This feature helps security researchers access your security policies and provides a standardized way for them to report security vulnerabilities they discover in your systems.

**How it works:**

1. When enabled, BunkerWeb creates a `/.well-known/security.txt` file at the root of your website.
2. This file contains information about your security policies, contacts, and other relevant details.
3. Security researchers and automated tools can easily find this file at the standard location.
4. The content is configured using simple settings that allow you to specify contact information, encryption keys, policies, and acknowledgments.
5. BunkerWeb automatically formats the file in accordance with RFC 9116.

### How to Use

Follow these steps to configure and use the Security.txt feature:

1. **Enable the feature:** Set the `USE_SECURITYTXT` setting to `yes` to enable the security.txt file.
2. **Configure contact information:** Specify at least one contact method using the `SECURITYTXT_CONTACT` setting.
3. **Set additional information:** Configure optional fields like expiration date, encryption, acknowledgments, and policy URLs.
4. **Let BunkerWeb handle the rest:** Once configured, BunkerWeb will automatically create and serve the security.txt file at the standard location.

### Configuration Settings

| Setting                        | Default                     | Context   | Multiple | Description                                                                                              |
| ------------------------------ | --------------------------- | --------- | -------- | -------------------------------------------------------------------------------------------------------- |
| `USE_SECURITYTXT`              | `no`                        | multisite | no       | **Enable Security.txt:** Set to `yes` to enable the security.txt file.                                   |
| `SECURITYTXT_URI`              | `/.well-known/security.txt` | multisite | no       | **Security.txt URI:** Indicates the URI where the security.txt file will be accessible.                  |
| `SECURITYTXT_CONTACT`          |                             | multisite | yes      | **Contact Information:** How security researchers can contact you (e.g., `mailto:security@example.com`). |
| `SECURITYTXT_EXPIRES`          |                             | multisite | no       | **Expiration Date:** When this security.txt file should be considered expired (ISO 8601 format).         |
| `SECURITYTXT_ENCRYPTION`       |                             | multisite | yes      | **Encryption:** URL pointing to encryption keys to be used for secure communication.                     |
| `SECURITYTXT_ACKNOWLEDGEMENTS` |                             | multisite | yes      | **Acknowledgements:** URL where security researchers are recognized for their reports.                   |
| `SECURITYTXT_POLICY`           |                             | multisite | yes      | **Security Policy:** URL pointing to the security policy describing how to report vulnerabilities.       |
| `SECURITYTXT_HIRING`           |                             | multisite | yes      | **Security Jobs:** URL pointing to security-related job openings.                                        |
| `SECURITYTXT_CANONICAL`        |                             | multisite | yes      | **Canonical URL:** The canonical URI(s) for this security.txt file.                                      |
| `SECURITYTXT_PREFERRED_LANG`   | `en`                        | multisite | no       | **Preferred Language:** The language(s) used in communications. Specified as an ISO 639-1 language code. |
| `SECURITYTXT_CSAF`             |                             | multisite | yes      | **CSAF:** Link to the provider-metadata.json of your Common Security Advisory Framework provider.        |

!!! warning "Expiration Date Required"
    According to RFC 9116, the `Expires` field is required. If you don't provide a value for `SECURITYTXT_EXPIRES`, BunkerWeb automatically sets the expiration date to one year from the current date.

!!! info "Contact Information Is Essential"
    The `Contact` field is the most important part of the security.txt file. You should provide at least one way for security researchers to contact you. This can be an email address, a web form, a phone number, or any other method that works for your organization.

!!! warning "URLs Must Use HTTPS"
    According to RFC 9116, all URLs in the security.txt file (except for `mailto:` and `tel:` links) MUST use HTTPS. Non-HTTPS URLs will automatically be converted to HTTPS by BunkerWeb to ensure compliance with the standard.

### Example Configurations

=== "Basic Configuration"

    A minimal configuration with just contact information:

    ```yaml
    USE_SECURITYTXT: "yes"
    SECURITYTXT_CONTACT: "mailto:security@example.com"
    SECURITYTXT_POLICY: "https://example.com/security-policy"
    ```

=== "Comprehensive Configuration"

    A more complete configuration with all fields:

    ```yaml
    USE_SECURITYTXT: "yes"
    SECURITYTXT_CONTACT: "mailto:security@example.com"
    SECURITYTXT_CONTACT_2: "https://example.com/security-contact-form"
    SECURITYTXT_EXPIRES: "2023-12-31T23:59:59+00:00"
    SECURITYTXT_ENCRYPTION: "https://example.com/pgp-key.txt"
    SECURITYTXT_ACKNOWLEDGEMENTS: "https://example.com/hall-of-fame"
    SECURITYTXT_POLICY: "https://example.com/security-policy"
    SECURITYTXT_HIRING: "https://example.com/jobs/security"
    SECURITYTXT_CANONICAL: "https://example.com/.well-known/security.txt"
    SECURITYTXT_PREFERRED_LANG: "en"
    SECURITYTXT_CSAF: "https://example.com/provider-metadata.json"
    ```

=== "Multiple Contacts Configuration"

    Configuration with multiple contact methods:

    ```yaml
    USE_SECURITYTXT: "yes"
    SECURITYTXT_CONTACT: "mailto:security@example.com"
    SECURITYTXT_CONTACT_2: "tel:+1-201-555-0123"
    SECURITYTXT_CONTACT_3: "https://example.com/security-form"
    SECURITYTXT_POLICY: "https://example.com/security-policy"
    SECURITYTXT_EXPIRES: "2024-06-30T23:59:59+00:00"
    ```
