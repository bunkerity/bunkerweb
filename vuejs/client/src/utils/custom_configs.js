// Custom configs types based on NGINX foundation
// Will determine context and order to execute specific config
export function getTypes() {
  return [
    "http",
    "server_http",
    "default_server_http",
    "modsec",
    "modsec_crs",
    "stream",
    "server_stream",
  ];
}

// Base structure for file manager with custom_configs
// For UI we will convert types as base folders where we can create custom conf in it
export function getBaseConfig() {
  const baseConfig = [];
  // We need a root folder
  baseConfig.push(generateItem("folder", "", false, false, false, false));
  // Base folders are after root
  const types = getTypes();
  for (let i = 0; i < types.length; i++) {
    baseConfig.push(
      generateItem("folder", types[i], true, false, false, false),
    );
  }

  return baseConfig;
}

// Allow to create a valid item for file manager
// type => "folder" || "file"
// path => "path" (<type>/<service_id>/<name> or <type>/<name> or <name>)
// canCreateFile => bool (possible to create a conf file on the folder)
// canEdit => bool (possible to edit item like name or content)
// canDelete => bool (allow to delete item)
// children => [item] (item that need to be display when inside parent item)
export function generateItem(
  type,
  path,
  canCreateFile,
  canCreateFolder,
  canEdit,
  canDelete,
  children = [],
  data = "",
  method = "static",
) {
  const fullPath = `root${path ? `/${path}` : ``}`;
  return {
    type: type,
    path: fullPath,
    pathLevel: fullPath.split("/").length - 1,
    canDelete: canDelete,
    canEdit: canEdit,
    canCreateFile: canCreateFile,
    canCreateFolder: canCreateFolder,
    data: data,
    children: children,
    method: method,
  };
}

export function generateConfTree(configs, services) {
  const baseConf = getBaseConfig();

  // Add services to base folders
  // Exclude some base folders that can only have roots
  const rootOnly = ["server_stream", "server_http", "modsec", "modsec_crs"];
  const servItems = [];
  for (let i = 0; i < services.length; i++) {
    const servName = services[i];

    baseConf.forEach((folder) => {
      // Target only base folder (pathLevel 1)
      if (folder.pathLevel !== 1) return;
      // Case exclude
      const folderName = folder["path"].replace("root/", "");
      if (rootOnly.includes(folderName)) return;

      // Case not exclude
      const path = folder["path"].replace("root/", "");
      const servItem = generateItem(
        "folder",
        `${path}/${servName}`,
        true,
        false,
        false,
        false,
      );
      folder.children.push(servItem);
      servItems.push(servItem);
    });
  }
  const conf = [...baseConf, ...servItems];

  // Fetch config is always file type with data and actions
  // Retrieve file data and format
  for (let i = 0; i < configs.length; i++) {
    conf.push(
      generateItem(
        "file",
        `${configs[i].type}${
          configs[i].service_id ? `/${configs[i].service_id}` : ""
        }/${configs[i].name}`,
        false,
        false,
        configs[i].method === "static" ? false : true,
        configs[i].method === "static" ? false : true,
        [],
        configs[i].data || "",
        configs[i].method || "",
      ),
    );
  }

  // We need to define parent and children to create tree structure
  // First we need to be sure that a parent exist or create it
  // (May not exist because fetch only file and not intermediate folders)
  const parents = [];
  for (let i = 0; i < conf.length; i++) {
    // Check only pathLevel > 2 because 0 = root, 1 = base
    const item = conf[i];
    if (item.pathLevel < 2) continue;
    // Get prev item path (parent)
    const splitPath = item["path"].split("/");
    splitPath.pop();
    const prevPath = splitPath.join("/");
    // Check if parent on base or on created ones
    const isParent =
      conf.filter((item) => item["path"] === prevPath).length === 0 &&
      parents.filter((item) => item["path"] === prevPath).length === 0
        ? false
        : true;
    // Parent is always a folder because fetch return only file conf
    if (!isParent) {
      // Can create folder only on level 1 and 2
      const canCreateFolder =
        item.pathLevel === 1 || item.pathLevel === 2 ? true : false;

      parents.push(
        generateItem(
          "folder",
          prevPath.replace("root/", ""),
          true,
          canCreateFolder,
          true,
          true,
        ),
      );
    }
  }

  // Then we need to set children
  // children must be only one path level more than parent
  for (let i = 0; i < conf.length; i++) {
    const item = conf[i];

    // Get children and set them to parent
    const children = [];
    conf.forEach((child) => {
      const isChild =
        child["path"].startsWith(item["path"]) &&
        child["pathLevel"] === item["pathLevel"] + 1
          ? true
          : false;

      if (isChild) children.push(child);
    });

    item["children"] = children;
  }

  return conf;
}

// Filter custom configs
export function getCustomConfByFilter(items, filters) {
  const itemsToDel = [];
  items.forEach((item, id) => {
    let isMatch = true;
    const path = item.path.replace("root/", "");
    const splitPath = path.split("/");
    const name = splitPath.pop();
    const pathLevel = item.pathLevel;
    // root exclude to avoid break
    if (pathLevel === 0) return;

    // Check every filter
    for (const [key, value] of Object.entries(filters)) {
      // Case no match by a previous filter
      if (!isMatch) continue;

      // Case path keyword
      if (key === "pathKeyword" && value) {
        isMatch = path.includes(value) ? true : false;
      }

      // Case name keyword
      if (key === "nameKeyword" && value) {
        isMatch = name.includes(value) ? true : false;
      }

      // Case services folders
      if (key === "showServices" && value === "no" && pathLevel === 2) {
        isMatch = false;
      }

      // Case check for .conf at end of path
      if (key === "showOnlyCaseConf" && value === "yes") {
        isMatch =
          items.filter(
            (item) => item.pathLevel === 3 && item.path.includes(path),
          ).length === 0
            ? false
            : true;
      }
    }

    // Case no match
    if (!isMatch) itemsToDel.push(items[id]);
  });

  // For items that didn't pass filter
  // We need to remove them itself as item and as other items children
  itemsToDel.forEach((itemDel) => {
    const delPath = itemDel.path;
    const delPathLevel = itemDel.pathLevel;
    // Get prev path level
    const prevPathLevel = itemDel.pathLevel - 1;
    // Avoid remove root
    if (prevPathLevel === -1) return;
    // Get prev path
    const splitPath = itemDel.path.split("/");
    splitPath.pop();
    const prevPath = splitPath.join("/");

    // Remove item as children
    items.forEach((item) => {
      const path = item.path;
      const pathLevel = item.pathLevel;
      if (prevPathLevel !== pathLevel || prevPath !== path) return;
      // Get item that match
      const children = item.children;
      const matchIds = [];
      children.forEach((child, id) => {
        if (child.path !== delPath || child.pathLevel !== delPathLevel) return;
        matchIds.push(id);
      });

      // Remove them using id
      matchIds.forEach((id) => {
        children[id] = "";
      });
      item.children = children.filter((item) => typeof item !== "string");

      // At the end remove item itself
      item = "";
    });
  });

  // Update items removing empty string
  return items
    .filter((item) => typeof item !== "string")
    .sort((a, b) => {
      if (a.type === "file" && b.type === "folder") return -1;
    });
}
