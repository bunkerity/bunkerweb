"""Service-template packages: the one parser for a template that arrives from outside the database.

A template can arrive in two shapes, and both end as the exact dict ``create_template`` takes
(``{"id", "name", "settings", "steps", "configs"}``, configs as ``{"type", "name", "data"}``
objects):

* **the folder layout** the ``bunkerweb-templates`` repository uses: ``<id>/template.json`` plus
  ``<id>/configs/<type>/<name>.conf``, where ``template.json`` lists its configs as relative
  **paths**. ``template_from_folder`` reads it through a callback, so the same code serves the
  catalogue (a verified GitHub source archive, ``plugin_catalog.template_payload``) and a
  ``.zip`` / ``.tar.gz`` an operator uploads (``template_from_archive``);
* **the package format** ``bunkerweb-template/1``: one self-contained JSON file carrying the
  ``create_template`` input plus ``format``, configs inline (``parse_package``).

It lives in ``common/utils`` rather than in the UI because the API and the scheduler need the
same parser, and neither may import UI models. It validates structure only -- ids, shapes, caps,
config references. Whether every setting exists on this build, whether values are valid, and
whether steps and configs agree is ``create_template``'s job (``_prepare_template_entities``),
which refuses the whole template on the first problem.
"""

from io import BytesIO
from json import JSONDecodeError, loads
from re import compile as re_compile
from tarfile import TarError, open as tar_open
from typing import Any, Callable, Dict, List, Optional, Tuple
from zipfile import BadZipFile, ZipFile, is_zipfile

PACKAGE_FORMAT = "bunkerweb-template/1"

# One template, whatever its shape, is at most this many bytes: the package file itself, and the
# sum of the files read out of an uploaded folder archive.
PACKAGE_MAX = 1024 * 1024

# A template.json read out of an archive. Real ones are a few KB.
MAX_MEMBER_JSON = 256 * 1024

MAX_TEMPLATE_CONFIGS = 32

# An uploaded archive is walked header by header; these bound how much of it is decompressed
# before the walk gives up. The sizes are declared, but a tar can only skip what its headers
# declare, so a lying header buys nothing past the one member it describes.
_ARCHIVE_MAX_MEMBERS = 256
_ARCHIVE_MAX_DECLARED = 8 * PACKAGE_MAX

# The id rule of ``db_methods/templates.py`` (``TEMPLATE_ID_PATTERN``), with ``\Z`` so a trailing
# newline is refused too. Repeated rather than imported: the UI image does not ship the db
# package. The DB re-checks it on write; here it guards the id's use as an archive folder name.
TEMPLATE_ID_RX = re_compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,255}\Z")

# Config references inside a folder-layout template: `<type>/<name>.conf`, where `<type>` is one
# of BunkerWeb's custom-config types. Anchored, one separator, no dots in either half beyond the
# extension -- because this string is joined onto a path to read the blob out of the archive,
# and it is also what `_prepare_template_entities` splits back into a type and a name.
TEMPLATE_CONFIG_RX = re_compile(r"^[a-z][a-z0-9-]{0,31}/[A-Za-z0-9][A-Za-z0-9_-]{0,63}\.conf\Z")

# Inline config objects of the package format. No path is built from them, so they follow the
# API's own rules instead: the type as the DB stores it (`modsec_crs`) or as the repository spells
# it (`modsec-crs`), and the custom-config name rule (`schemas.py`, `^[\w_-]{1,255}\Z`).
PACKAGE_CONFIG_TYPE_RX = re_compile(r"^[a-z][a-z0-9_-]{0,31}\Z")
PACKAGE_CONFIG_NAME_RX = re_compile(r"^[\w-]{1,255}\Z")

_MAX_FOLDER_NAME = 64
_MAX_PACKAGE_NAME = 256  # bw_templates.name is String(256)

Reader = Callable[[str], Optional[bytes]]


