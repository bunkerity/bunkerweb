from contextlib import suppress
from datetime import datetime
from re import search
from os import getenv
from requests import get
from requests.exceptions import RequestException
from time import sleep
from traceback import format_exc

try:
    ready = False
    retries = 0
    while not ready:
        with suppress(RequestException):
            resp = get("http://www.example.com/ready", headers={"Host": "www.example.com"})
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

    use_modsecurity = getenv("USE_MODSECURITY", "yes") == "yes"
    use_modsecurity_crs = getenv("USE_MODSECURITY_CRS", "yes") == "yes"
    modsecurity_crs_version = getenv("MODSECURITY_CRS_VERSION", "3")

    current_time = datetime.now().timestamp()

    print(
        "ℹ️ Sending a requests to http://www.example.com/?id=/etc/passwd ...",
        flush=True,
    )

    status_code = get("http://www.example.com/?id=/etc/passwd", headers={"Host": "www.example.com"}).status_code

    print(f"ℹ️ Status code: {status_code}", flush=True)

    if status_code == 403:
        if not use_modsecurity:
            print(
                "❌ ModSecurity should have been disabled, exiting ...",
                flush=True,
            )
            exit(1)
        elif not use_modsecurity_crs:
            print(
                "❌ ModSecurity CRS should have been disabled, exiting ...",
                flush=True,
            )
            exit(1)
    elif use_modsecurity and use_modsecurity_crs:
        print("❌ ModSecurity is not working as expected, exiting ...", flush=True)
        exit(1)

    if use_modsecurity and use_modsecurity_crs:
        found = False
        if getenv("TEST_TYPE", "docker") == "docker":
            from docker import DockerClient

            docker_host = getenv("DOCKER_HOST", "unix:///var/run/docker.sock")
            docker_client = DockerClient(base_url=docker_host)

            bw_instances = docker_client.containers.list(filters={"label": "bunkerweb.INSTANCE"})

            if not bw_instances:
                print("❌ BunkerWeb instance not found ...", flush=True)
                exit(1)

            bw_instance = bw_instances[0]

            for log in bw_instance.logs(since=current_time).split(b"\n"):
                if (
                    modsecurity_crs_version == "nightly" and b'[file "/var/cache/bunkerweb/modsecurity/crs/crs-nightly' in log
                ) or f'[ver "OWASP_CRS/{modsecurity_crs_version}'.encode() in log:
                    found = True
                    break
        else:
            with open("/var/log/bunkerweb/error.log", "r") as f:
                for line in f.readlines():
                    if (modsecurity_crs_version == "nightly" and search(r'\[file "/var/cache/bunkerweb/modsecurity/crs/crs-nightly', line)) or search(
                        r'\[ver "OWASP_CRS/' + modsecurity_crs_version, line
                    ):
                        found = True
                        break

        if not found:
            print("❌ ModSecurity CRS doesn't use the expected version, exiting ...", flush=True)
            exit(1)

    print("✅ ModSecurity is working as expected ...", flush=True)
except SystemExit:
    exit(1)
except:
    print(f"❌ Something went wrong, exiting ...\n{format_exc()}", flush=True)
    exit(1)
