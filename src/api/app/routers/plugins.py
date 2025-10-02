from contextlib import suppress
from io import BytesIO
from json import JSONDecodeError, loads as json_loads
from os import sep
from pathlib import Path
from re import compile as re_compile
from tarfile import TarFile, open as tar_open
from typing import Any, Dict, List, Optional
from zipfile import ZipFile, BadZipFile

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import JSONResponse

from ..auth.guard import guard
from ..utils import get_db

from common_utils import bytes_hash  # type: ignore


router = APIRouter(prefix="/plugins", tags=["plugins"])

_PLUGIN_ID_RX = re_compile(r"^[\w.-]{4,64}$")
_RECOGNIZED_TYPES = {"all", "external", "ui", "pro"}

TMP_UI_ROOT = Path(sep, "var", "tmp", "bunkerweb", "ui")


def _safe_member_path(root: Path, member_name: str) -> Optional[Path]:
    try:
        # Prevent absolute paths and path traversal
        if member_name.startswith("/"):
            return None
        target = (root / member_name).resolve()
        if not str(target).startswith(str(root.resolve())):
            return None
        return target
    except Exception:
        return None


def _extract_plugin_from_tar(tar: TarFile, root_dir: str, dest: Path) -> None:
    for member in tar.getmembers():
        # Filter only entries under the plugin root dir
        name = member.name
        if root_dir:
            if not name.startswith(root_dir + "/") and name != root_dir:
                continue
            rel = name[len(root_dir) + 1 :] if name != root_dir else ""  # noqa: E203
        else:
            rel = name
        if rel == "":
            continue
        target = _safe_member_path(dest, rel)
        if target is None:
            continue
        if member.isdir():
            target.mkdir(parents=True, exist_ok=True)
        elif member.isfile() or member.isreg():
            target.parent.mkdir(parents=True, exist_ok=True)
            with tar.extractfile(member) as src:  # type: ignore[arg-type]
                if src is None:
                    continue
                target.write_bytes(src.read())


def _extract_plugin_from_zip(zipf: ZipFile, root_dir: str, dest: Path) -> None:
    for name in zipf.namelist():
        if root_dir:
            if not name.startswith(root_dir + "/") and name != root_dir:
                continue
            rel = name[len(root_dir) + 1 :] if name != root_dir else ""  # noqa: E203
        else:
            rel = name
        if not rel or rel.endswith("/"):
            # Directory
            d = _safe_member_path(dest, rel)
            if d is not None:
                d.mkdir(parents=True, exist_ok=True)
            continue
        target = _safe_member_path(dest, rel)
        if target is None:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with zipf.open(name) as src:
            target.write_bytes(src.read())


def _find_plugin_roots_in_tar(tar: TarFile) -> List[str]:
    roots: List[str] = []
    names = [m.name for m in tar.getmembers()]
    for n in names:
        if n.endswith("plugin.json"):
            parent = str(Path(n).parent)
            roots.append(parent)
    # Normalize root of "." when plugin.json is at archive root
    return [r if r != "." else "" for r in roots]


def _find_plugin_roots_in_zip(zipf: ZipFile) -> List[str]:
    roots: List[str] = []
    for n in zipf.namelist():
        if n.endswith("plugin.json"):
            parent = str(Path(n).parent)
            roots.append(parent)
    return [r if r != "." else "" for r in roots]


@router.get("", dependencies=[Depends(guard)])
def list_plugins(type: str = "all", with_data: bool = False) -> JSONResponse:  # noqa: A002
    """List plugins of specified type.

    Args:
        type: Plugin type filter ("all", "external", "ui", "pro")
        with_data: Include plugin data/content
    """
    if type not in _RECOGNIZED_TYPES:
        return JSONResponse(status_code=422, content={"status": "error", "message": "Invalid type"})
    plugins = get_db().get_plugins(_type=type, with_data=with_data)
    return JSONResponse(status_code=200, content={"status": "success", "plugins": plugins})


@router.delete("/{plugin_id}", dependencies=[Depends(guard)])
def delete_plugin(plugin_id: str) -> JSONResponse:
    """Delete a UI plugin.

    Args:
        plugin_id: ID of the plugin to delete
    """
    if not _PLUGIN_ID_RX.match(plugin_id):
        return JSONResponse(status_code=422, content={"status": "error", "message": "Invalid plugin id"})
    err = get_db().delete_plugin(plugin_id, "ui", changes=True)
    if err:
        return JSONResponse(status_code=404, content={"status": "error", "message": err})
    return JSONResponse(status_code=200, content={"status": "success"})


