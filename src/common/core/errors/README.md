The Errors plugin provides customizable error handling for your website, allowing you to configure how HTTP error responses are displayed to users. This feature helps you present user-friendly, branded error pages that enhance user experience during error scenarios, instead of displaying the default server error pages that can appear technical and confusing to visitors.

**Here's how the Errors feature works:**

1. When a client encounters an HTTP error (like 400, 404, 500), BunkerWeb intercepts the error response.
2. Instead of showing the default error page, BunkerWeb displays a custom, professionally designed error page.
3. Error pages are fully customizable through your configuration, letting you specify custom pages for specific error codes.
4. The default error pages provide clear explanations, helping users understand what went wrong and what they can do next.

### How to Use

Follow these steps to configure and use the Errors feature:

1. **Define custom error pages:** Specify which HTTP error codes should use custom error pages with the `ERRORS` setting.
2. **Configure your error pages:** For each error code, you can use the default BunkerWeb error page or provide your own custom HTML page.
3. **Set intercepted error codes:** Select which error codes should always be handled by BunkerWeb with the `INTERCEPTED_ERROR_CODES` setting.
4. **Let BunkerWeb handle the rest:** Once configured, error handling happens automatically for all specified error codes.

### Configuration Settings

| Setting                   | Default                                           | Context   | Multiple | Description                                                                                                                                 |
| ------------------------- | ------------------------------------------------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `ERRORS`                  |                                                   | multisite | no       | **Custom Error Pages:** Map specific error codes to custom HTML files using the format `ERROR_CODE=/path/to/file.html`.                     |
| `INTERCEPTED_ERROR_CODES` | `400 401 403 404 405 413 429 500 501 502 503 504` | multisite | no       | **Intercepted Errors:** List of HTTP error codes that BunkerWeb should handle with its default error page when no custom page is specified. |

!!! tip "Error Page Design"
    The default BunkerWeb error pages are designed to be informative, user-friendly, and provide a professional appearance. They include:

    - Clear error descriptions
    - Information about what might have caused the error
    - Suggested actions for the user to resolve the issue
    - Visual indicators to help users understand if the issue is on their side or the server side

!!! info "Error Types"
    Error codes are categorized by type:

    - **4xx errors (client-side):** These indicate issues with the client's request, such as trying to access non-existent pages or lacking proper authentication.
    - **5xx errors (server-side):** These indicate issues with the server's ability to fulfill a valid request, like internal server errors or temporary unavailability.

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
