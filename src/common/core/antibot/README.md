Attackers often use automated tools (bots) to try and exploit your website. To protect against this, BunkerWeb includes an "Antibot" feature that challenges users to prove they are human. If a user successfully completes the challenge, they are granted access to your website. This feature is disabled by default.

**How it works:**

1.  When a user visits your site, BunkerWeb checks if they've already passed the antibot challenge.
2.  If not, the user is redirected to a challenge page.
3.  The user must complete the challenge (e.g., solve a CAPTCHA, run JavaScript).
4.  If the challenge is successful, the user is redirected back to the page they were originally trying to visit and can browse your website normally.

### How to Use

Follow these steps to enable and configure the Antibot feature:

1. **Choose a challenge type:** Decide which type of antibot challenge to use (e.g., [captcha](#__tabbed_3_3), [hcaptcha](#__tabbed_3_5), [javascript](#__tabbed_3_2)).
2. **Enable the feature:** Set the `USE_ANTIBOT` setting to your chosen challenge type in your BunkerWeb configuration.
3. **Configure the settings:** Adjust the other `ANTIBOT_*` settings as needed. For reCAPTCHA, hCaptcha, Turnstile, and mCaptcha, you must create an account with the respective service and obtain API keys.
4. **Important:** Ensure the `ANTIBOT_URI` is a unique URL on your site that is not in use.

!!! important "About the `ANTIBOT_URI` Setting"
    Ensure the `ANTIBOT_URI` is a unique URL on your site that is not in use.

!!! warning "Session Configuration in Clustered Environments"
    The antibot feature uses cookies to track whether a user has completed the challenge. If you are running BunkerWeb in a clustered environment (multiple BunkerWeb instances), you **must** configure session management properly. This involves setting the `SESSIONS_SECRET` and `SESSIONS_NAME` settings to the **same values** across all BunkerWeb instances. If you don't do this, users may be repeatedly prompted to complete the antibot challenge. You can find more information about session configuration [here](#sessions).

### Common Settings

The following settings are shared across all challenge mechanisms:

| Setting                | Default      | Context   | Multiple | Description                                                                                                                                         |
| ---------------------- | ------------ | --------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ANTIBOT_URI`          | `/challenge` | multisite | no       | **Challenge URL:** The URL where users will be redirected to complete the challenge. Make sure this URL is not used for anything else on your site. |
| `ANTIBOT_TIME_RESOLVE` | `60`         | multisite | no       | **Challenge Time Limit:** The maximum time (in seconds) a user has to complete the challenge. After this time, a new challenge will be generated.   |
| `ANTIBOT_TIME_VALID`   | `86400`      | multisite | no       | **Challenge Validity:** How long (in seconds) a completed challenge is valid. After this time, users will have to solve a new challenge.            |

### Excluding Traffic from Challenges

BunkerWeb allows you to specify certain users, IPs, or requests that should bypass the antibot challenge completely. This is useful for whitelisting trusted services, internal networks, or specific pages that should always be accessible without challenge:

| Setting                     | Default | Context   | Multiple | Description                                                                                                       |
| --------------------------- | ------- | --------- | -------- | ----------------------------------------------------------------------------------------------------------------- |
| `ANTIBOT_IGNORE_URI`        |         | multisite | no       | **Excluded URLs:** List of URI regex patterns separated by spaces that should bypass the challenge.               |
| `ANTIBOT_IGNORE_IP`         |         | multisite | no       | **Excluded IPs:** List of IP addresses or CIDR ranges separated by spaces that should bypass the challenge.       |
| `ANTIBOT_IGNORE_RDNS`       |         | multisite | no       | **Excluded Reverse DNS:** List of reverse DNS suffixes separated by spaces that should bypass the challenge.      |
| `ANTIBOT_RDNS_GLOBAL`       | `yes`   | multisite | no       | **Global IPs Only:** If set to `yes`, only perform reverse DNS checks on public IP addresses.                     |
| `ANTIBOT_IGNORE_ASN`        |         | multisite | no       | **Excluded ASNs:** List of ASN numbers separated by spaces that should bypass the challenge.                      |
| `ANTIBOT_IGNORE_USER_AGENT` |         | multisite | no       | **Excluded User Agents:** List of User-Agent regex patterns separated by spaces that should bypass the challenge. |

**Examples:**

- `ANTIBOT_IGNORE_URI: "^/api/ ^/webhook/ ^/assets/"`
  This will exclude all URIs starting with `/api/`, `/webhook/`, or `/assets/` from the antibot challenge.

- `ANTIBOT_IGNORE_IP: "192.168.1.0/24 10.0.0.1"`
  This will exclude the internal network `192.168.1.0/24` and the specific IP `10.0.0.1` from the antibot challenge.

- `ANTIBOT_IGNORE_RDNS: ".googlebot.com .bingbot.com"`
  This will exclude requests from hosts with reverse DNS ending with `googlebot.com` or `bingbot.com` from the antibot challenge.

- `ANTIBOT_IGNORE_ASN: "15169 8075"`
  This will exclude requests from ASN 15169 (Google) and ASN 8075 (Microsoft) from the antibot challenge.

- `ANTIBOT_IGNORE_USER_AGENT: "^Mozilla.+Chrome.+Safari"`
  This will exclude requests with User-Agents matching the specified regex pattern from the antibot challenge.

### Supported Challenge Mechanisms

=== "Cookie"

    The Cookie challenge is a lightweight mechanism that relies on setting a cookie in the user's browser. When a user accesses the site, the server sends a cookie to the client. On subsequent requests, the server checks for the presence of this cookie to verify that the user is legitimate. This method is simple and effective for basic bot protection without requiring additional user interaction.

    **How it works:**

    1. The server generates a unique cookie and sends it to the client.
    2. The client must return the cookie in subsequent requests.
    3. If the cookie is missing or invalid, the user is redirected to the challenge page.

    **Configuration Settings:**

    | Setting       | Default | Context   | Multiple | Description                                                         |
    | ------------- | ------- | --------- | -------- | ------------------------------------------------------------------- |
    | `USE_ANTIBOT` | `no`    | multisite | no       | **Enable Antibot:** Set to `cookie` to enable the Cookie challenge. |

    Refer to the [Common Settings](#common-settings) for additional configuration options.

=== "JavaScript"

    The JavaScript challenge requires the client to solve a computational task using JavaScript. This mechanism ensures that the client has JavaScript enabled and can execute the required code, which is typically beyond the capability of most bots.

    **How it works:**

    1. The server sends a JavaScript script to the client.
    2. The script performs a computational task (e.g., hashing) and submits the result back to the server.
    3. The server verifies the result to confirm the client's legitimacy.

    **Key Features:**

    - The challenge dynamically generates a unique task for each client.
    - The computational task involves hashing with specific conditions (e.g., finding a hash with a certain prefix).

    **Configuration Settings:**

    | Setting       | Default | Context   | Multiple | Description                                                                 |
    | ------------- | ------- | --------- | -------- | --------------------------------------------------------------------------- |
    | `USE_ANTIBOT` | `no`    | multisite | no       | **Enable Antibot:** Set to `javascript` to enable the JavaScript challenge. |

    Refer to the [Common Settings](#common-settings) for additional configuration options.

=== "Captcha"

    The Captcha challenge is a homemade mechanism that generates image-based challenges hosted entirely within your BunkerWeb environment. It tests users' ability to recognize and interpret randomized characters, ensuring automated bots are effectively blocked without relying on external services.

    **How it works:**

    1. The server generates a CAPTCHA image containing randomized characters.
    2. The user must enter the characters displayed in the image into a text field.
    3. The server validates the user's input against the generated CAPTCHA.

    **Key Features:**

    - Fully self-hosted, eliminating the need for third-party APIs.
    - Dynamically generated challenges ensure uniqueness for each user session.

    **Configuration Settings:**

    | Setting       | Default | Context   | Multiple | Description                                                           |
    | ------------- | ------- | --------- | -------- | --------------------------------------------------------------------- |
    | `USE_ANTIBOT` | `no`    | multisite | no       | **Enable Antibot:** Set to `captcha` to enable the Captcha challenge. |

    Refer to the [Common Settings](#common-settings) for additional configuration options.

=== "reCAPTCHA"

    When enabled, reCAPTCHA runs in the background (v3) to assign a score based on user behavior. A score lower than the configured threshold will prompt further verification or block the request. For visible challenges (v2), users must interact with the reCAPTCHA widget before continuing.

    To use reCAPTCHA with BunkerWeb, you need to obtain your site and secret keys from the [Google reCAPTCHA admin console](https://www.google.com/recaptcha/admin). Once you have the keys, you can configure BunkerWeb to use reCAPTCHA as an antibot mechanism.

    **Configuration Settings:**

    | Setting                     | Default | Context   | Multiple | Description                                                                                                   |
    | --------------------------- | ------- | --------- | -------- | ------------------------------------------------------------------------------------------------------------- |
    | `USE_ANTIBOT`               | `no`    | multisite | no       | **Enable Antibot:** Set to `recaptcha` to enable the reCAPTCHA challenge.                                     |
    | `ANTIBOT_RECAPTCHA_SITEKEY` |         | multisite | no       | **reCAPTCHA Site Key:** Your reCAPTCHA site key (get this from Google).                                       |
    | `ANTIBOT_RECAPTCHA_SECRET`  |         | multisite | no       | **reCAPTCHA Secret Key:** Your reCAPTCHA secret key (get this from Google).                                   |
    | `ANTIBOT_RECAPTCHA_SCORE`   | `0.7`   | multisite | no       | **reCAPTCHA Minimum Score:** The minimum score required for reCAPTCHA to pass a user (only for reCAPTCHA v3). |

    Refer to the [Common Settings](#common-settings) for additional configuration options.

=== "hCaptcha"

    When enabled, hCaptcha provides an effective alternative to reCAPTCHA by verifying user interactions without relying on a scoring mechanism. It challenges users with a simple, interactive test to confirm their legitimacy.

    To integrate hCaptcha with BunkerWeb, you must obtain the necessary credentials from the hCaptcha dashboard at [hCaptcha](https://www.hcaptcha.com). These credentials include a site key and a secret key.

    **Configuration Settings:**

    | Setting                    | Default | Context   | Multiple | Description                                                                 |
    | -------------------------- | ------- | --------- | -------- | --------------------------------------------------------------------------- |
    | `USE_ANTIBOT`              | `no`    | multisite | no       | **Enable Antibot:** Set to `hcaptcha` to enable the hCaptcha challenge.     |
    | `ANTIBOT_HCAPTCHA_SITEKEY` |         | multisite | no       | **hCaptcha Site Key:** Your hCaptcha site key (get this from hCaptcha).     |
    | `ANTIBOT_HCAPTCHA_SECRET`  |         | multisite | no       | **hCaptcha Secret Key:** Your hCaptcha secret key (get this from hCaptcha). |

    Refer to the [Common Settings](#common-settings) for additional configuration options.

=== "Turnstile"

    Turnstile is a modern, privacy-friendly challenge mechanism that leverages Cloudflare’s technology to detect and block automated traffic. It validates user interactions in a seamless, background manner, reducing friction for legitimate users while effectively discouraging bots.

    To integrate Turnstile with BunkerWeb, ensure you obtain the necessary credentials from [Cloudflare Turnstile](https://www.cloudflare.com/turnstile).

    **Configuration Settings:**

    | Setting                     | Default | Context   | Multiple | Description                                                                     |
    | --------------------------- | ------- | --------- | -------- | ------------------------------------------------------------------------------- |
    | `USE_ANTIBOT`               | `no`    | multisite | no       | **Enable Antibot:** Set to `turnstile` to enable the Turnstile challenge.       |
    | `ANTIBOT_TURNSTILE_SITEKEY` |         | multisite | no       | **Turnstile Site Key:** Your Turnstile site key (get this from Cloudflare).     |
    | `ANTIBOT_TURNSTILE_SECRET`  |         | multisite | no       | **Turnstile Secret Key:** Your Turnstile secret key (get this from Cloudflare). |

    Refer to the [Common Settings](#common-settings) for additional configuration options.

=== "mCaptcha"

    mCaptcha is an alternative CAPTCHA challenge mechanism that verifies the legitimacy of users by presenting an interactive test similar to other antibot solutions. When enabled, it challenges users with a CAPTCHA provided by mCaptcha, ensuring that only genuine users bypass the automated security checks.

    mCaptcha is designed with privacy in mind. It is fully GDPR compliant, ensuring that all user data involved in the challenge process adheres to strict data protection standards. Additionally, mCaptcha offers the flexibility to be self-hosted, allowing organizations to maintain full control over their data and infrastructure. This self-hosting capability not only enhances privacy but also optimizes performance and customization to suit specific deployment needs.

    To integrate mCaptcha with BunkerWeb, you must obtain the necessary credentials from the [mCaptcha](https://mcaptcha.org/) platform or your own provider. These credentials include a site key and a secret key for verification.

    **Configuration Settings:**

    | Setting                    | Default                     | Context   | Multiple | Description                                                                 |
    | -------------------------- | --------------------------- | --------- | -------- | --------------------------------------------------------------------------- |
    | `USE_ANTIBOT`              | `no`                        | multisite | no       | **Enable Antibot:** Set to `mcaptcha` to enable the mCaptcha challenge.     |
    | `ANTIBOT_MCAPTCHA_SITEKEY` |                             | multisite | no       | **mCaptcha Site Key:** Your mCaptcha site key (get this from mCaptcha).     |
    | `ANTIBOT_MCAPTCHA_SECRET`  |                             | multisite | no       | **mCaptcha Secret Key:** Your mCaptcha secret key (get this from mCaptcha). |
    | `ANTIBOT_MCAPTCHA_URL`     | `https://demo.mcaptcha.org` | multisite | no       | **mCaptcha Domain:** The domain to use for the mCaptcha challenge.          |

    Refer to the [Common Settings](#common-settings) for additional configuration options.

### Example Configurations

=== "Cookie Challenge"

    Example configuration for enabling the Cookie challenge:

    ```yaml
    USE_ANTIBOT: "cookie"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

=== "JavaScript Challenge"

    Example configuration for enabling the JavaScript challenge:

    ```yaml
    USE_ANTIBOT: "javascript"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

=== "Captcha Challenge"

    Example configuration for enabling the Captcha challenge:

    ```yaml
    USE_ANTIBOT: "captcha"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

=== "reCAPTCHA Challenge"

    Example configuration for enabling the reCAPTCHA challenge:

    ```yaml
    USE_ANTIBOT: "recaptcha"
    ANTIBOT_RECAPTCHA_SITEKEY: "your-site-key"
    ANTIBOT_RECAPTCHA_SECRET: "your-secret-key"
    ANTIBOT_RECAPTCHA_SCORE: "0.7"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

=== "hCaptcha Challenge"

    Example configuration for enabling the hCaptcha challenge:

    ```yaml
    USE_ANTIBOT: "hcaptcha"
    ANTIBOT_HCAPTCHA_SITEKEY: "your-site-key"
    ANTIBOT_HCAPTCHA_SECRET: "your-secret-key"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

=== "Turnstile Challenge"

    Example configuration for enabling the Turnstile challenge:

    ```yaml
    USE_ANTIBOT: "turnstile"
    ANTIBOT_TURNSTILE_SITEKEY: "your-site-key"
    ANTIBOT_TURNSTILE_SECRET: "your-secret-key"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

=== "mCaptcha Challenge"

    Example configuration for enabling the mCaptcha challenge:

    ```yaml
    USE_ANTIBOT: "mcaptcha"
    ANTIBOT_MCAPTCHA_SITEKEY: "your-site-key"
    ANTIBOT_MCAPTCHA_SECRET: "your-secret-key"
    ANTIBOT_MCAPTCHA_URL: "https://demo.mcaptcha.org"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```
