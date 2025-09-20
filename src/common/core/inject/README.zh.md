HTML 注入插件允许您无缝地将自定义 HTML 代码添加到您网站页面的 `</body>` 或 `</head>` 结束标签之前。此功能对于添加分析脚本、跟踪像素、自定义 JavaScript、CSS 样式或其他第三方集成非常有用，而无需修改您网站的源代码。

**工作原理：**

1.  当您的网站提供页面服务时，BunkerWeb 会检查 HTML 响应。
2.  如果您配置了 body 注入，BunkerWeb 会在 `</body>` 结束标签之前插入您的自定义 HTML 代码。
3.  如果您配置了 head 注入，BunkerWeb 会在 `</head>` 结束标签之前插入您的自定义 HTML 代码。
4.  此插入操作会自动应用于您网站提供的所有 HTML 页面。
5.  这使您无需修改应用程序代码即可添加脚本、样式或其他元素。

### 如何使用

请按照以下步骤配置和使用 HTML 注入功能：

1.  **准备您的自定义 HTML：** 决定要注入到页面中的 HTML 代码。
2.  **选择注入位置：** 确定您需要在 `<head>` 部分、`<body>` 部分还是两者都注入代码。
3.  **配置设置：** 将您的自定义 HTML 添加到适当的设置中 (`INJECT_HEAD` 和/或 `INJECT_BODY`)。
4.  **让 BunkerWeb 处理其余部分：** 配置完成后，HTML 将自动注入到所有提供的 HTML 页面中。

### 配置设置

| 设置          | 默认值 | 上下文    | 多选 | 描述                                                       |
| ------------- | ------ | --------- | ---- | ---------------------------------------------------------- |
| `INJECT_HEAD` |        | multisite | 否   | **头部 HTML 代码：** 在 `</head>` 标签前注入的 HTML 代码。 |
| `INJECT_BODY` |        | multisite | 否   | **主体 HTML 代码：** 在 `</body>` 标签前注入的 HTML 代码。 |

!!! tip "最佳实践" - 出于性能考虑，请将 JavaScript 文件放在 body 的末尾，以防止渲染阻塞。- 将 CSS 和关键的 JavaScript 放在 head 部分，以避免出现无样式内容的闪烁。- 请谨慎处理可能破坏您网站功能的注入内容。

!!! info "常见用例" - 添加分析脚本（如 Google Analytics, Matomo）- 集成聊天小部件或客户支持工具 - 为营销活动添加跟踪像素 - 添加自定义 CSS 样式或 JavaScript 功能 - 无需修改应用程序代码即可引入第三方库

### 配置示例

=== "谷歌分析"

    将谷歌分析跟踪添加到您的网站：

    ```yaml
    INJECT_HEAD: ""
    INJECT_BODY: "<script async src=\"https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX\"></script><script>window.dataLayer = window.dataLayer || [];function gtag(){dataLayer.push(arguments);}gtag('js', new Date());gtag('config', 'G-XXXXXXXXXX');</script>"
    ```

=== "自定义样式"

    向您的网站添加自定义 CSS 样式：

    ```yaml
    INJECT_HEAD: "<style>body { font-family: 'Arial', sans-serif; } .custom-element { color: blue; }</style>"
    INJECT_BODY: ""
    ```

=== "多个集成"

    同时添加自定义样式和 JavaScript：

    ```yaml
    INJECT_HEAD: "<style>body { font-family: 'Arial', sans-serif; } .notification-banner { background: #f8f9fa; padding: 10px; text-align: center; }</style>"
    INJECT_BODY: "<script src=\"https://cdn.example.com/js/widget.js\"></script><script>initializeWidget('your-api-key');</script>"
    ```

=== "Cookie 同意横幅"

    添加一个简单的 Cookie 同意横幅：

    ```yaml
    INJECT_HEAD: "<style>.cookie-banner { position: fixed; bottom: 0; left: 0; right: 0; background: #f1f1f1; padding: 20px; text-align: center; z-index: 1000; } .cookie-banner button { background: #4CAF50; border: none; color: white; padding: 10px 20px; cursor: pointer; }</style>"
    INJECT_BODY: "<div id=\"cookie-banner\" class=\"cookie-banner\">本网站使用 Cookie 以确保您获得最佳体验。 <button onclick=\"acceptCookies()\">接受</button></div><script>function acceptCookies() { document.getElementById('cookie-banner').style.display = 'none'; localStorage.setItem('cookies-accepted', 'true'); } if(localStorage.getItem('cookies-accepted') === 'true') { document.getElementById('cookie-banner').style.display = 'none'; }</script>"
    ```
