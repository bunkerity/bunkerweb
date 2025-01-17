from logging import getLogger
from os import sep
from pathlib import Path

from app.models.config import Config
from app.models.instance import InstancesUtils
from app.models.ui_data import UIData
from app.models.ui_database import UIDatabase

DB = UIDatabase(getLogger("UI"), log=False)
DATA = UIData(Path(sep, "var", "tmp", "bunkerweb").joinpath("ui_data.json"))

BW_CONFIG = Config(DB, data=DATA)
BW_INSTANCES_UTILS = InstancesUtils(DB)
