"""The bundled zlib must bind its own symbols (bunkerity/bunkerweb#4237).

lua-ffi-zlib loads /usr/share/bunkerweb/deps/lib/lua/libz.so next to the zlib that nginx links. Without -Bsymbolic the
bundled library resolves inflateReset2() and friends through the PLT to that other zlib, whose inflate_state layout can
differ (zlib 1.4 added fields), so every deflated session cookie fails with "INFLATE: data error".
The linker flags the package build sets (relro, now) must survive: -Bsymbolic is appended, never substituted.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
ZLIB_SRC = ROOT / "src/deps/src/zlib"
HARDENING = "-Wl,-z,relro -Wl,-z,now"


@pytest.mark.skipif(not all(shutil.which(tool) for tool in ("gcc", "make", "readelf")), reason="needs gcc, make and readelf")
@pytest.mark.parametrize("ldflags", [HARDENING, None], ids=["hardened-env", "no-ldflags"])
def test_bundled_zlib_does_not_bind_to_another_zlib(tmp_path, ldflags):
    install = (ROOT / "src/deps/install.sh").read_text()
    prefix = install.split("# Compiling and installing lua\n", 1)[0]
    block = install.split("# Compiling and installing zlib\n", 1)[1].split("# RHEL 10 has no system YAJL", 1)[0]
    src = tmp_path / "zlib"
    shutil.copytree(ZLIB_SRC, src, ignore=shutil.ignore_patterns("contrib", "win32", "os400", "qnx", "watcom", "amiga", "msdos", "nintendods"))

    # Run the production zlib block as is; only the source directory, the job count and the install step change.
    block = block.replace('"/tmp/bunkerweb/deps/src/zlib"', f'"{src}"').replace("do_and_check_cmd make install", "do_and_check_cmd true")
    script = prefix.replace('NTASK="$(nproc)"', "NTASK=2") + block + '\necho "LDFLAGS_AFTER=${LDFLAGS-<unset>}"\n'
    env = {"PATH": subprocess.os.environ["PATH"]}
    if ldflags is not None:
        env["LDFLAGS"] = ldflags
    result = subprocess.run(["bash", "-c", script], env=env, text=True, capture_output=True, cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    # The variable is scoped to the block: later builds in install.sh see what they saw before.
    assert f"LDFLAGS_AFTER={ldflags if ldflags is not None else '<unset>'}" in result.stdout

    shared = next(src.glob("libz.so.[0-9]*.*"))
    dynamic = subprocess.run(["readelf", "-dW", str(shared)], check=True, capture_output=True, text=True).stdout
    assert "SYMBOLIC" in dynamic, "bundled libz.so lost -Bsymbolic"
    assert "(SONAME)" in dynamic and "libz.so.1" in dynamic, "bundled libz.so lost its SONAME"
    if ldflags is not None:
        assert "BIND_NOW" in dynamic, "bundled libz.so lost the linker hardening of the build environment"

    relocs = subprocess.run(["readelf", "-rW", str(shared)], check=True, capture_output=True, text=True).stdout
    bound_to_plt = sorted(
        {line.split()[4].split("@")[0] for line in relocs.splitlines() if "JUMP_SLOT" in line} & {"inflateReset2", "deflateReset", "crc32", "adler32"}
    )
    assert not bound_to_plt, f"bundled libz.so resolves its own functions through the PLT, so another zlib can hijack them: {bound_to_plt}"
