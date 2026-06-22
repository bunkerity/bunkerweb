"""plugin_extensions — discovery, trust gate, safe import, and table-prefix enforcement.

These exercise the generic plugin API/DB extension loader (1.7) without a DB or a live
API: temp "plugins" on disk + the shared ``Base.metadata``. Registered fake tables are
removed from the global metadata in teardown so they cannot leak into DB-fixture tests.
"""

import logging

import pytest

import plugin_extensions as pe
from model import Base  # type: ignore


LOGGER = logging.getLogger("bw-unit-test-ext")
LOGGER.addHandler(logging.NullHandler())


def _make_plugin(root, plugin_id, *, extensions=None, models_src=None, methods_src=None, api_src=None):
    """Write a minimal plugin tree under ``root`` and return its directory."""
    pdir = root / plugin_id
    (pdir).mkdir(parents=True, exist_ok=True)
    manifest = {
        "id": plugin_id,
        "name": plugin_id,
        "description": "test",
        "version": "1.0",
        "stream": "no",
        "settings": {},
    }
    if extensions is not None:
        manifest["extensions"] = extensions
    (pdir / "plugin.json").write_text(__import__("json").dumps(manifest), encoding="utf-8")
    if models_src is not None:
        (pdir / "db").mkdir(exist_ok=True)
        (pdir / "db" / "__init__.py").write_text("", encoding="utf-8")
        (pdir / "db" / "models.py").write_text(models_src, encoding="utf-8")
    if methods_src is not None:
        (pdir / "db").mkdir(exist_ok=True)
        (pdir / "db" / "__init__.py").write_text("", encoding="utf-8")
        (pdir / "db" / "methods.py").write_text(methods_src, encoding="utf-8")
    if api_src is not None:
        (pdir / "api").mkdir(exist_ok=True)
        (pdir / "api" / "__init__.py").write_text("", encoding="utf-8")
        (pdir / "api" / "router.py").write_text(api_src, encoding="utf-8")
    return pdir


@pytest.fixture
def cleanup_metadata():
    """Drop any tables added to the global Base.metadata during a test."""
    before = set(Base.metadata.tables)
    yield
    for name in set(Base.metadata.tables) - before:
        table = Base.metadata.tables.get(name)
        if table is not None:
            Base.metadata.remove(table)


class TestTrustGate:
    def test_core_and_pro_trusted(self):
        assert pe.is_trusted("core") is True
        assert pe.is_trusted("pro") is True

    def test_external_off_by_default(self, monkeypatch):
        monkeypatch.delenv("PLUGIN_API_EXTENSIONS_ALLOW_EXTERNAL", raising=False)
        assert pe.is_trusted("external") is False

    def test_external_opt_in(self, monkeypatch):
        monkeypatch.setenv("PLUGIN_API_EXTENSIONS_ALLOW_EXTERNAL", "yes")
        assert pe.is_trusted("external") is True


class TestDiscovery:
    def test_finds_only_declaring_plugins(self, tmp_path):
        _make_plugin(tmp_path, "with_ext", extensions={"api": {"module": "api/router.py"}})
        _make_plugin(tmp_path, "no_ext")  # no extensions key
        found = pe.iter_extension_plugins(paths=[(tmp_path, "core")])
        assert [e.plugin_id for e in found] == ["with_ext"]
        assert found[0].plugin_type == "core"
        assert found[0].table_prefix == "bw_with_ext_"

    def test_external_path_typed_external(self, tmp_path):
        _make_plugin(tmp_path, "ext_one", extensions={"db": {"models": "db/models.py"}})
        found = pe.iter_extension_plugins(paths=[(tmp_path, "external")])
        assert found[0].plugin_type == "external"


class TestSafeImport:
    def test_rejects_traversal(self, tmp_path):
        pdir = _make_plugin(tmp_path, "trav", extensions={"db": {"models": "db/models.py"}}, models_src="x = 1\n")
        with pytest.raises(ValueError):
            pe.import_plugin_submodule("trav", pdir, "../../etc/passwd.py")

    def test_rejects_missing(self, tmp_path):
        pdir = _make_plugin(tmp_path, "missing", extensions={"db": {"models": "db/models.py"}})
        with pytest.raises((FileNotFoundError, ValueError, ImportError)):
            pe.import_plugin_submodule("missing", pdir, "db/models.py")


_GOOD_MODEL = """
from model import Base
from sqlalchemy import Integer, String, Identity
from sqlalchemy.orm import Mapped, mapped_column

class GoodExt(Base):
    __tablename__ = "bw_goodext_thing"
    id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1), primary_key=True)
    name: Mapped[str] = mapped_column(String(32), nullable=False, default="")
"""

_BAD_MODEL = """
from model import Base
from sqlalchemy import Integer, Identity
from sqlalchemy.orm import Mapped, mapped_column

class EvilExt(Base):
    __tablename__ = "bw_settings_shadow"
    id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1), primary_key=True)
"""

