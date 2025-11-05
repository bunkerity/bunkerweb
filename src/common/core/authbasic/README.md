The Auth Basic plugin provides HTTP basic authentication to protect your website or specific resources. This feature adds an extra layer of security by requiring users to enter a username and password before accessing protected content. This type of authentication is simple to implement and widely supported by browsers.

**How it works:**

1. When a user tries to access a protected area of your website, the server sends an authentication challenge.
2. The browser displays a login dialog box prompting the user for a username and password.
3. The user enters their credentials, which are sent to the server.
4. If the credentials are valid, the user is granted access to the requested content.
5. If the credentials are invalid, the user is served an error message with the 401 Unauthorized status code.

### How to Use

Follow these steps to enable and configure Auth Basic authentication:

1. **Enable the feature:** Set the `USE_AUTH_BASIC` setting to `yes` in your BunkerWeb configuration.
2. **Choose protection scope:** Decide whether to protect your entire site or just specific URLs by configuring the `AUTH_BASIC_LOCATION` setting.
3. **Define credentials:** Set up at least one username and password pair using the `AUTH_BASIC_USER` and `AUTH_BASIC_PASSWORD` settings.
4. **Customize the message:** Optionally change the `AUTH_BASIC_TEXT` to display a custom message in the login prompt.
5. **Tune hashing cost (optional):** Adjust `AUTH_BASIC_ROUNDS` (1000-999999999 inclusive) to balance login performance and password hashing strength.

### Configuration Settings

| Setting               | Default           | Context   | Multiple | Description                                                                                                                                                               |
| --------------------- | ----------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `USE_AUTH_BASIC`      | `no`              | multisite | no       | **Enable Auth Basic:** Set to `yes` to enable basic authentication.                                                                                                       |
| `AUTH_BASIC_LOCATION` | `sitewide`        | multisite | no       | **Protection Scope:** Set to `sitewide` to protect the entire site, or specify a URL path (e.g., `/admin`) to protect only specific areas.                                |
| `AUTH_BASIC_USER`     | `changeme`        | multisite | yes      | **Username:** The username required for authentication. You can define multiple username/password pairs.                                                                  |
| `AUTH_BASIC_PASSWORD` | `changeme`        | multisite | yes      | **Password:** The password required for authentication. Each password corresponds to a username.                                                                          |
| `AUTH_BASIC_ROUNDS`   | `656000`          | multisite | yes      | **Hash Rounds:** Number of SHA-512 rounds applied when generating the htpasswd file (allowed range: 1000 to 999999999). Lower values improve login speed but reduce cost. |
| `AUTH_BASIC_TEXT`     | `Restricted area` | multisite | no       | **Prompt Text:** The message displayed in the authentication prompt shown to users.                                                                                       |

!!! warning "Security Considerations"
    HTTP Basic Authentication transmits credentials encoded (not encrypted) in Base64. While this is acceptable when used over HTTPS, it should not be considered secure over plain HTTP. Always enable SSL/TLS when using basic authentication.

!!! tip "Using Multiple Credentials"
    You can configure multiple username/password pairs for access. Each `AUTH_BASIC_USER` setting should have a corresponding `AUTH_BASIC_PASSWORD` setting.

### Example Configurations

=== "Site-wide Protection"

    To protect your entire website with a single set of credentials:

    ```yaml
    USE_AUTH_BASIC: "yes"
    AUTH_BASIC_LOCATION: "sitewide"
    AUTH_BASIC_USER: "admin"
    AUTH_BASIC_PASSWORD: "secure_password"
    AUTH_BASIC_TEXT: "Admin Access Only"
    ```

=== "Protecting Specific Areas"

    To only protect a specific path, such as an admin panel:

    ```yaml
    USE_AUTH_BASIC: "yes"
    AUTH_BASIC_LOCATION: "/admin/"
    AUTH_BASIC_USER: "admin"
    AUTH_BASIC_PASSWORD: "secure_password"
    AUTH_BASIC_TEXT: "Admin Access Only"
    ```

=== "Multiple Users"

    To set up multiple users with different credentials:

    ```yaml
    USE_AUTH_BASIC: "yes"
    AUTH_BASIC_LOCATION: "sitewide"
    AUTH_BASIC_TEXT: "Staff Area"

    # First user
    AUTH_BASIC_USER: "admin"
    AUTH_BASIC_PASSWORD: "admin_password"

    # Second user
    AUTH_BASIC_USER_2: "editor"
    AUTH_BASIC_PASSWORD_2: "editor_password"

    # Third user
    AUTH_BASIC_USER_3: "viewer"
    AUTH_BASIC_PASSWORD_3: "viewer_password"
    ```
