import hashlib
import importlib.util
import sys
from pathlib import Path

ALLOWED_ROOTS = (
    Path("/usr/share/bunkerweb/core"),
    Path("/etc/bunkerweb/plugins"),
    Path("/etc/bunkerweb/pro/plugins"),
)


class JobExecutor:
    """Execute a dynamic BunkerWeb job module in-process."""

    def __init__(self, logger):
        self.logger = logger

    def run(self, job_data: dict) -> int:
        name = job_data["name"]
        job_path = Path(job_data["path"]).joinpath("jobs", job_data["file"])
        resolved = job_path.resolve()

        if not self._is_allowed_job_path(resolved):
            self.logger.error(f"Path {resolved} is outside allowed job directories")
            return 2

        if not resolved.is_file():
            self.logger.error(f"Job file not found: {resolved}")
            return 2

        self.logger.info(f"Executing job '{name}' from {resolved}")

        inserted_paths: list[str] = []
        for import_path in (resolved.parent.as_posix(), resolved.parent.parent.as_posix()):
            if import_path not in sys.path:
                sys.path.insert(0, import_path)
                inserted_paths.append(import_path)

        try:
            module_name = f"bw_job_{name}_{hashlib.md5(resolved.as_posix().encode('utf-8')).hexdigest()[:8]}"
            spec = importlib.util.spec_from_file_location(module_name, resolved.as_posix())
            if spec is None or spec.loader is None:
                self.logger.error(f"Cannot create module spec for {resolved}")
                return 2

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return 0
        except Exception as exc:
            self.logger.error(f"Job '{name}' failed: {exc}")
            return 2
        finally:
            for import_path in reversed(inserted_paths):
                if import_path in sys.path:
                    sys.path.remove(import_path)

    def _is_allowed_job_path(self, resolved: Path) -> bool:
        for root in ALLOWED_ROOTS:
            try:
                resolved.relative_to(root.resolve())
                return True
            except ValueError:
                continue
        return False
