from utils import save_builder

from pages.instances2 import instances_builder


# Create instance class using keys from the instances list
class Instance:
    def __init__(self, _type, health, _id, hostname, name):
        self._type = _type
        self.health = health
        self._id = _id
        self.hostname = hostname
        self.name = name


instances = [
    {"name": "instance1", "hostname": "hostname1", "type": "static", "health": "up", "id": 1},
    {"name": "instance2", "hostname": "hostname2", "type": "container", "health": "down", "id": 2},
]

types = ["static", "container"]
methods = ["ui", "manual"]
healths = ["up", "down", "loading"]


builder = instances_builder(instances)

save_builder("instances2", builder, update_page=False)