@router.post("/upload", dependencies=[Depends(guard)])
async def upload_plugins(files: List[UploadFile] = File(...), method: str = Form("ui")) -> JSONResponse:
    """Upload and install UI plugins from archive files.

    Supports .zip, .tar.gz, .tar.xz formats. Each archive may contain
    multiple plugins if they have separate plugin.json files.

    Args:
        files: Archive files containing plugins
        method: Installation method (currently only "ui" supported)
    """
    if method != "ui":
        return JSONResponse(status_code=422, content={"status": "error", "message": "Only method=ui is supported"})

    db = get_db()
    created: List[str] = []
    errors: List[Dict[str, str]] = []

    # Build set of existing UI plugin ids to avoid collisions
    try:
        existing_ids = {p.get("id") for p in db.get_plugins(_type="ui", with_data=False)}
    except Exception:
        existing_ids = set()

    TMP_UI_ROOT.mkdir(parents=True, exist_ok=True)

    for up in files:
        try:
            filename = up.filename or ""
            lower = filename.lower()
            data = await up.read()
            if not lower.endswith((".zip", ".tar.gz", ".tar.xz")):
                errors.append({"file": filename, "error": "Unsupported archive format"})
                continue

            # Parse archive and find plugin roots
            plugin_roots: List[str] = []
            is_zip = lower.endswith(".zip")
            if is_zip:
                try:
                    with ZipFile(BytesIO(data)) as zipf:
                        plugin_roots = _find_plugin_roots_in_zip(zipf)
                        if not plugin_roots:
                            errors.append({"file": filename, "error": "plugin.json not found"})
                            continue
                        # Process each plugin root found
                        for root in plugin_roots:
                            # Load plugin.json
                            pj_path = f"{root + '/' if root else ''}plugin.json"
                            try:
                                meta = json_loads(zipf.read(pj_path).decode("utf-8"))
                            except KeyError:
                                errors.append({"file": filename, "error": "Invalid plugin.json location"})
                                continue
                            except JSONDecodeError as e:
                                errors.append({"file": filename, "error": f"Invalid plugin.json: {e}"})
                                continue

                            pid = str(meta.get("id", ""))
                            if not _PLUGIN_ID_RX.match(pid):
                                errors.append({"file": filename, "error": f"Invalid plugin id '{pid}'"})
                                continue
                            if pid in existing_ids:
                                errors.append({"file": filename, "error": f"Plugin {pid} already exists"})
                                continue

                            # Extract to /var/tmp/bunkerweb/ui/<id>
                            dest = TMP_UI_ROOT / pid
                            if dest.exists():
                                # Clean previous tmp content
                                for p in sorted(dest.rglob("*"), reverse=True):
                                    with suppress(Exception):
                                        p.unlink() if p.is_file() else p.rmdir()
                                with suppress(Exception):
                                    dest.rmdir()
                            dest.mkdir(parents=True, exist_ok=True)
                            _extract_plugin_from_zip(zipf, root, dest)

                            # Package full plugin dir to tar.gz bytes
                            with BytesIO() as buf:
                                with tar_open(fileobj=buf, mode="w:gz", compresslevel=9) as tf:
                                    tf.add(dest, arcname=dest.name, recursive=True)
                                buf.seek(0)
                                blob = buf.getvalue()
                            checksum = bytes_hash(BytesIO(blob), algorithm="sha256")

                            # Compute flags and call DB update
                            page = dest.joinpath("ui").is_dir()
                            plugin_item = meta | {"type": "ui", "page": page, "method": "ui", "data": blob, "checksum": checksum}
                            err = db.update_external_plugins([plugin_item], _type="ui", delete_missing=False)
                            if err:
                                errors.append({"file": filename, "error": err})
                            else:
                                created.append(pid)
                                existing_ids.add(pid)
                except BadZipFile:
                    errors.append({"file": filename, "error": "Invalid zip archive"})
                continue

            # Tar formats
            try:
                with tar_open(fileobj=BytesIO(data)) as tarf:
                    roots = _find_plugin_roots_in_tar(tarf)
                    if not roots:
                        errors.append({"file": filename, "error": "plugin.json not found"})
                        continue
                    for root in roots:
                        try:
                            pj_member = next(m for m in tarf.getmembers() if m.name == (root + "/plugin.json" if root else "plugin.json"))
                            meta = json_loads(tarf.extractfile(pj_member).read().decode("utf-8"))  # type: ignore[arg-type]
                        except StopIteration:
                            errors.append({"file": filename, "error": "Invalid plugin.json location"})
                            continue
                        except JSONDecodeError as e:
                            errors.append({"file": filename, "error": f"Invalid plugin.json: {e}"})
                            continue

                        pid = str(meta.get("id", ""))
                        if not _PLUGIN_ID_RX.match(pid):
                            errors.append({"file": filename, "error": f"Invalid plugin id '{pid}'"})
                            continue
                        if pid in existing_ids:
                            errors.append({"file": filename, "error": f"Plugin {pid} already exists"})
                            continue

                        dest = TMP_UI_ROOT / pid
                        if dest.exists():
                            for p in sorted(dest.rglob("*"), reverse=True):
                                with suppress(Exception):
                                    p.unlink() if p.is_file() else p.rmdir()
                            with suppress(Exception):
                                dest.rmdir()
                        dest.mkdir(parents=True, exist_ok=True)
                        _extract_plugin_from_tar(tarf, root, dest)

                        with BytesIO() as buf:
                            with tar_open(fileobj=buf, mode="w:gz", compresslevel=9) as tf:
                                tf.add(dest, arcname=dest.name, recursive=True)
                            buf.seek(0)
                            blob = buf.getvalue()
                        checksum = bytes_hash(BytesIO(blob), algorithm="sha256")

                        page = dest.joinpath("ui").is_dir()
                        plugin_item = meta | {"type": "ui", "page": page, "method": "ui", "data": blob, "checksum": checksum}
                        err = db.update_external_plugins([plugin_item], _type="ui", delete_missing=False)
                        if err:
                            errors.append({"file": filename, "error": err})
                        else:
                            created.append(pid)
                            existing_ids.add(pid)
            except Exception as e:
                errors.append({"file": filename, "error": f"Invalid tar archive: {e}"})
                continue
        except Exception as e:
            errors.append({"file": up.filename or "(unknown)", "error": str(e)})

    status = 207 if errors and created else (400 if errors and not created else 201)
    body: Dict[str, Any] = {"status": "success" if created and not errors else ("partial" if created else "error")}
    if created:
        body["created"] = sorted(created)
    if errors:
        body["errors"] = errors
    return JSONResponse(status_code=status, content=body)
