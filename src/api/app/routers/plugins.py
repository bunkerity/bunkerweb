from base64 import b64decode, b64encode
from binascii import Error as BinasciiError
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
from ..schemas import PluginEnabledRequest, UpdateExternalPluginsRequest
from ..utils import get_db

from common_utils import bytes_hash, create_plugin_tar_gz, plugin_icon_content_type, read_local_plugin_icon, read_plugin_icon  # type: ignore

router = APIRouter(prefix="/plugins", tags=["plugins"])

_PLUGIN_ID_RX = re_compile(r"^[\w.-]{4,64}$")
_RECOGNIZED_TYPES = {"all", "external", "ui", "pro"}

TMP_UI_ROOT = Path(sep, "var", "tmp", "bunkerweb", "ui")
# Core plugins ship their icon in-dir; the API container carries the core plugin tree here
# (see src/api/Dockerfile `COPY src/common/core core`).
CORE_PLUGINS_ROOT = Path(sep, "usr", "share", "bunkerweb", "core")


def _icon_response_headers(name: str) -> Dict[str, str]:
    """Response headers for a served plugin icon. The bytes are attacker-controlled for
    external/pro plugins, so on top of ``<img src>``-only intended usage we neutralize direct
    navigation: ``default-src 'none'; sandbox`` stops any script embedded in an SVG from
    executing when the endpoint URL is opened in a browser tab (CSP response headers never
    affect the page that embeds the image), ``nosniff`` blocks MIME confusion, and the filename
    is quoted. There is no path-traversal surface — ``name`` is one of the fixed allowlist."""
    return {
        "Content-Disposition": f'inline; filename="{name}"',
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'; sandbox",
    }


def _safe_member_path(root: Path, member_name: str) -> Optional[Path]:
    try:
        # Prevent absolute paths and path traversal
        if member_name.startswith("/"):
            return None
        target = (root / member_name).resolve()
        if not target.is_relative_to(root.resolve()):
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


@router.put("/external", dependencies=[Depends(guard)])
def update_external_plugins(payload: UpdateExternalPluginsRequest) -> JSONResponse:
    """Bulk update external/pro plugins in the database.

    Args:
        payload: Plugin list, type, and delete_missing flag
    """
    # Plugin archive bytes arrive base64-encoded over JSON (the DB layer expects raw bytes).
    for plugin in payload.plugins:
        data = plugin.get("data") if isinstance(plugin, dict) else None
        if isinstance(data, str):
            try:
                plugin["data"] = b64decode(data)
            except (BinasciiError, ValueError):
                return JSONResponse(status_code=422, content={"status": "error", "message": f"Invalid base64 data for plugin {plugin.get('id', '?')!r}"})
    ret = get_db().update_external_plugins(payload.plugins, _type=payload.plugin_type, delete_missing=payload.delete_missing)
    if ret:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(ret)})
    return JSONResponse(status_code=200, content={"status": "success"})


@router.get("", dependencies=[Depends(guard)])
def list_plugins(type: str = "all", with_data: bool = False, only_enabled: bool = False) -> JSONResponse:  # noqa: A002
    """List plugins of specified type.

    Args:
        type: Plugin type filter ("all", "external", "ui", "pro")
        with_data: Include plugin data/content
        only_enabled: Exclude disabled external/ui/pro plugins (scheduler materialization)
    """
    if type not in _RECOGNIZED_TYPES:
        return JSONResponse(status_code=422, content={"status": "error", "message": "Invalid type"})
    plugins = get_db().get_plugins(_type=type, with_data=with_data, only_enabled=only_enabled)
    if with_data:
        for plugin in plugins:
            if isinstance(plugin.get("data"), bytes):
                plugin["data"] = b64encode(plugin["data"]).decode("ascii")
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


