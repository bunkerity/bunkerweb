from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, model_validator

from ..action import ActionBase, ActionData


class UiData(ActionData):
    ui: Dict[str, Optional[str]] = {}  # ? If ui value is None, then the ui setting is not set
    steps: Dict[str, Any]

    @model_validator(mode="after")
    def check_fields(self):
        classes = []

        base_path = Path(__file__).parent
        for file in base_path.rglob("*.py"):
            if file.name in ("__init__.py"):
                continue
            spec = spec_from_file_location(file.stem, file)
            if spec and spec.loader:
                module = module_from_spec(spec)
                spec.loader.exec_module(module)
                for item in getattr(module, "__all__", []):
                    if isinstance(getattr(module, item), type):
                        classes.append(item)

        for index, (step, class_) in enumerate(self.steps.items(), start=1):
            class_type = class_ if isinstance(class_, type) else class_.__class__
            if not any(class_type.__name__ == class_name for class_name in classes):
                raise ValueError(f"Step {index} class name {class_type.__name__} is not found in the ui folder (step: {step})")

        return self


class UiBase(ActionBase, UiData):
    type: Literal["ui"] = "ui"
    url: str = "http://127.0.0.1"
    database: Literal["mariadb", "mysql", "postgresql", "oracle"] = "mariadb"


class Ui(UiBase):
    Docker: Optional[UiData] = None
    Linux: Optional[UiData] = None
    Autoconf: Optional[UiData] = None
    Kubernetes: Optional[UiData] = None
    All_in_one: Optional[UiData] = None


class StepBase(BaseModel):
    type: str
    sleep: float = 0.3


class CrudBase(StepBase):
    type: Literal["create", "read", "update", "delete"]
    item: str


from .create import *  # noqa: F401, F403
from .custom import *  # noqa: F401, F403
from .delete import *  # noqa: F401, F403
from .read import *  # noqa: F401, F403
from .update import *  # noqa: F401, F403

from .access import Access  # noqa: F401
from .close_tab import Close_Tab  # noqa: F401
from .login import Login  # noqa: F401
from .setup import Setup  # noqa: F401
from .switch_tab import Switch_Tab  # noqa: F401
