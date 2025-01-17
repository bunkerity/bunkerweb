from contextlib import suppress
from os import getenv
from requests import RequestException, get, head
from traceback import format_exc
from time import sleep


try:
    ssl = getenv("GENERATE_SELF_SIGNED_SSL", "no") == "yes"

    ready = False
    retries = 0
    while not ready:
        with suppress(RequestException):
            resp = get(
                f"http{'s' if ssl else ''}://www.example.com/ready",
                headers={"Host": "www.example.com"},
                verify=False,
            )
            status_code = resp.status_code
            text = resp.text

            if status_code >= 500:
                print("❌ An error occurred with the server, exiting ...", flush=True)
                exit(1)

            ready = status_code < 400 and text == "ready"

        if retries > 10:
            print("❌ The service took too long to be ready, exiting ...", flush=True)
            exit(1)
        elif not ready:
            retries += 1
            print("⚠️ Waiting for the service to be ready, retrying in 5s ...", flush=True)
            sleep(5)

    custom_headers = getenv("CUSTOM_HEADER", "")
    remove_headers = getenv("REMOVE_HEADERS", "Server X-Powered-By X-AspNet-Version X-AspNetMvc-Version")
    keep_upstream_headers = getenv("KEEP_UPSTREAM_HEADERS", "Content-Security-Policy X-Frame-Options")
    strict_transport_security = getenv("STRICT_TRANSPORT_SECURITY", "max-age=31536000; includeSubDomains; preload")
    cookie_flags = getenv("COOKIE_FLAGS", "* HttpOnly SameSite=Lax")
    cookie_flags_1 = getenv("COOKIE_FLAGS_1")
    cookie_auto_secure_flag = getenv("COOKIE_AUTO_SECURE_FLAG", "yes") == "yes"
    content_security_policy = getenv(
        "CONTENT_SECURITY_POLICY",
        "object-src 'none'; form-action 'self'; frame-ancestors 'self';",
    )
    content_security_policy_report_only = getenv("CONTENT_SECURITY_POLICY_REPORT_ONLY", "no") == "yes"
    referrer_policy = getenv("REFERRER_POLICY", "strict-origin-when-cross-origin")
    permissions_policy = getenv(
        "PERMISSIONS_POLICY",
        "accelerometer=(), ambient-light-sensor=(), attribution-reporting=(), autoplay=(), battery=(), bluetooth=(), browsing-topics=(), camera=(), compute-pressure=(), display-capture=(), document-domain=(), encrypted-media=(), execution-while-not-rendered=(), execution-while-out-of-viewport=(), fullscreen=(), gamepad=(), geolocation=(), gyroscope=(), hid=(), identity-credentials-get=(), idle-detection=(), local-fonts=(), magnetometer=(), microphone=(), midi=(), otp-credentials=(), payment=(), picture-in-picture=(), publickey-credentials-create=(), publickey-credentials-get=(), screen-wake-lock=(), serial=(), speaker-selection=(), storage-access=(), usb=(), web-share=(), window-management=(), xr-spatial-tracking=()",  # noqa: E501
    )
    x_frame_options = getenv("X_FRAME_OPTIONS", "SAMEORIGIN")
    x_content_type_options = getenv("X_CONTENT_TYPE_OPTIONS", "nosniff")
    x_xss_protection = getenv("X_XSS_PROTECTION", "1; mode=block")
    x_dns_prefetch_control = getenv("X_DNS_PREFETCH_CONTROL", "off")

    print(
        f"ℹ️ Sending a HEAD request to http{'s' if ssl else ''}://www.example.com ...",
        flush=True,
    )

    response = head(
        f"http{'s' if ssl else ''}://www.example.com",
        headers={"Host": "www.example.com"},
        verify=False,
    )
    response.raise_for_status()

    if custom_headers:
        split = custom_headers.split(":")

        if response.headers.get(split[0].strip()) != split[1].strip():
            print(
                f"❌ Header {split[0].strip()} is not set to {split[1].strip()}, exiting ...\nheaders: {response.headers}",
                flush=True,
            )
            exit(1)
    elif "Server" not in remove_headers and "Server" not in response.headers:
        print(
            f'❌ Header "Server" is not removed, exiting ...\nheaders: {response.headers}',
            flush=True,
        )
        exit(1)
    elif ssl and response.headers.get("Strict-Transport-Security") != strict_transport_security:
        print(
            f'❌ Header "Strict-Transport-Security" doesn\'t have the right value. {response.headers.get("Strict-Transport-Security", "missing header")} (header) != {strict_transport_security} (env), exiting ...\nheaders: {response.headers}',
            flush=True,
        )
        exit(1)
    elif not ssl and "Strict-Transport-Security" in response.headers:
        print(
            f'❌ Header "Strict-Transport-Security" is present even though ssl is deactivated, exiting ...\nheaders: {response.headers}',
            flush=True,
        )
        exit(1)
    elif (
        response.headers.get("Content-Security-Policy-Report-Only" if content_security_policy_report_only else "Content-Security-Policy")
        != content_security_policy
    ):
        print(
            f'❌ Header "{"Content-Security-Policy-Report-Only" if content_security_policy_report_only else "Content-Security-Policy"}" doesn\'t have the right value. {response.headers.get("Content-Security-Policy-Report-Only" if content_security_policy_report_only else "Content-Security-Policy", "missing header")} (header) != {content_security_policy} (env), exiting ...\nheaders: {response.headers}',
            flush=True,
        )
        exit(1)
    elif response.headers.get("Referrer-Policy") != referrer_policy:
        print(
            f'❌ Header "Referrer-Policy" doesn\'t have the right value. {response.headers.get("Referrer-Policy", "missing header")} (header) != {referrer_policy} (env), exiting ...\nheaders: {response.headers}',
            flush=True,
        )
        exit(1)
    elif ("Permissions-Policy" not in keep_upstream_headers and keep_upstream_headers != "*") and response.headers.get(
        "Permissions-Policy"
    ) != permissions_policy:
        print(
            f'❌ Header "Permissions-Policy" doesn\'t have the right value. {response.headers.get("Permissions-Policy", "missing header")} (header) != {permissions_policy} (env), exiting ...\nheaders: {response.headers}',
            flush=True,
        )
        exit(1)
    elif ("Permissions-Policy" in keep_upstream_headers or keep_upstream_headers == "*") and response.headers.get("Permissions-Policy") == permissions_policy:
        print(
            f'❌ Header "Permissions-Policy" was not kept even though it was supposed to be. {response.headers.get("Permissions-Policy", "missing header")} (header) != {permissions_policy} (env), exiting ...\nheaders: {response.headers}',
            flush=True,
        )
        exit(1)
    elif response.headers.get("X-Frame-Options") != x_frame_options:
        print(
            f'❌ Header "X-Frame-Options" doesn\'t have the right value. {response.headers.get("X-Frame-Options", "missing header")} (header) != {x_frame_options} (env), exiting ...\nheaders: {response.headers}',
            flush=True,
        )
        exit(1)
    elif response.headers.get("X-Content-Type-Options") != x_content_type_options:
        print(
            f'❌ Header "X-Content-Type-Options" doesn\'t have the right value. {response.headers.get("X-Content-Type-Options", "missing header")} (header) != {x_content_type_options} (env), exiting ...\nheaders: {response.headers}',
            flush=True,
        )
        exit(1)
    elif response.headers.get("X-XSS-Protection") != x_xss_protection:
        print(
            f'❌ Header "X-XSS-Protection" doesn\'t have the right value. {response.headers.get("X-XSS-Protection", "missing header")} (header) != {x_xss_protection} (env), exiting ...\nheaders: {response.headers}',
            flush=True,
        )
        exit(1)
    elif response.headers.get("X-DNS-Prefetch-Control") != x_dns_prefetch_control:
        print(
            f'❌ Header "X-DNS-Prefetch-Control" doesn\'t have the right value. {response.headers.get("X-DNS-Prefetch-Control", "missing header")} (header) != {x_dns_prefetch_control} (env), exiting ...\nheaders: {response.headers}',
            flush=True,
        )
        exit(1)

    if not response.cookies:
        print("❌ No cookies were set, exiting ...", flush=True)
        exit(1)

    cookie = next(iter(response.cookies))

    # Iterate over the cookies and print their values and flags
    if ssl and cookie_auto_secure_flag and not cookie.secure:
        print(
            f"❌ Cookie {cookie.name} doesn't have the secure flag, exiting ...\ncookie: name = {cookie.name}, secure = {cookie.secure}, HttpOnly = {cookie.has_nonstandard_attr('HttpOnly')}",
        )
        exit(1)
    elif (not ssl or not cookie_auto_secure_flag) and cookie.secure:
        print(
            f"❌ Cookie {cookie.name} has the secure flag even though it's not supposed to, exiting ...\ncookie: name = {cookie.name}, secure = {cookie.secure}, HttpOnly = {cookie.has_nonstandard_attr('HttpOnly')}",
        )
        exit(1)
    elif "HttpOnly" not in cookie_flags and cookie.has_nonstandard_attr("HttpOnly"):
        print(
            f"❌ Cookie {cookie.name} has the HttpOnly flag even though it's not supposed to, exiting ...\ncookie: name = {cookie.name}, secure = {cookie.secure}, HttpOnly = {cookie.has_nonstandard_attr('HttpOnly')}",
        )
        exit(1)
    elif not cookie_flags_1 and "HttpOnly" in cookie_flags and not cookie.has_nonstandard_attr("HttpOnly"):
        print(
            f"❌ Cookie {cookie.name} doesn't have the HttpOnly flag even though it's set in the env, exiting ...\ncookie: name = {cookie.name}, secure = {cookie.secure}, HttpOnly = {cookie.has_nonstandard_attr('HttpOnly')}",
        )
        exit(1)

    print("✅ Headers are working as expected ...", flush=True)
except SystemExit:
    exit(1)
except:
    print(f"❌ Something went wrong, exiting ...\n{format_exc()}", flush=True)
    exit(1)
