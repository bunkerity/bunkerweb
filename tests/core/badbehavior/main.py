from contextlib import suppress
from datetime import datetime
from re import search
from docker import DockerClient
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

    use_bad_behavior = getenv("USE_BAD_BEHAVIOR", "yes") == "yes"
    bad_behavior_status_codes = getenv("BAD_BEHAVIOR_STATUS_CODES", "400 401 403 404 405 429 444")
    bad_behavior_ban_time = getenv("BAD_BEHAVIOR_BAN_TIME", "86400")
    bad_behavior_threshold = getenv("BAD_BEHAVIOR_THRESHOLD", "10")
    bad_behavior_count_time = getenv("BAD_BEHAVIOR_COUNT_TIME", "60")

    print(
        "ℹ️ Sending 15 requests to http://www.example.com/?id=/etc/passwd ...",
        flush=True,
    )

    for _ in range(15):
        get(
            "http://www.example.com/?id=/etc/passwd",
            headers={"Host": "www.example.com"},
        )
        sleep(1.5)

    sleep(3)

    status_code = get("http://www.example.com", headers={"Host": "www.example.com"}).status_code

    if status_code == 403:
        if not use_bad_behavior:
            print("❌ Bad Behavior is enabled, it shouldn't be ...", flush=True)
            exit(1)
        elif bad_behavior_status_codes != "400 401 403 404 405 429 444":
            print("❌ Bad Behavior's status codes didn't changed ...", flush=True)
            exit(1)
        elif bad_behavior_ban_time != "86400":
            print(
                "ℹ️ Sleeping for 65s to wait if Bad Behavior's ban time changed ...",
                flush=True,
            )
            sleep(65)

            status_code = get("http://www.example.com", headers={"Host": "www.example.com"}).status_code

            if status_code == 403:
                print("❌ Bad Behavior's ban time didn't changed ...", flush=True)
                exit(1)
        elif bad_behavior_threshold != "10":
            print("❌ Bad Behavior's threshold didn't changed ...", flush=True)
            exit(1)
        elif bad_behavior_count_time != "60":
            print(
                "ℹ️ Sleeping for 35s to wait if Bad Behavior's count time changed ...",
                flush=True,
            )
            current_time = datetime.now().timestamp()
            sleep(35)

            print(
                "ℹ️ Checking BunkerWeb's logs to see if Bad Behavior's count time changed ...",
                flush=True,
            )

            found = False
            if getenv("TEST_TYPE", "docker") == "docker":
                docker_host = getenv("DOCKER_HOST", "unix:///var/run/docker.sock")
                docker_client = DockerClient(base_url=docker_host)

                bw_instances = docker_client.containers.list(filters={"label": "bunkerweb.INSTANCE"})

                if not bw_instances:
                    print("❌ BunkerWeb instance not found ...", flush=True)
                    exit(1)

                bw_instance = bw_instances[0]

                for log in bw_instance.logs(since=current_time).split(b"\n"):
                    if b"decreased counter for IP 192.168.0.3 (0/10)" in log:
                        found = True
                        break
            else:
                with open("/var/log/bunkerweb/error.log", "r") as f:
                    for line in f.readlines():
                        if search(
                            r"decreased counter for IP \d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3} \(0/10\)",
                            line,
                        ):
                            found = True
                            break

            if not found:
                print("❌ Bad Behavior's count time didn't changed ...", flush=True)
                exit(1)
    elif use_bad_behavior and bad_behavior_status_codes == "400 401 403 404 405 429 444" and bad_behavior_threshold == "10":
        print("❌ Bad Behavior is disabled, it shouldn't be ...", flush=True)
        exit(1)

    print("✅ Bad Behavior is working as expected ...", flush=True)
except SystemExit:
    exit(1)
except:
    print(f"❌ Something went wrong, exiting ...\n{format_exc()}", flush=True)
    exit(1)
