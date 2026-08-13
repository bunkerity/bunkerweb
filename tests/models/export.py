from typing import Dict, Literal, Optional

from .action import ActionBase, ActionData


class ExportData(ActionData):
    # Mapping of ENV_VAR -> json.path (dot notation)
    exports: Dict[str, str] = {}


class ExportBase(ActionBase, ExportData):
    type: Literal["export"] = "export"


class Export(ExportBase):
    Docker: Optional[ExportData] = None
    Linux: Optional[ExportData] = None
    Autoconf: Optional[ExportData] = None
    Kubernetes: Optional[ExportData] = None
    All_in_one: Optional[ExportData] = None


__all__ = ("Export",)