# A plugin whose models declare a table in a FOREIGN namespace, with a manifest that
# lies (table_prefix claims that foreign namespace). Runtime must bind to the plugin id.
_FOREIGN_PREFIX_MODEL = """
from model import Base
from sqlalchemy import Integer, Identity
from sqlalchemy.orm import Mapped, mapped_column

class ForeignExt(Base):
    __tablename__ = "bw_victim_data"
    id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1), primary_key=True)
"""

# A db/methods.py that tries to smuggle a foreign table onto Base.metadata as an import
# side effect — the methods path must be namespace-guarded exactly like models.
_EVIL_METHODS = """
from model import Base
from sqlalchemy import Table, Column, Integer

Table("bw_pwned_via_methods", Base.metadata, Column("id", Integer, primary_key=True))

from db_methods.common import DatabaseMixinBase

class EvilMixin(DatabaseMixinBase):
    pass
"""

_CLEAN_METHODS = """
from db_methods.common import DatabaseMixinBase

class CleanMixin(DatabaseMixinBase):
    pass
"""


class TestModelRegistration:
    def test_registers_namespaced_table(self, tmp_path, cleanup_metadata):
        _make_plugin(tmp_path, "goodext", extensions={"db": {"models": "db/models.py"}}, models_src=_GOOD_MODEL)
        registered = pe.register_plugin_models(LOGGER, db=None, paths=[(tmp_path, "core")])
        assert registered.get("goodext") == ["bw_goodext_thing"]
        assert "bw_goodext_thing" in Base.metadata.tables

    def test_rejects_out_of_namespace_table(self, tmp_path, cleanup_metadata):
        _make_plugin(tmp_path, "evilext", extensions={"db": {"models": "db/models.py", "table_prefix": "bw_evilext_"}}, models_src=_BAD_MODEL)
        registered = pe.register_plugin_models(LOGGER, db=None, paths=[(tmp_path, "core")])
        assert "evilext" not in registered
        # the out-of-namespace table must NOT have been left registered
        assert "bw_settings_shadow" not in Base.metadata.tables

    def test_manifest_prefix_ignored_namespace_bound_to_id(self, tmp_path, cleanup_metadata):
        # Hostile manifest LIES: declares a foreign table_prefix to try to claim "bw_victim_".
        # Runtime must ignore the manifest and bind the namespace to the plugin id ("attacker").
        _make_plugin(tmp_path, "attacker", extensions={"db": {"models": "db/models.py", "table_prefix": "bw_victim_"}}, models_src=_FOREIGN_PREFIX_MODEL)
        registered = pe.register_plugin_models(LOGGER, db=None, paths=[(tmp_path, "core")])
        assert "attacker" not in registered
        assert "bw_victim_data" not in Base.metadata.tables

    def test_enforced_prefix_derives_from_id(self):
        assert pe.enforced_table_prefix("my-plug.x") == "bw_my_plug_x_"


class TestMethodsNamespaceGuard:
    def test_methods_cannot_smuggle_table(self, tmp_path, cleanup_metadata):
        _make_plugin(tmp_path, "methodsevil", extensions={"db": {"methods": "db/methods.py"}}, methods_src=_EVIL_METHODS)
        found = pe.discover_db_methods(LOGGER, db=None, paths=[(tmp_path, "core")])
        assert "methodsevil" not in found
        assert "bw_pwned_via_methods" not in Base.metadata.tables

    def test_clean_methods_discovered(self, tmp_path, cleanup_metadata):
        _make_plugin(tmp_path, "cleanmethods", extensions={"db": {"methods": "db/methods.py"}}, methods_src=_CLEAN_METHODS)
        found = pe.discover_db_methods(LOGGER, db=None, paths=[(tmp_path, "core")])
        assert "cleanmethods" in found


class TestNamespaceCollision:
    def test_sanitize_collision_refuses_all(self, tmp_path):
        _make_plugin(tmp_path, "a-b", extensions={"api": {"module": "api/router.py"}})
        _make_plugin(tmp_path, "a_b", extensions={"api": {"module": "api/router.py"}})
        # both ids collapse to bw_a_b_ -> both refused
        assert pe.iter_extension_plugins(paths=[(tmp_path, "core")]) == []

    def test_distinct_namespaces_kept(self, tmp_path):
        _make_plugin(tmp_path, "alpha", extensions={"api": {"module": "api/router.py"}})
        _make_plugin(tmp_path, "beta", extensions={"api": {"module": "api/router.py"}})
        ids = {e.plugin_id for e in pe.iter_extension_plugins(paths=[(tmp_path, "core")])}
        assert ids == {"alpha", "beta"}


class TestPrefix:
    def test_effective_api_prefix_is_locked_to_id(self, tmp_path):
        _make_plugin(tmp_path, "myplug", extensions={"api": {"module": "api/router.py", "prefix": "/evil"}})
        ext = pe.iter_extension_plugins(paths=[(tmp_path, "core")])[0]
        assert pe.effective_api_prefix(ext) == "/myplug"
