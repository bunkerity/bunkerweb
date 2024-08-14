from utils import save_builder

from pages.instances import instances_builder


# Create instance class using keys from the instances list
class Instance:
    def __init__(self, _type, health, _id, hostname, name):
        self._type = _type
        self.health = health
        self._id = _id
        self.hostname = hostname
        self.name = name


instances = [
    {"name": "instance1", "hostname": "hostname1", "type": "static", "health": "up", "last_seen": "yyyy", "method": "method", "creation_date": "yyyy", "id": 1},
    {
        "name": "instance2",
        "hostname": "hostname2",
        "type": "container",
        "health": "down",
        "last_seen": "yyyy",
        "method": "ui",
        "creation_date": "yyyy",
        "id": 2,
    },
]

types = ["static", "container"]
methods = ["ui", "manual"]
healths = ["up", "down", "loading"]

builder = instances_builder(instances=instances, types=types, methods=methods, healths=healths)

save_builder(page_name="instances", output=builder, script_name="instances")
