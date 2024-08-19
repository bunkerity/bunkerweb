from logging import getLogger
from os import sep
from pathlib import Path

from src.config import Config
from src.instance import InstancesUtils
from src.ui_data import UIData

from ui_database import UIDatabase

DB = UIDatabase(getLogger("UI"), log=False)
DATA = UIData(Path(sep, "var", "tmp", "bunkerweb").joinpath("ui_data.json"))

BW_CONFIG = Config(DB)
BW_INSTANCES_UTILS = InstancesUtils(DB)
