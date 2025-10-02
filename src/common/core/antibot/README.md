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
    - Uses a customizable character set for CAPTCHA generation.

    **Supported Characters:**

    The CAPTCHA system supports the following character types:

    - **Letters:** All lowercase (a-z) and uppercase (A-Z) letters
    - **Numbers:** 2, 3, 4, 5, 6, 7, 8, 9 (excludes 0 and 1 to avoid confusion)
    - **Special characters:** ```+-/=%"'&_(),.;:?!§`^ÄÖÜßäöüé''‚""„```

    To have the complete set of supported characters, refer to the [Font charmap](https://www.dafont.com/moms-typewriter.charmap?back=theme) of the font used for the CAPTCHA.

    **Configuration Settings:**

    | Setting                    | Default                                                | Context   | Multiple | Description                                                                                                                                                                                                                    |
    | -------------------------- | ------------------------------------------------------ | --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
    | `USE_ANTIBOT`              | `no`                                                   | multisite | no       | **Enable Antibot:** Set to `captcha` to enable the Captcha challenge.                                                                                                                                                          |
    | `ANTIBOT_CAPTCHA_ALPHABET` | `abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ` | multisite | no       | **Captcha Alphabet:** A string of characters to use for generating the CAPTCHA. Supported characters: all letters (a-z, A-Z), numbers 2-9 (excludes 0 and 1), and special characters: ```+-/=%"'&_(),.;:?!§`^ÄÖÜßäöüé''‚""„``` |

    Refer to the [Common Settings](#common-settings) for additional configuration options.

=== "reCAPTCHA"

    When enabled, reCAPTCHA runs in the background (v3) to assign a score based on user behavior. A score lower than the configured threshold will prompt further verification or block the request. For visible challenges (v2), users must interact with the reCAPTCHA widget before continuing.

    There are now two ways to integrate reCAPTCHA:
    - The classic version (site/secret keys, v2/v3 verify endpoint)
    - The new version using Google Cloud (Project ID + API key). The classic version remains available and can be toggled with `ANTIBOT_RECAPTCHA_CLASSIC`.

    For the classic version, obtain your site and secret keys from the [Google reCAPTCHA admin console](https://www.google.com/recaptcha/admin).
    For the new version, create a reCAPTCHA key in your Google Cloud project and use the Project ID and an API key (see the [Google Cloud reCAPTCHA console](https://console.cloud.google.com/security/recaptcha)). A site key is still required.

    **Configuration Settings:**

    | Setting                          | Default | Context   | Multiple | Description |
    | -------------------------------- | ------- | --------- | -------- | ----------- |
    | `USE_ANTIBOT`                    | `no`    | multisite | no       | Enable antibot; set to `recaptcha` to enable reCAPTCHA. |
    | `ANTIBOT_RECAPTCHA_CLASSIC`      | `yes`   | multisite | no       | Use classic reCAPTCHA. Set to `no` to use the new Google Cloud-based version. |
    | `ANTIBOT_RECAPTCHA_SITEKEY`      |         | multisite | no       | reCAPTCHA site key. Required for both classic and new versions. |
    | `ANTIBOT_RECAPTCHA_SECRET`       |         | multisite | no       | reCAPTCHA secret key. Required for the classic version only. |
    | `ANTIBOT_RECAPTCHA_PROJECT_ID`   |         | multisite | no       | Google Cloud Project ID. Required for the new version only. |
    | `ANTIBOT_RECAPTCHA_API_KEY`      |         | multisite | no       | Google Cloud API key used to call the reCAPTCHA Enterprise API. Required for the new version only. |
    | `ANTIBOT_RECAPTCHA_JA3`          |         | multisite | no       | Optional JA3 TLS fingerprint to include in Enterprise assessments. |
    | `ANTIBOT_RECAPTCHA_JA4`          |         | multisite | no       | Optional JA4 TLS fingerprint to include in Enterprise assessments. |
    | `ANTIBOT_RECAPTCHA_SCORE`        | `0.7`   | multisite | no       | Minimum score required to pass (applies to both classic v3 and the new version). |

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
    ANTIBOT_CAPTCHA_ALPHABET: "23456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    ```

    Note: The example above uses numbers 2-9 and all letters, which are the most commonly used characters for CAPTCHA challenges. You can customize the alphabet to include special characters as needed.

=== "reCAPTCHA Classic"

    Example configuration for the classic reCAPTCHA (site/secret keys):

    ```yaml
    USE_ANTIBOT: "recaptcha"
    ANTIBOT_RECAPTCHA_CLASSIC: "yes"
    ANTIBOT_RECAPTCHA_SITEKEY: "your-site-key"
    ANTIBOT_RECAPTCHA_SECRET: "your-secret-key"
    ANTIBOT_RECAPTCHA_SCORE: "0.7"
    ANTIBOT_URI: "/challenge"
    ANTIBOT_TIME_RESOLVE: "60"
    ANTIBOT_TIME_VALID: "86400"
    ```

=== "reCAPTCHA (new)"

    Example configuration for the new Google Cloud-based reCAPTCHA (Project ID + API key):

    ```yaml
    USE_ANTIBOT: "recaptcha"
    ANTIBOT_RECAPTCHA_CLASSIC: "no"
    ANTIBOT_RECAPTCHA_SITEKEY: "your-site-key"
    ANTIBOT_RECAPTCHA_PROJECT_ID: "your-gcp-project-id"
    ANTIBOT_RECAPTCHA_API_KEY: "your-gcp-api-key"
    # Optional fingerprints to improve Enterprise assessments
    # ANTIBOT_RECAPTCHA_JA3: "<ja3-fingerprint>"
    # ANTIBOT_RECAPTCHA_JA4: "<ja4-fingerprint>"
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
