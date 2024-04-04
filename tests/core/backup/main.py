from datetime import datetime
from os import getenv
from subprocess import PIPE, Popen
from time import sleep
from traceback import format_exc
from typing import List, Tuple, Union

try:
    use_backup = getenv("USE_BACKUP", "no") == "yes"
    backup_dir = getenv("BACKUP_DIRECTORY", "/var/lib/bunkerweb/backups")
    backup_rotation = int(getenv("BACKUP_ROTATION", "7"))

    if backup_rotation < 1:
        backup_rotation = 1

    scheduler_instance = None
    if getenv("TEST_TYPE", "docker") == "docker":
        from docker import DockerClient
        from docker.models.containers import Container

        docker_client = DockerClient(base_url=getenv("DOCKER_HOST", "unix:///var/run/docker.sock"))

        scheduler_instances = docker_client.containers.list(filters={"label": "bunkerweb.SCHEDULER"})

        if not scheduler_instances:
            print("❌ Scheduler instance not found ...", flush=True)
            exit(1)

        scheduler_instance = scheduler_instances[0]  # type: ignore
        assert isinstance(scheduler_instance, Container), "Scheduler instance is not a container"

    def exec_command(command: Union[str, List[str]]) -> Tuple[int, str, str]:
        if scheduler_instance:
            result = scheduler_instance.exec_run(command)

            assert isinstance(result.exit_code, int), "Exit code is not an integer"
            assert isinstance(result.output, bytes), "Output is not bytes"

            return result.exit_code, result.output.decode() if result.output else "", ""

        result = Popen(command, stderr=PIPE, stdout=PIPE, universal_newlines=True, text=True)
        stdout, stderr = result.communicate()
        return result.returncode, stdout, stderr

    print(f"ℹ️ Generating {backup_rotation + 1} backups ...", flush=True)

    for _ in range(backup_rotation + 1):
        result = exec_command(["bwcli", "plugin", "backup", "save"])
        if result[0] != 0:
            print(f"❌ Backup failed:\nstdout={result[1]}\nstderr={result[2]}", flush=True)
            exit(1)

    print("ℹ️ Checking backup directory ...", flush=True)

    result = exec_command(["ls", backup_dir])

    if result[0] != 0:
        print(f"❌ Backup directory not found:\nstdout={result[1]}\nstderr={result[2]}", flush=True)
        exit(1)

    backup_files = result[1].split("\n")[:-1]
    if len(backup_files) < backup_rotation + 1:
        print(f"❌ Backup files count is less than expected:\nstdout={result[1]}\nstderr={result[2]}", flush=True)
        exit(1)

    print("ℹ️ Backups are generated successfully", flush=True)

    print("ℹ️ Reloading BunkerWeb ...", flush=True)

    current_time = datetime.now()
    if scheduler_instance:
        scheduler_instance.restart()
        scheduler_instance.reload()

        while scheduler_instance.health != "healthy" and (datetime.now() - current_time).seconds < 60:
            print("⏳ Waiting for the scheduler to be healthy, retrying in 1s ...", flush=True)
            scheduler_instance.reload()
            sleep(1)

        if scheduler_instance.health != "healthy":
            print("❌ The scheduler took too long to be healthy, exiting ...", flush=True)
            exit(1)
    else:
        exit_code = exec_command(["sudo", "truncate", "-s", "0", "/var/log/bunkerweb/error.log"])[0]
        if exit_code != 0:
            print("❌ An error occurred when truncating the error log, exiting ...", flush=True)
            exit(1)

        exit_code = exec_command(["sudo", "systemctl", "restart", "bunkerweb"])[0]
        if exit_code != 0:
            print("❌ An error occurred when restarting BunkerWeb, exiting ...", flush=True)
            exit(1)

        ready = False
        while not ready and (datetime.now() - current_time).seconds < 60:
            print("⏳ Waiting for BunkerWeb to be ready, retrying in 1s ...", flush=True)
            exit_code, stdout, stderr = exec_command(["sudo", "grep", "BunkerWeb is ready", "/var/log/bunkerweb/error.log"])
            if exit_code == 0:
                ready = True
            sleep(1)

        if not ready:
            print("❌ BunkerWeb took too long to be ready, exiting ...", flush=True)
            exit(1)

    print("ℹ️ Checking rotated backups ...", flush=True)

    result = exec_command(["ls", backup_dir])

    if result[0] != 0:
        print(f"❌ Backup directory not found:\nstdout={result[1]}\nstderr={result[2]}", flush=True)
        exit(1)

    if use_backup:
        backup_files = result[1].split("\n")[:-1]
        if len(backup_files) != backup_rotation:
            print(f"❌ Backup files count is more than expected, the rotation failed:\nstdout={result[1]}\nstderr={result[2]}", flush=True)
            exit(1)
    else:
        backup_files = result[1].split("\n")[:-1]
        if len(backup_files) != backup_rotation + 1:
            print(f"❌ Backup files count is not as expected, the rotation failed:\nstdout={result[1]}\nstderr={result[2]}", flush=True)
            exit(1)

    print("✅ Backup tests completed successfully", flush=True)
except SystemExit as se:
    exit(se.code)
except:
    print(f"❌ Something went wrong, exiting ...\n{format_exc()}", flush=True)
    exit(1)
