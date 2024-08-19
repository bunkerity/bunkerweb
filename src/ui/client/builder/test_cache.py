from utils import save_builder
from pages.cache import cache_builder

# parents is parent folders
# children can be either files or folders
file_manager = {
    # always need a root, this is the first folder display
    "base": {"parents": [], "children": ["certificates", "configs", "test"], "type": "folder"},
    "certificates": {"parents": ["base"], "children": ["cert-1"], "type": "folder"},
    "cert-1": {"parents": ["base", "certificates"], "children": [], "type": "file", "downloadEndpoint": "/download/cert-1"},
    "configs": {"parents": ["base"], "children": ["config-1"], "type": "folder"},
    "config-1": {"parents": ["base", "configs"], "children": [], "type": "file", "downloadEndpoint": "/download/cert-1"},
    "test": {"parents": ["base"], "children": ["test-1"], "type": "folder"},
    "test-1": {"parents": ["base", "test"], "children": ["test-2"], "type": "folder", "downloadEndpoint": "/download/cert-1"},
    "test-2": {"parents": ["base", "test", "test-1"], "children": [], "type": "file", "downloadEndpoint": "/download/cert-1"},
}


builder = cache_builder(file_manager=file_manager)

save_builder(page_name="cache", output=builder, script_name="cache")