def _structure(template_id: str, name: str, data: Dict[str, Any], configs: List[Dict[str, Any]]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """The checks both shapes share, and the only five fields carried across."""
    settings = data.get("settings")
    steps = data.get("steps")
    if not isinstance(settings, dict) or not isinstance(steps, list):
        return None, f"{template_id}: settings must be an object and steps a list"
    return {"id": template_id, "name": name, "settings": settings, "steps": steps, "configs": configs}, None


def template_from_folder(read: Reader, template_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """One template, assembled from its folder, ready for ``create_template``. ``(data, error)``.

    ``read(relative)`` returns the bytes of one file relative to the template's own folder
    (``template.json``, ``configs/modsec-crs/x.conf``), or None when it is absent. The caller
    owns the archive and its caps; this owns what is asked of it.

    Upstream splits a template across ``template.json`` and sibling files, and its ``configs``
    value is a list of **relative paths** (``"modsec-crs/nextcloud_false_positives.conf"``), while
    ``_prepare_template_entities`` requires config **objects** carrying ``type``, ``name`` and the
    config ``data`` itself. So each reference is resolved against ``configs/<reference>`` and
    materialised here. Every reference is pattern-checked before it is used as a path.

    The declared id must equal ``template_id``: the declared id is what ``create_template``
    writes, so a folder whose file names another template is refused rather than installed under
    the other name. Only the five fields ``create_template`` takes are carried across.
    """
    if not isinstance(template_id, str) or not TEMPLATE_ID_RX.match(template_id):
        return None, f"invalid template id {template_id!r}"

    blob = read("template.json")
    if blob is None:
        return None, f"the archive contains no template named {template_id}"
    if len(blob) > MAX_MEMBER_JSON:
        return None, f"{template_id}: template.json is oversized"
    try:
        data = loads(blob.decode("utf-8"))
    except (UnicodeDecodeError, JSONDecodeError, ValueError):
        return None, f"{template_id}: template.json is not valid UTF-8 JSON"
    if not isinstance(data, dict):
        return None, f"{template_id}: template.json is not a JSON object"

    declared = data.get("id")
    if declared != template_id:
        return None, f"the payload declares id {declared!r} but the folder is {template_id!r}"

    references = data.get("configs") or []
    if not isinstance(references, list) or len(references) > MAX_TEMPLATE_CONFIGS:
        return None, f"{template_id}: configs must be a list of at most {MAX_TEMPLATE_CONFIGS} references"

    configs: List[Dict[str, Any]] = []
    for reference in references:
        if not isinstance(reference, str) or not TEMPLATE_CONFIG_RX.match(reference):
            return None, f"{template_id}: invalid config reference {reference!r}"
        blob = read(f"configs/{reference}")
        if blob is None:
            return None, f"{template_id}: config {reference} is missing from the archive"
        try:
            text = blob.decode("utf-8")
        except UnicodeDecodeError:
            return None, f"{template_id}: config {reference} is not valid UTF-8"
        config_type, filename = reference.split("/", 1)
        configs.append({"type": config_type, "name": filename.removesuffix(".conf"), "data": text})

    # A long name is clipped, not refused: that is what the catalogue has always done with it.
    name = data.get("name")
    name = name.strip()[:_MAX_FOLDER_NAME] if isinstance(name, str) else ""
    return _structure(template_id, name or template_id, data, configs)


def parse_package(raw: Any) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """A ``bunkerweb-template/1`` package, as bytes, text or an already-parsed object.

    Returns ``(data, error)`` with ``data`` in the ``create_template`` shape. An optional
    ``locales`` key is accepted and dropped: there is nowhere to store it yet. Every other unknown
    key is dropped too, so nothing rides through to the database that the format does not name.
    """
    if isinstance(raw, (bytes, bytearray, str)):
        if len(raw) > PACKAGE_MAX:
            return None, f"the package exceeds {PACKAGE_MAX} bytes"
        try:
            raw = loads(raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw)
        except (UnicodeDecodeError, JSONDecodeError, ValueError):
            return None, "the package is not valid UTF-8 JSON"
    if not isinstance(raw, dict):
        return None, "the package is not a JSON object"
    if raw.get("format") != PACKAGE_FORMAT:
        return None, f"unsupported package format {raw.get('format')!r}, expected {PACKAGE_FORMAT!r}"

    template_id = raw.get("id")
    if not isinstance(template_id, str) or not TEMPLATE_ID_RX.match(template_id):
        return None, f"invalid template id {template_id!r}"

    name = raw.get("name")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > _MAX_PACKAGE_NAME:
        return None, f"{template_id}: name must be a non-empty string of at most {_MAX_PACKAGE_NAME} characters"

    entries = raw.get("configs") or []
    if not isinstance(entries, list) or len(entries) > MAX_TEMPLATE_CONFIGS:
        return None, f"{template_id}: configs must be a list of at most {MAX_TEMPLATE_CONFIGS} objects"

    configs: List[Dict[str, Any]] = []
    for index, entry in enumerate(entries, start=1):
        if (
            not isinstance(entry, dict)
            or not isinstance(entry.get("type"), str)
            or not PACKAGE_CONFIG_TYPE_RX.match(entry["type"])
            or not isinstance(entry.get("name"), str)
            or not PACKAGE_CONFIG_NAME_RX.match(entry["name"])
            or not isinstance(entry.get("data"), str)
        ):
            return None, f"{template_id}: config {index} must be an object with a valid type, name and string data"
        configs.append({"type": entry["type"], "name": entry["name"], "data": entry["data"]})

    return _structure(template_id, name.strip(), raw, configs)


def _archive_reader(blob: bytes) -> Tuple[Optional[str], Optional[Reader], Optional[str]]:
    """``(root, read, error)`` for an uploaded ``.zip`` / ``.tar.*`` holding one template folder.

    Only regular files are indexed, by their exact member name; a hostile name (absolute, ``..``,
    a backslash) simply never equals the ``<root>/<relative>`` the parser asks for.
    """
    files: Dict[str, Callable[[int], Optional[bytes]]] = {}
    if is_zipfile(BytesIO(blob)):
        try:
            archive = ZipFile(BytesIO(blob))
            infos = archive.infolist()
        except (BadZipFile, ValueError, OSError):
            return None, None, "the archive could not be read"
        if len(infos) > _ARCHIVE_MAX_MEMBERS:
            return None, None, f"the archive holds more than {_ARCHIVE_MAX_MEMBERS} entries"
        for info in infos:
            if not info.is_dir():
                files[info.filename] = lambda cap, info=info: archive.open(info).read(cap + 1)
    else:
        try:
            archive = tar_open(fileobj=BytesIO(blob), mode="r:*")
        except (TarError, EOFError, ValueError):
            return None, None, "the file is neither a JSON package nor a .zip / .tar archive"
        declared = 0
        try:
            while (member := archive.next()) is not None:
                declared += max(member.size, 0)
                if len(files) >= _ARCHIVE_MAX_MEMBERS or declared > _ARCHIVE_MAX_DECLARED:
                    return None, None, "the archive is too large"
                if member.isfile():
                    files[member.name] = lambda cap, member=member: (archive.extractfile(member) or BytesIO()).read(cap + 1)
        except (TarError, EOFError, ValueError):
            return None, None, "the archive could not be read"

    roots = {name.split("/", 1)[0] for name in files}
    if len(roots) != 1:
        return None, None, "the archive must hold exactly one template folder"
    root = roots.pop()

    budget = [PACKAGE_MAX]

    def read(relative: str) -> Optional[bytes]:
        opener = files.get(f"{root}/{relative}")
        if opener is None:
            return None
        try:
            data = opener(budget[0])
        except (BadZipFile, TarError, EOFError, ValueError, OSError, RuntimeError):
            return None
        if len(data) > budget[0]:
            raise OverflowError
        budget[0] -= len(data)
        return data

    return root, read, None


def template_from_archive(blob: Any) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """One template from an uploaded ``.zip`` / ``.tar.gz`` holding ``<id>/template.json``.

    The folder name is the template id, and the folder parser's identity check makes the declared
    id agree with it. Everything read out of the archive counts against ``PACKAGE_MAX``, so a
    template is bounded the same way whether it arrives as a package file or as a folder.
    """
    if not isinstance(blob, (bytes, bytearray)) or not blob:
        return None, "the upload is empty"
    if len(blob) > PACKAGE_MAX:
        return None, f"the upload exceeds {PACKAGE_MAX} bytes"
    root, read, error = _archive_reader(bytes(blob))
    if error or read is None or root is None:
        return None, error or "the archive could not be read"
    try:
        return template_from_folder(read, root)
    except OverflowError:
        return None, f"{root}: the template expands past {PACKAGE_MAX} bytes"
