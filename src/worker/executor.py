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
        # Why the last run() returned a failure code. run() is the only place that sees these
        # messages -- it returns a bare int -- so without this the caller can persist nothing more
        # than "2", and the reason survives only in the worker's stdout.
        self.last_error = None

    def run(self, job_data: dict) -> int:
        self.last_error = None
        name = job_data["name"]
        resolved = Path(job_data["path"]).joinpath("jobs", job_data["file"]).resolve()

        if not self._is_allowed_job_path(resolved):
            return self._fail(f"Path {resolved} is outside allowed job directories")

        if not resolved.is_file():
            return self._fail(f"Job file not found: {resolved}")

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
                return self._fail(f"Cannot create module spec for {resolved}")

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return 0
        except Exception as exc:
            return self._fail(f"Job '{name}' failed: {exc}")
        finally:
            for import_path in reversed(inserted_paths):
                if import_path in sys.path:
                    sys.path.remove(import_path)

    def _fail(self, message: str) -> int:
        """Log the failure and keep it, so the caller can record it against the job run."""
        self.logger.error(message)
        self.last_error = message
        return 2

    def _is_allowed_job_path(self, resolved: Path) -> bool:
        for root in ALLOWED_ROOTS:
            try:
                resolved.relative_to(root.resolve())
                return True
            except ValueError:
                continue
        return False
