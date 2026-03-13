from datetime import datetime
from os import environ, getenv, sep
from pathlib import Path
from subprocess import PIPE, Popen
from time import sleep
from traceback import format_exc
from typing import List, Tuple, Union

try:
    use_backup = getenv("USE_BACKUP", "yes") == "yes"
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
        sleep(1)

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

        sleep(3)

        ready = False
        healthy_path = Path(sep, "var", "tmp", "bunkerweb", "scheduler.healthy")
        while not ready and (datetime.now() - current_time).seconds < 60:
            print("⏳ Waiting for BunkerWeb to be ready, retrying in 1s ...", flush=True)
            if healthy_path.is_file():
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

    print("ℹ️ Testing checksum verification ...", flush=True)

    # Create a fresh backup dedicated to checksum tests
    result = exec_command(["bwcli", "plugin", "backup", "save"])
    if result[0] != 0:
        print(f"❌ Backup for checksum test failed:\nstdout={result[1]}\nstderr={result[2]}", flush=True)
        exit(1)

    # Find the most recently created backup file
    result = exec_command(["ls", "-1t", backup_dir])
    if result[0] != 0:
        print(f"❌ Backup directory listing failed:\nstdout={result[1]}\nstderr={result[2]}", flush=True)
        exit(1)

    checksum_test_files = [f for f in result[1].strip().split("\n") if f.startswith("backup-") and f.endswith(".zip")]
    if not checksum_test_files:
        print("❌ No backup files found for checksum test", flush=True)
        exit(1)

    latest_backup = f"{backup_dir}/{checksum_test_files[0]}"

    # Corrupt the stored .sha256 (replace hash with all-zeros) while keeping the SQL intact.
    # This ensures 'check' and 'restore' fail on mismatch, but 'restore' with the ignore flag
    # can actually complete successfully (valid SQL, just a bad hash record).
    corrupt_script = (
        "import zipfile; "
        f"f='{latest_backup}'; "
        "zin=zipfile.ZipFile(f,'r'); "
        "names=zin.namelist(); "
        "contents={n: zin.read(n) for n in names}; "
        "zin.close(); "
        "sha=[n for n in names if n.endswith('.sha256')][0]; "
        "contents[sha]=b'0000000000000000000000000000000000000000000000000000000000000000  ' + sha[:-7].encode() + b'\\n'; "
        "zout=zipfile.ZipFile(f,'w',compression=zipfile.ZIP_DEFLATED); "
        "[zout.writestr(n,d) for n,d in contents.items()]; "
        "zout.close()"
    )
    result = exec_command(["python3", "-c", corrupt_script])
    if result[0] != 0:
        print(f"❌ Failed to corrupt backup file:\nstdout={result[1]}\nstderr={result[2]}", flush=True)
        exit(1)

    # Test 1: 'bwcli plugin backup check' must exit non-zero when a checksum is bad
    print("ℹ️ Verifying that 'bwcli plugin backup check' detects checksum mismatch ...", flush=True)
    result = exec_command(["bwcli", "plugin", "backup", "check"])
    if result[0] == 0:
        print(f"❌ 'bwcli plugin backup check' should have failed but returned 0:\nstdout={result[1]}\nstderr={result[2]}", flush=True)
        exit(1)
    print("✅ 'bwcli plugin backup check' correctly detected checksum mismatch", flush=True)

    # Test 2: restore must abort when checksum does not match
    print("ℹ️ Verifying that restore aborts on checksum mismatch ...", flush=True)
    result = exec_command(["bwcli", "plugin", "backup", "restore", latest_backup])
    if result[0] == 0:
        print(f"❌ 'bwcli plugin backup restore' should have failed but returned 0:\nstdout={result[1]}\nstderr={result[2]}", flush=True)
        exit(1)
    print("✅ 'bwcli plugin backup restore' correctly aborted on checksum mismatch", flush=True)

    # Test 3: restore must succeed when BACKUP_IGNORE_CHECKSUM_ERROR_ON_DB_RESTORE=yes
    print("ℹ️ Verifying that restore proceeds with BACKUP_IGNORE_CHECKSUM_ERROR_ON_DB_RESTORE=yes ...", flush=True)
    ignore_env = {"BACKUP_IGNORE_CHECKSUM_ERROR_ON_DB_RESTORE": "yes"}
    if scheduler_instance:
        result_obj = scheduler_instance.exec_run(
            ["bwcli", "plugin", "backup", "restore", latest_backup],
            environment=ignore_env,
        )
        rc = result_obj.exit_code
        out = result_obj.output.decode() if result_obj.output else ""
    else:
        proc = Popen(
            ["bwcli", "plugin", "backup", "restore", latest_backup],
            stdout=PIPE,
            stderr=PIPE,
            universal_newlines=True,
            text=True,
            env={**environ, **ignore_env},
        )
        out, _ = proc.communicate()
        rc = proc.returncode
    if rc != 0:
        print(f"❌ Restore with BACKUP_IGNORE_CHECKSUM_ERROR_ON_DB_RESTORE=yes failed (exit {rc}):\n{out}", flush=True)
        exit(1)
    print("✅ Restore proceeded correctly with BACKUP_IGNORE_CHECKSUM_ERROR_ON_DB_RESTORE=yes", flush=True)

    print("✅ Backup tests completed successfully", flush=True)
except SystemExit as se:
    exit(se.code)
except:
    print(f"❌ Something went wrong, exiting ...\n{format_exc()}", flush=True)
    exit(1)
