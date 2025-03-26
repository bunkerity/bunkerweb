The HTML Injection plugin enables you to seamlessly add custom HTML code to your website's pages before either the closing `</body>` or `</head>` tags. This feature is particularly useful for adding analytics scripts, tracking pixels, custom JavaScript, CSS styles, or other third-party integrations without modifying your website's source code.

**Here's how the HTML Injection feature works:**

1. When a page is served from your website, BunkerWeb examines the HTML response.
2. If you've configured body injection, BunkerWeb inserts your custom HTML code just before the closing `</body>` tag.
3. If you've configured head injection, BunkerWeb inserts your custom HTML code just before the closing `</head>` tag.
4. The insertion happens automatically for all HTML pages served by your website.
5. This allows you to add scripts, styles, or other elements without modifying your application's code.

### How to Use

Follow these steps to configure and use the HTML Injection feature:

1. **Prepare your custom HTML:** Decide what HTML code you want to inject into your pages.
2. **Choose injection locations:** Determine whether you need to inject code in the `<head>` section, the `<body>` section, or both.
3. **Configure the settings:** Add your custom HTML to the appropriate settings (`INJECT_HEAD` and/or `INJECT_BODY`).
4. **Let BunkerWeb handle the rest:** Once configured, the HTML will be automatically injected into all served HTML pages.

### Configuration Settings

| Setting       | Default | Context   | Multiple | Description                                                           |
| ------------- | ------- | --------- | -------- | --------------------------------------------------------------------- |
| `INJECT_HEAD` |         | multisite | no       | **Head HTML Code:** The HTML code to inject before the `</head>` tag. |
| `INJECT_BODY` |         | multisite | no       | **Body HTML Code:** The HTML code to inject before the `</body>` tag. |

!!! tip "Best Practices"
    - For performance reasons, place JavaScript files at the end of the body to prevent render blocking.
    - Place CSS and critical JavaScript in the head section to avoid flash of unstyled content.
    - Be careful with injected content that could potentially break your site's functionality.

!!! info "Common Use Cases"
    - Adding analytics scripts (like Google Analytics, Matomo)
    - Integrating chat widgets or customer support tools
    - Including tracking pixels for marketing campaigns
    - Adding custom CSS styles or JavaScript functionality
    - Including third-party libraries without modifying your application code

### Example Configurations

=== "Google Analytics"

    Adding Google Analytics tracking to your website:

    ```yaml
    INJECT_HEAD: ""
    INJECT_BODY: "<script async src=\"https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX\"></script><script>window.dataLayer = window.dataLayer || [];function gtag(){dataLayer.push(arguments);}gtag('js', new Date());gtag('config', 'G-XXXXXXXXXX');</script>"
    ```

=== "Custom Styles"

    Adding custom CSS styles to your website:

    ```yaml
    INJECT_HEAD: "<style>body { font-family: 'Arial', sans-serif; } .custom-element { color: blue; }</style>"
    INJECT_BODY: ""
    ```

=== "Multiple Integrations"

    Adding both custom styles and JavaScript:

    ```yaml
    INJECT_HEAD: "<style>body { font-family: 'Arial', sans-serif; } .notification-banner { background: #f8f9fa; padding: 10px; text-align: center; }</style>"
    INJECT_BODY: "<script src=\"https://cdn.example.com/js/widget.js\"></script><script>initializeWidget('your-api-key');</script>"
    ```

=== "Cookie Consent Banner"

    Adding a simple cookie consent banner:

    ```yaml
    INJECT_HEAD: "<style>.cookie-banner { position: fixed; bottom: 0; left: 0; right: 0; background: #f1f1f1; padding: 20px; text-align: center; z-index: 1000; } .cookie-banner button { background: #4CAF50; border: none; color: white; padding: 10px 20px; cursor: pointer; }</style>"
    INJECT_BODY: "<div id=\"cookie-banner\" class=\"cookie-banner\">This website uses cookies to ensure you get the best experience. <button onclick=\"acceptCookies()\">Accept</button></div><script>function acceptCookies() { document.getElementById('cookie-banner').style.display = 'none'; localStorage.setItem('cookies-accepted', 'true'); } if(localStorage.getItem('cookies-accepted') === 'true') { document.getElementById('cookie-banner').style.display = 'none'; }</script>"
    ```
