from datetime import datetime
from pathlib import Path
from subprocess import PIPE, Popen
from traceback import format_exc

try:
    print(
        'ℹ️ Executing the command "bwcli ban 127.0.0.1 -exp 3600" ...',
        flush=True,
    )

    result = Popen(
        ["bwcli", "ban", "127.0.0.1", "-exp", "3600"],
        stderr=PIPE,
        stdout=PIPE,
    )
    stdout, stderr = result.communicate()

    if result.returncode != 0:
        print(f'❌ Command "ban" failed, exiting ...\noutput: {stderr.decode()}\nexit_code: {result.returncode}')
        exit(1)

    print(stderr.decode(), flush=True)

    print(
        'ℹ️ Executing the command "bwcli bans" and checking the result ...',
        flush=True,
    )

    result = Popen(["bwcli", "bans"], stderr=PIPE, stdout=PIPE)
    stdout, stderr = result.communicate()

    if result.returncode != 0:
        print(f'❌ Command "bans" failed, exiting ...\noutput: {stderr.decode()}\nexit_code: {result.returncode}')
        exit(1)

    if b"- 127.0.0.1" not in stderr:
        print(f'❌ IP 127.0.0.1 not found in the output of "bans", exiting ...\noutput: {stderr.decode()}')
        exit(1)
    elif b"List of bans for redis:" not in stderr:
        print(f'❌ Redis ban list not found in the output of "bans", exiting ...\noutput: {stderr.decode()}')
        exit(1)
    elif b"1 hour" not in stderr and b"59 minutes" not in stderr:
        print(f"❌ Ban duration isn't 1 hour, exiting ...\noutput: {stderr.decode()}")
        exit(1)

    print(
        'ℹ️ Executing the command "bwcli unban 127.0.0.1" ...',
        flush=True,
    )

    result = Popen(["bwcli", "unban", "127.0.0.1"], stderr=PIPE, stdout=PIPE)
    stdout, stderr = result.communicate()

    if result.returncode != 0:
        print(f'❌ Command "unban" failed, exiting ...\noutput: {stderr.decode()}\nexit_code: {result.returncode}')
        exit(1)

    print(stderr.decode(), flush=True)

    print(
        'ℹ️ Executing the command "bwcli bans" to check if the IP was unbanned ...',
        flush=True,
    )

    result = Popen(["bwcli", "bans"], stderr=PIPE, stdout=PIPE)
    stdout, stderr = result.communicate()

    if result.returncode != 0:
        print(f'❌ Command "bans" failed, exiting ...\noutput: {stderr.decode()}\nexit_code: {result.returncode}')
        exit(1)

    found = 0
    for line in stderr.splitlines():
        if b"No ban found" in line:
            found += 1

    if found < 2:
        print(
            f"❌ IP 127.0.0.1 was not unbanned from both redis and the local ban list, exiting ...\noutput: {stderr.decode()}",
            flush=True,
        )
        exit(1)

    print(stderr.decode(), flush=True)

    print("ℹ️ Setting integration metadata to Unknown ...", flush=True)

    result = Popen(["sqlite3", "/var/lib/bunkerweb/db.sqlite3"], stdin=PIPE, stderr=PIPE, stdout=PIPE)
    stdout, stderr = result.communicate(b"UPDATE bw_metadata SET integration = 'Unknown';")

    if result.returncode != 0:
        print(f"❌ Command failed, exiting ...\nexit_code: {result.returncode}\nstdout: {stdout.decode()}\nstderr: {stderr.decode()}", flush=True)
        exit(1)

    print("ℹ️ Checking if the metadata was set correctly ...", flush=True)

    result = Popen(["sqlite3", "/var/lib/bunkerweb/db.sqlite3"], stdin=PIPE, stderr=PIPE, stdout=PIPE)
    stdout, stderr = result.communicate(b"SELECT integration FROM bw_metadata;")

    if result.returncode != 0:
        print(f"❌ Command failed, exiting ...\nexit_code: {result.returncode}\nstdout: {stdout.decode()}\nstderr: {stderr.decode()}", flush=True)
        exit(1)

    if b"Unknown" not in stdout:
        print(f"❌ Metadata was not set correctly, exiting ...\nstdout: {stdout.decode()}\nstderr: {stderr.decode()}", flush=True)
        exit(1)

    print("ℹ️ Metadata was set correctly", flush=True)

    print('ℹ️ Executing the command "bwcli plugin backup save" ...', flush=True)

    result = Popen(["bwcli", "plugin", "backup", "save"], stderr=PIPE, stdout=PIPE)
    stdout, stderr = result.communicate()

    if result.returncode != 0:
        print(
            f'❌ Command "plugin backup save" failed, exiting ...\nexit_code: {result.returncode}\nstdout: {stdout.decode()}\nstderr: {stderr.decode()}',
            flush=True,
        )
        exit(1)

    file = b""
    for line in stdout.splitlines():
        if b"created successfully" in line:
            file = line[line.find(b"Backup") + 7 :].split(b" ")[0].strip()  # noqa: E203
            break

    if not file:
        print(f"❌ Backup was not created successfully, exiting ...\nstdout: {stdout.decode()}\nstderr: {stderr.decode()}", flush=True)
        exit(1)

    print(stderr.decode(), flush=True)

    print(f"ℹ️ Checking if the backup file {file.decode()} exists ...", flush=True)

    result = Popen(["bwcli", "plugin", "backup", "list"], stderr=PIPE, stdout=PIPE)
    stdout, stderr = result.communicate()

    if result.returncode != 0:
        print(
            f"❌ Command failed, exiting ...\nexit_code: {result.returncode}\nstdout: {stdout.decode()}\nstderr: {stderr.decode()}",
            flush=True,
        )
        exit(1)

    date = datetime.strptime("-".join(Path(file.decode()).stem.split("-")[2:]), "%Y-%m-%d_%H-%M-%S").strftime("%d/%m/%Y %H:%M:%S").encode()
    found = False
    for line in stdout.splitlines():
        if date in line:
            found = True
            break

    if not found:
        print(f"❌ Backup {file.decode()} does not exist, exiting ...\nstdout: {stdout.decode()}\nstderr: {stderr.decode()}", flush=True)
        exit(1)

    print(f"ℹ️ Backup {file.decode()} created successfully", flush=True)

    print("ℹ️ Setting integration metadata to Windows ...", flush=True)

    result = Popen(["sqlite3", "/var/lib/bunkerweb/db.sqlite3"], stdin=PIPE, stderr=PIPE, stdout=PIPE)
    stdout, stderr = result.communicate(b"UPDATE bw_metadata SET integration = 'Windows';")

    if result.returncode != 0:
        print(f"❌ Command failed, exiting ...\nexit_code: {result.returncode}\nstdout: {stdout.decode()}\nstderr: {stderr.decode()}", flush=True)
        exit(1)

    print("ℹ️ Checking if the metadata was set correctly ...", flush=True)

    result = Popen(["sqlite3", "/var/lib/bunkerweb/db.sqlite3"], stdin=PIPE, stderr=PIPE, stdout=PIPE)
    stdout, stderr = result.communicate(b"SELECT integration FROM bw_metadata;")

    if result.returncode != 0:
        print(f"❌ Command failed, exiting ...\nexit_code: {result.returncode}\nstdout: {stdout.decode()}\nstderr: {stderr.decode()}", flush=True)
        exit(1)

    if b"Windows" not in stdout:
        print(f"❌ Metadata was not set correctly, exiting ...\nstdout: {stdout.decode()}\nstderr: {stderr.decode()}", flush=True)
        exit(1)

    print("ℹ️ Metadata was set correctly", flush=True)

    print('ℹ️ Executing the command "bwcli plugin backup restore" ...', flush=True)

    result = Popen(["bwcli", "plugin", "backup", "restore", f"/var/lib/bunkerweb/backups/{file.decode()}"], stderr=PIPE, stdout=PIPE)
    stdout, stderr = result.communicate()

    if result.returncode != 0:
        print(
            f'❌ Command "plugin backup restore" failed, exiting ...\nexit_code: {result.returncode}\nstdout: {stdout.decode()}\nstderr: {stderr.decode()}',
            flush=True,
        )
        exit(1)

    backup_file = b""
    found = False
    for line in stdout.splitlines():
        if b"created successfully" in line:
            backup_file = line[line.find(b"Backup") + 7 :].split(b" ")[0].strip()  # noqa: E203
        if b"Database restored successfully from /var/lib/bunkerweb/backups/" + file in line:
            found = True
            break

    if not backup_file:
        print(f"❌ Temporary backup was not created successfully, exiting ...\nstout: {stdout.decode()}\nstderr: {stderr.decode()}", flush=True)
        exit(1)
    elif not found:
        print(f"❌ Database was not restored successfully, exiting ...\nstdout: {stdout.decode()}\nstderr: {stderr.decode()}", flush=True)
        exit(1)

    print(stderr.decode(), flush=True)

    print("ℹ️ Checking if the temporary backup file was created ...", flush=True)

    result = Popen(["ls", "/tmp/bunkerweb/backups"], stderr=PIPE, stdout=PIPE)
    stdout, stderr = result.communicate()

    if result.returncode != 0:
        print(
            f"❌ Temporary backup {backup_file.decode()} does not exist, exiting ...\nexit_code: {result.returncode}\nstout: {stdout.decode()}\nstderr: {stderr.decode()}",
            flush=True,
        )
        exit(1)

    found = False
    for line in stdout.splitlines():
        if backup_file in line:
            found = True
            break

    if not found:
        print(f"❌ Temporary backup {backup_file.decode()} does not exist, exiting ...\nstdout: {stdout.decode()}\nstderr: {stderr.decode()}", flush=True)
        exit(1)

    print(f"ℹ️ Temporary backup {backup_file.decode()} created successfully", flush=True)

    print("ℹ️ Checking if the metadata was restored correctly ...", flush=True)

    result = Popen(["sqlite3", "/var/lib/bunkerweb/db.sqlite3"], stdin=PIPE, stderr=PIPE, stdout=PIPE)
    stdout, stderr = result.communicate(b"SELECT integration FROM bw_metadata;")

    if result.returncode != 0:
        print(f"❌ Command failed, exiting ...\nexit_code: {result.returncode}\nstdout: {stdout.decode()}\nstderr: {stderr.decode()}", flush=True)
        exit(1)

    if b"Unknown" not in stdout:
        print(f"❌ Metadata was not restored correctly, exiting ...\nstdout: {stdout.decode()}\nstderr: {stderr.decode()}", flush=True)
        exit(1)

    print("ℹ️ Metadata was restored correctly", flush=True)

    print("ℹ️ Trying to restore the temporary backup ...", flush=True)

    result = Popen(["bwcli", "plugin", "backup", "restore", f"/tmp/bunkerweb/backups/{backup_file.decode()}"], stderr=PIPE, stdout=PIPE)
    stdout, stderr = result.communicate()

    if result.returncode != 0:
        print(
            f'❌ Command "plugin backup restore" failed, exiting ...\nexit_code: {result.returncode}\nstdout: {stdout.decode()}\nstderr: {stderr.decode()}',
            flush=True,
        )
        exit(1)

    found = False
    for line in stdout.splitlines():
        if b"Database restored successfully from /tmp/bunkerweb/backups/" + backup_file in line:
            found = True
            break

    if not found:
        print(f"❌ Database was not restored successfully, exiting ...\nstdout: {stdout.decode()}\nstderr: {stderr.decode()}", flush=True)
        exit(1)

    print(stderr.decode(), flush=True)

    print("ℹ️ Checking if the metadata was restored correctly ...", flush=True)

    result = Popen(["sqlite3", "/var/lib/bunkerweb/db.sqlite3"], stdin=PIPE, stderr=PIPE, stdout=PIPE)
    stdout, stderr = result.communicate(b"SELECT integration FROM bw_metadata;")

    if result.returncode != 0:
        print(f"❌ Command failed, exiting ...\nexit_code: {result.returncode}\nstdout: {stdout.decode()}\nstderr: {stderr.decode()}", flush=True)
        exit(1)

    if b"Windows" not in stdout:
        print(f"❌ Metadata was not restored correctly, exiting ...\nstdout: {stdout.decode()}\nstderr: {stderr.decode()}", flush=True)
        exit(1)

    print("ℹ️ Metadata was restored correctly", flush=True)
except SystemExit:
    exit(1)
except:
    print(f"❌ Something went wrong, exiting ...\n{format_exc()}", flush=True)
    exit(1)
