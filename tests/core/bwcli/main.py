from datetime import datetime
from os import getenv
from pathlib import Path
from traceback import format_exc
from docker import DockerClient
from docker.models.containers import Container

try:
    docker_host = getenv("DOCKER_HOST", "unix:///var/run/docker.sock")
    docker_client = DockerClient(base_url=docker_host)

    bw_instances = docker_client.containers.list(filters={"label": "bunkerweb.INSTANCE"})

    if not bw_instances:
        print("❌ BunkerWeb instance not found ...", flush=True)
        exit(1)

    bw_instance: Container = bw_instances[0]

    print('ℹ️ Executing the command "bwcli ban 127.0.0.1 -exp 3600" inside the BW container ...', flush=True)

    result = bw_instance.exec_run("bwcli ban 127.0.0.1 -exp 3600")

    if result.exit_code != 0:
        print(f'❌ Command "ban" failed, exiting ...\noutput: {result.output.decode()}\nexit_code: {result.exit_code}')
        exit(1)

    print(result.output.decode(), flush=True)

    print('ℹ️ Executing the command "bwcli bans" inside the BW container and checking the result ...', flush=True)

    result = bw_instance.exec_run("bwcli bans")

    if result.exit_code != 0:
        print(f'❌ Command "bans" failed, exiting ...\noutput: {result.output.decode()}\nexit_code: {result.exit_code}')
        exit(1)

    if b"- 127.0.0.1" not in result.output:
        print(f'❌ IP 127.0.0.1 not found in the output of "bans", exiting ...\noutput: {result.output.decode()}')
        exit(1)
    elif b"List of bans for redis:" not in result.output:
        print(f'❌ Redis ban list not found in the output of "bans", exiting ...\noutput: {result.output.decode()}')
        exit(1)
    elif b"1 hour" not in result.output and b"59 minutes" not in result.output:
        print(f"❌ Ban duration isn't 1 hour, exiting ...\noutput: {result.output.decode()}")
        exit(1)

    print(result.output.decode(), flush=True)

    print('ℹ️ Executing the command "bwcli unban 127.0.0.1" inside the BW container ...', flush=True)

    result = bw_instance.exec_run("bwcli unban 127.0.0.1")

    if result.exit_code != 0:
        print(f'❌ Command "unban" failed, exiting ...\noutput: {result.output.decode()}\nexit_code: {result.exit_code}')
        exit(1)

    print(result.output.decode(), flush=True)

    print('ℹ️ Executing the command "bwcli bans" inside the BW container to check if the IP was unbanned ...', flush=True)

    result = bw_instance.exec_run("bwcli bans")

    if result.exit_code != 0:
        print(f'❌ Command "bans" failed, exiting ...\noutput: {result.output.decode()}\nexit_code: {result.exit_code}')
        exit(1)

    found = 0
    for line in result.output.splitlines():
        if b"No ban found" in line:
            found += 1

    if found < 2:
        print(f"❌ IP 127.0.0.1 was not unbanned from both redis and the local ban list, exiting ...\noutput: {result.output.decode()}", flush=True)
        exit(1)

    print(result.output.decode(), flush=True)

    print('ℹ️ Executing the command "bwcli plugin backup save" inside the BW container ...', flush=True)

    result = bw_instance.exec_run("bwcli plugin backup save")

    if result.exit_code == 0:
        print(f"❌ Command 'plugin backup save' should have failed, exiting ...\noutput: {result.output.decode()}\nexit_code: {result.exit_code}", flush=True)
        exit(1)

    print("ℹ️ Command 'plugin backup save' failed as expected", flush=True)

    scheduler_instances = docker_client.containers.list(filters={"label": "bunkerweb.SCHEDULER"})

    if not scheduler_instances:
        print("❌ BunkerWeb instance not found ...", flush=True)
        exit(1)

    scheduler_instance: Container = scheduler_instances[0]

    print("ℹ️ Setting integration metadata to Unknown ...", flush=True)

    result = scheduler_instance.exec_run("sqlite3 /var/lib/bunkerweb/db.sqlite3 \"UPDATE bw_metadata SET integration = 'Unknown';\"")

    if result.exit_code != 0:
        print(f"❌ Command failed, exiting ...\noutput: {result.output.decode()}\nexit_code: {result.exit_code}", flush=True)
        exit(1)

    print("ℹ️ Checking if the metadata was set correctly ...", flush=True)

    result = scheduler_instance.exec_run('sqlite3 /var/lib/bunkerweb/db.sqlite3 "SELECT integration FROM bw_metadata;"')

    if result.exit_code != 0:
        print(f"❌ Command failed, exiting ...\noutput: {result.output.decode()}\nexit_code: {result.exit_code}", flush=True)
        exit(1)

    if b"Unknown" not in result.output:
        print(f"❌ Metadata was not set correctly, exiting ...\noutput: {result.output.decode()}", flush=True)
        exit(1)

    print("ℹ️ Metadata was set correctly", flush=True)

    print('ℹ️ Executing the command "bwcli plugin backup save" inside the Scheduler container ...', flush=True)

    result = scheduler_instance.exec_run("bwcli plugin backup save")

    if result.exit_code != 0:
        print(f'❌ Command "plugin backup save" failed, exiting ...\noutput: {result.output.decode()}\nexit_code: {result.exit_code}')
        exit(1)

    file = b""
    for line in result.output.splitlines():
        if b"created successfully" in line:
            file = line[line.find(b"Backup") + 7 :].split(b" ")[0].strip()  # noqa: E203
            break

    if not file:
        print(f"❌ Backup was not created successfully, exiting ...\noutput: {result.output.decode()}", flush=True)
        exit(1)

    print(result.output.decode(), flush=True)

    print(f"ℹ️ Checking if the backup file {file.decode()} exists ...", flush=True)

    result = scheduler_instance.exec_run("bwcli plugin backup list")

    if result.exit_code != 0:
        print(f"❌ Command failed, exiting ...\noutput: {result.output.decode()}\nexit_code: {result.exit_code}", flush=True)
        exit(1)

    date = datetime.strptime("-".join(Path(file.decode()).stem.split("-")[2:]), "%Y-%m-%d_%H-%M-%S").strftime("%Y/%m/%d %H:%M:%S").encode()
    found = False
    for line in result.output.splitlines():
        if date in line:
            found = True
            break

    if not found:
        print(f"❌ Backup {file.decode()} does not exist, exiting ...\noutput: {result.output.decode()}", flush=True)
        exit(1)

    print(f"ℹ️ Backup {file.decode()} created successfully", flush=True)

    print("ℹ️ Setting integration metadata to Windows ...", flush=True)

    result = scheduler_instance.exec_run("sqlite3 /var/lib/bunkerweb/db.sqlite3 \"UPDATE bw_metadata SET integration = 'Windows';\"")

    if result.exit_code != 0:
        print(f"❌ Command failed, exiting ...\noutput: {result.output.decode()}\nexit_code: {result.exit_code}", flush=True)
        exit(1)

    print("ℹ️ Checking if the metadata was set correctly ...", flush=True)

    result = scheduler_instance.exec_run('sqlite3 /var/lib/bunkerweb/db.sqlite3 "SELECT integration FROM bw_metadata;"')

    if result.exit_code != 0:
        print(f"❌ Command failed, exiting ...\noutput: {result.output.decode()}\nexit_code: {result.exit_code}", flush=True)
        exit(1)

    if b"Windows" not in result.output:
        print(f"❌ Metadata was not set correctly, exiting ...\noutput: {result.output.decode()}", flush=True)
        exit(1)

    print("ℹ️ Metadata was set correctly", flush=True)

    print('ℹ️ Executing the command "bwcli plugin backup restore" inside the Scheduler container ...', flush=True)

    result = scheduler_instance.exec_run("bwcli plugin backup restore")

    if result.exit_code != 0:
        print(f'❌ Command "plugin backup restore" failed, exiting ...\noutput: {result.output.decode()}\nexit_code: {result.exit_code}')
        exit(1)

    backup_file = b""
    found = False
    for line in result.output.splitlines():
        if b"created successfully" in line:
            backup_file = line[line.find(b"Backup") + 7 :].split(b" ")[0].strip()  # noqa: E203
        if b"Database restored successfully from /var/lib/bunkerweb/backups/" + file in line:
            found = True
            break

    if not backup_file:
        print(f"❌ Temporary backup was not created successfully, exiting ...\noutput: {result.output.decode()}", flush=True)
        exit(1)
    elif not found:
        print(f"❌ Database was not restored successfully, exiting ...\noutput: {result.output.decode()}", flush=True)
        exit(1)

    print(result.output.decode(), flush=True)

    print("ℹ️ Checking if the temporary backup file was created ...", flush=True)

    result = scheduler_instance.exec_run("ls /tmp/bunkerweb/backups")

    if result.exit_code != 0:
        print(
            f"❌ Temporary backup {backup_file.decode()} does not exist, exiting ...\noutput: {result.output.decode()}\nexit_code: {result.exit_code}",
            flush=True,
        )
        exit(1)

    found = False
    for line in result.output.splitlines():
        if backup_file in line:
            found = True
            break

    if not found:
        print(f"❌ Temporary backup {backup_file.decode()} does not exist, exiting ...\noutput: {result.output.decode()}", flush=True)
        exit(1)

    print(f"ℹ️ Temporary backup {backup_file.decode()} created successfully", flush=True)

    print("ℹ️ Checking if the metadata was restored correctly ...", flush=True)

    result = scheduler_instance.exec_run('sqlite3 /var/lib/bunkerweb/db.sqlite3 "SELECT integration FROM bw_metadata;"')

    if result.exit_code != 0:
        print(f"❌ Command failed, exiting ...\noutput: {result.output.decode()}\nexit_code: {result.exit_code}", flush=True)
        exit(1)

    if b"Unknown" not in result.output:
        print(f"❌ Metadata was not restored correctly, exiting ...\noutput: {result.output.decode()}", flush=True)
        exit(1)

    print("ℹ️ Metadata was restored correctly", flush=True)

    print("ℹ️ Trying to restore the temporary backup ...", flush=True)

    result = scheduler_instance.exec_run(f"bwcli plugin backup restore /tmp/bunkerweb/backups/{backup_file.decode()}")

    if result.exit_code != 0:
        print(f'❌ Command "plugin backup restore" failed, exiting ...\noutput: {result.output.decode()}\nexit_code: {result.exit_code}')
        exit(1)

    found = False
    for line in result.output.splitlines():
        if b"Database restored successfully from /tmp/bunkerweb/backups/" + backup_file in line:
            found = True
            break

    if not found:
        print(f"❌ Database was not restored successfully, exiting ...\noutput: {result.output.decode()}", flush=True)
        exit(1)

    print(result.output.decode(), flush=True)

    print("ℹ️ Checking if the metadata was restored correctly ...", flush=True)

    result = scheduler_instance.exec_run('sqlite3 /var/lib/bunkerweb/db.sqlite3 "SELECT integration FROM bw_metadata;"')

    if result.exit_code != 0:
        print(f"❌ Command failed, exiting ...\noutput: {result.output.decode()}\nexit_code: {result.exit_code}", flush=True)
        exit(1)

    if b"Windows" not in result.output:
        print(f"❌ Metadata was not restored correctly, exiting ...\noutput: {result.output.decode()}", flush=True)
        exit(1)

    print("ℹ️ Metadata was restored correctly", flush=True)
except SystemExit:
    exit(1)
except:
    print(f"❌ Something went wrong, exiting ...\n{format_exc()}", flush=True)
    exit(1)