@router.patch("/{plugin_id}", dependencies=[Depends(guard)])
def set_plugin_enabled(plugin_id: str, payload: PluginEnabledRequest) -> JSONResponse:
    """Enable or disable an external/ui/pro plugin.

    Core plugins are structurally required (baked into the image, listed in order.json)
    and cannot be toggled — the DB layer refuses them and the endpoint maps that refusal
    to 422. A missing plugin maps to 404.

    Args:
        plugin_id: ID of the plugin to toggle
        payload: ``{"enabled": bool}``
    """
    if not _PLUGIN_ID_RX.match(plugin_id):
        return JSONResponse(status_code=422, content={"status": "error", "message": "Invalid plugin id"})
    err = get_db().set_plugin_enabled(plugin_id, payload.enabled)
    if err:
        if "not found" in err.lower():
            return JSONResponse(status_code=404, content={"status": "error", "message": err})
        if "core plugin" in err.lower():
            return JSONResponse(status_code=422, content={"status": "error", "message": err})
        return JSONResponse(status_code=500, content={"status": "error", "message": err})
    return JSONResponse(status_code=200, content={"status": "success"})


@router.get("/{plugin_id}/page", dependencies=[Depends(guard)], response_model=None)
def get_plugin_page(plugin_id: str):
    """Get plugin UI page data (tar.gz blob).

    Args:
        plugin_id: ID of the plugin
    """
    if not _PLUGIN_ID_RX.match(plugin_id):
        return JSONResponse(status_code=422, content={"status": "error", "message": "Invalid plugin id"})
    page = get_db().get_plugin_page(plugin_id)
    if not page:
        return JSONResponse(status_code=404, content={"status": "error", "message": "Plugin page not found"})
    from fastapi.responses import Response

    return Response(content=page, media_type="application/gzip")


@router.get("/{plugin_id}/icon", dependencies=[Depends(guard)], response_model=None)
def get_plugin_icon(plugin_id: str):
    """Serve a plugin's shipped icon file (allowlisted root-level icon.svg/png or logo.svg/png).

    Only plugins whose stored icon is an ``@file/<name>`` marker have a servable file; anything
    else (a ``*.svg`` static-asset name, a boxicon class, or absent) returns 404. Two source
    branches, chosen by the plugin ``type`` the DB returns:

    - **core** — the icon ships inside the plugin's on-disk directory (no data blob), so the file
      is read straight from ``CORE_PLUGINS_ROOT/<plugin_id>/<name>`` via ``read_local_plugin_icon``;
    - **external/ui/pro** — the icon lives in the plugin archive, so it is extracted from the
      stored ``data`` blob via ``read_plugin_icon``.

    Every response carries the three neutralizing headers from ``_icon_response_headers`` —
    ``Content-Security-Policy: default-src 'none'; sandbox`` (kills any script in an SVG opened by
    direct navigation), ``Content-Disposition: inline; filename="<name>"`` (quoted), and
    ``X-Content-Type-Options: nosniff`` — with the correct image Content-Type. The fixed 4-name
    allowlist (root only) means there is no path-traversal surface. Files over 512KB return 413.

    Args:
        plugin_id: ID of the plugin
    """
    if not _PLUGIN_ID_RX.match(plugin_id):
        return JSONResponse(status_code=422, content={"status": "error", "message": "Invalid plugin id"})
    row = get_db().get_plugin_icon(plugin_id)
    if row is None:
        return JSONResponse(status_code=404, content={"status": "error", "message": "Plugin not found"})
    plugin_type, icon, data = row
    if not (isinstance(icon, str) and icon.startswith("@file/")):
        return JSONResponse(status_code=404, content={"status": "error", "message": "Plugin has no shipped icon"})
    name = icon[len("@file/") :]  # noqa: E203
    if plugin_type == "core":
        result = read_local_plugin_icon(CORE_PLUGINS_ROOT / plugin_id, name)
    elif isinstance(data, (bytes, bytearray)):
        result = read_plugin_icon(bytes(data), name)
    else:
        result = None
    if result is None:
        return JSONResponse(status_code=404, content={"status": "error", "message": "Plugin icon not found"})
    payload, oversized = result
    if oversized:
        return JSONResponse(status_code=413, content={"status": "error", "message": "Plugin icon exceeds the 512KB limit"})
    from fastapi.responses import Response

    return Response(content=payload, media_type=plugin_icon_content_type(name), headers=_icon_response_headers(name))


@router.post("/upload", dependencies=[Depends(guard)])
def upload_plugins(files: List[UploadFile] = File(...), method: str = Form("ui")) -> JSONResponse:
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
            data = up.file.read()
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
                            buf = create_plugin_tar_gz(dest, arc_root=dest.name)
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

                        buf = create_plugin_tar_gz(dest, arc_root=dest.name)
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
