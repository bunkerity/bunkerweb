from typing import Literal, Optional

from .action import ActionBase, ActionData


class PathData(ActionData):
    # Asserted against the URL the response came from, so a redirect chain can be checked
    # by where it lands rather than by its status code.
    path: str


class PathBase(ActionBase, PathData):
    type: Literal["path"] = "path"


class Path(PathBase):
    Docker: Optional[PathData] = None
    Linux: Optional[PathData] = None
    Autoconf: Optional[PathData] = None
    Kubernetes: Optional[PathData] = None
    All_in_one: Optional[PathData] = None


__all__ = ("Path",)
