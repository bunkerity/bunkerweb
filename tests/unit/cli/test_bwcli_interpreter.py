"""The installed wrapper must use the packaged Python and preserve argv and exit status."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_bwcli_executes_interpreter_selected_by_shared_helper(tmp_path):
    install = tmp_path / "bunkerweb"
    (install / "helpers").mkdir(parents=True)
    (install / "cli").mkdir()
    interpreter = tmp_path / "packaged python"
    interpreter.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\nexit 23\n')
    interpreter.chmod(0o755)
    (install / "helpers/utils.sh").write_text(f'get_python_bin() {{ printf "%s\\n" "{interpreter}"; }}\n')
    main = install / "cli/main.py"
    main.write_text('#!/bin/sh\nprintf "wrong interpreter\\n"\nexit 99\n')
    main.chmod(0o755)
    wrapper = tmp_path / "bwcli"
    wrapper.write_text((ROOT / "src/common/helpers/bwcli").read_text().replace("/usr/share/bunkerweb", str(install)))
    result = subprocess.run(["bash", str(wrapper), "ban", "two words", "--time", "10"], capture_output=True, text=True, check=False)
    assert result.returncode == 23, result.stderr + result.stdout
    assert result.stdout.splitlines() == [str(main), "ban", "two words", "--time", "10"]
