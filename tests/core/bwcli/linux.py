# -*- coding: utf-8 -*-
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
    _, err = result.communicate()

    if result.returncode != 0:
        print(f'❌ Command "ban" failed, exiting ...\noutput: {err.decode()}\nexit_code: {result.returncode}')
        exit(1)

    print(err.decode(), flush=True)

    print(
        'ℹ️ Executing the command "bwcli bans" and checking the result ...',
        flush=True,
    )

    result = Popen(["bwcli", "bans"], stderr=PIPE, stdout=PIPE)
    _, err = result.communicate()

    if result.returncode != 0:
        print(f'❌ Command "bans" failed, exiting ...\noutput: {err.decode()}\nexit_code: {result.returncode}')
        exit(1)

    if b"- 127.0.0.1" not in err:
        print(f'❌ IP 127.0.0.1 not found in the output of "bans", exiting ...\noutput: {err.decode()}')
        exit(1)
    elif b"List of bans for redis:" not in err:
        print(f'❌ Redis ban list not found in the output of "bans", exiting ...\noutput: {err.decode()}')
        exit(1)
    elif b"1 hour" not in err and b"59 minutes" not in err:
        print(f"❌ Ban duration isn't 1 hour, exiting ...\noutput: {err.decode()}")
        exit(1)

    print(
        'ℹ️ Executing the command "bwcli unban 127.0.0.1" ...',
        flush=True,
    )

    result = Popen(["bwcli", "unban", "127.0.0.1"], stderr=PIPE, stdout=PIPE)
    _, err = result.communicate()

    if result.returncode != 0:
        print(f'❌ Command "unban" failed, exiting ...\noutput: {err.decode()}\nexit_code: {result.returncode}')
        exit(1)

    print(err.decode(), flush=True)

    print(
        'ℹ️ Executing the command "bwcli bans" to check if the IP was unbanned ...',
        flush=True,
    )

    result = Popen(["bwcli", "bans"], stderr=PIPE, stdout=PIPE)
    _, err = result.communicate()

    if result.returncode != 0:
        print(f'❌ Command "bans" failed, exiting ...\noutput: {err.decode()}\nexit_code: {result.returncode}')
        exit(1)

    found = 0
    for line in err.splitlines():
        if b"No ban found" in line:
            found += 1

    if found < 2:
        print(
            f"❌ IP 127.0.0.1 was not unbanned from both redis and the local ban list, exiting ...\noutput: {err.decode()}",
            flush=True,
        )
        exit(1)

    print(err.decode(), flush=True)
except SystemExit:
    exit(1)
except:
    print(f"❌ Something went wrong, exiting ...\n{format_exc()}", flush=True)
    exit(1)
