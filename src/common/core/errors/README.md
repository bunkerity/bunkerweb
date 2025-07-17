The Errors plugin provides customizable error handling for your website, letting you configure how HTTP error responses appear to users. This feature helps you present user-friendly, branded error pages that enhance the user experience during error scenarios, rather than displaying default server error pages, which can seem technical and confusing to visitors.

**How it works:**

1. When a client encounters an HTTP error (for example, 400, 404, or 500), BunkerWeb intercepts the error response.
2. Instead of showing the default error page, BunkerWeb displays a custom, professionally designed error page.
3. Error pages are fully customizable through your configuration, allowing you to specify custom pages for specific error codes. **Custom error page files must be placed in the directory defined by the `ROOT_FOLDER` setting (see the Miscellaneous plugin documentation).**
   - By default, `ROOT_FOLDER` is `/var/www/html/{server_name}` (where `{server_name}` is replaced by the actual server name).
   - In multisite mode, each site can have its own `ROOT_FOLDER`, so custom error pages must be placed in the corresponding directory for each site.
4. The default error pages provide clear explanations, helping users understand what went wrong and what they can do next.

### How to Use

Follow these steps to configure and use the Errors feature:

1. **Define custom error pages:** Specify which HTTP error codes should use custom error pages using the `ERRORS` setting. The custom error page files must be located in the folder specified by the `ROOT_FOLDER` setting for the site. In multisite mode, this means each site/server can have its own folder for custom error pages.
2. **Configure your error pages:** For each error code, you can use the default BunkerWeb error page or provide your own custom HTML page (placed in the appropriate `ROOT_FOLDER`).
3. **Set intercepted error codes:** Select which error codes should always be handled by BunkerWeb with the `INTERCEPTED_ERROR_CODES` setting.
4. **Let BunkerWeb handle the rest:** Once configured, error handling occurs automatically for all specified error codes.

### Configuration Settings

| Setting                   | Default                                           | Context   | Multiple | Description                                                                                                                                 |
| ------------------------- | ------------------------------------------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `ERRORS`                  |                                                   | multisite | no       | **Custom Error Pages:** Map specific error codes to custom HTML files using the format `ERROR_CODE=/path/to/file.html`.                     |
| `INTERCEPTED_ERROR_CODES` | `400 401 403 404 405 413 429 500 501 502 503 504` | multisite | no       | **Intercepted Errors:** List of HTTP error codes that BunkerWeb should handle with its default error page when no custom page is specified. |

!!! tip "Error Page Design"
    The default BunkerWeb error pages are designed to be informative, user-friendly, and professional in appearance. They include:

    - Clear error descriptions
    - Information about what might have caused the error
    - Suggested actions for users to resolve the issue
    - Visual indicators that help users understand whether the issue is on the client or the server side

!!! info "Error Types"
    Error codes are categorized by type:

    - **4xx errors (client-side):** These indicate issues with the client's request, such as attempting to access non-existent pages or lacking proper authentication.
    - **5xx errors (server-side):** These indicate issues with the server's ability to fulfill a valid request, such as internal server errors or temporary unavailability.

### Example Configurations

=== "Default Error Handling"

    Let BunkerWeb handle common error codes with its default error pages:

    ```yaml
    INTERCEPTED_ERROR_CODES: "400 401 403 404 405 413 429 500 501 502 503 504"
    ```

=== "Custom Error Pages"

    Use custom error pages for specific error codes:

    ```yaml
    ERRORS: "404=/custom/404.html 500=/custom/500.html"
    INTERCEPTED_ERROR_CODES: "400 401 403 404 405 413 429 500 501 502 503 504"
    ```

=== "Selective Error Handling"

    Only handle specific error codes with BunkerWeb:

    ```yaml
    INTERCEPTED_ERROR_CODES: "404 500"
    ```
