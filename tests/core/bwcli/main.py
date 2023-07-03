from os import getenv
from traceback import format_exc
from docker import DockerClient
from docker.models.containers import Container

try:
    docker_host = getenv("DOCKER_HOST", "unix:///var/run/docker.sock")
    docker_client = DockerClient(base_url=docker_host)

    bw_instances = docker_client.containers.list(
        filters={"label": "bunkerweb.INSTANCE"}
    )

    if not bw_instances:
        print("❌ BunkerWeb instance not found ...", flush=True)
        exit(1)

    bw_instance: Container = bw_instances[0]

    print(
        'ℹ️ Executing the command "bwcli ban 127.0.0.1 -exp 3600" inside the BW container ...',
        flush=True,
    )

    result = bw_instance.exec_run("bwcli ban 127.0.0.1 -exp 3600")

    if result.exit_code != 0:
        print(
            f'❌ Command "ban" failed, exiting ...\noutput: {result.output.decode()}\nexit_code: {result.exit_code}'
        )
        exit(1)

    print(result.output.decode(), flush=True)

    print(
        'ℹ️ Executing the command "bwcli bans" inside the BW container and checking the result ...',
        flush=True,
    )

    result = bw_instance.exec_run("bwcli bans")

    if result.exit_code != 0:
        print(
            f'❌ Command "bans" failed, exiting ...\noutput: {result.output.decode()}\nexit_code: {result.exit_code}'
        )
        exit(1)

    if b"- 127.0.0.1" not in result.output:
        print(
            f'❌ IP 127.0.0.1 not found in the output of "bans", exiting ...\noutput: {result.output.decode()}'
        )
        exit(1)
    elif b"List of bans for redis:" not in result.output:
        print(
            f'❌ Redis ban list not found in the output of "bans", exiting ...\noutput: {result.output.decode()}'
        )
        exit(1)
    elif b"1 hour" not in result.output and b"59 minutes" not in result.output:
        print(
            f"❌ Ban duration isn't 1 hour, exiting ...\noutput: {result.output.decode()}"
        )
        exit(1)

    print(result.output.decode(), flush=True)

    print(
        'ℹ️ Executing the command "bwcli unban 127.0.0.1" inside the BW container ...',
        flush=True,
    )

    result = bw_instance.exec_run("bwcli unban 127.0.0.1")

    if result.exit_code != 0:
        print(
            f'❌ Command "unban" failed, exiting ...\noutput: {result.output.decode()}\nexit_code: {result.exit_code}'
        )
        exit(1)

    print(result.output.decode(), flush=True)

    print(
        'ℹ️ Executing the command "bwcli bans" inside the BW container to check if the IP was unbanned ...',
        flush=True,
    )

    result = bw_instance.exec_run("bwcli bans")

    if result.exit_code != 0:
        print(
            f'❌ Command "bans" failed, exiting ...\noutput: {result.output.decode()}\nexit_code: {result.exit_code}'
        )
        exit(1)

    found = 0
    for line in result.output.splitlines():
        if b"No ban found" in line:
            found += 1

    if found < 2:
        print(
            f"❌ IP 127.0.0.1 was not unbanned from both redis and the local ban list, exiting ...\noutput: {result.output.decode()}",
            flush=True,
        )
        exit(1)

    print(result.output.decode(), flush=True)
except SystemExit:
    exit(1)
except:
    print(f"❌ Something went wrong, exiting ...\n{format_exc()}", flush=True)
    exit(1)
