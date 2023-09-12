// Custom configs types based on NGINX foundation
// Will determine context and order to execute specifig config
export function getTypes() {
  return [
    "http",
    "server_http",
    "default_server_http",
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
    baseConfig.push(generateItem("folder", types[i], true, true, false, false));
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
  data = ""
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
  };
}

export function generateConfTree(configs) {
  const baseConf = getBaseConfig();

  // Fetch config is always file type with data and actions
  // Retrieve file data and format
  for (let i = 0; i < configs.length; i++) {
    baseConf.push(
      generateItem(
        "file",
        `${configs[i].type}${
          configs[i].service_id ? `/${configs[i].service_id}` : ""
        }/${configs[i].name}`,
        false,
        false,
        true,
        true,
        [],
        configs[i].data || ""
      )
    );
  }

  // We need to define parent and children to create tree structure
  // First we need to be sure that a parent exist or create it
  // (May not exist because fetch only file and not intermediate folders)
  const parents = [];
  for (let i = 0; i < baseConf.length; i++) {
    // Check only pathLevel > 2 because 0 = root, 1 = base
    const item = baseConf[i];
    if (item.pathLevel < 2) continue;
    // Get prev item path (parent)
    const splitPath = item["path"].split("/");
    splitPath.pop();
    const prevPath = splitPath.join("/");
    // Check if parent on base or on created ones
    const isParent =
      baseConf.filter((item) => item["path"] === prevPath).length === 0 &&
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
          true
        )
      );
    }
  }

  // Then we need to set children
  // children must be only one path level more than parent
  for (let i = 0; i < baseConf.length; i++) {
    const item = baseConf[i];

    // Get children and set them to parent
    const children = [];
    baseConf.forEach((child) => {
      const isChild =
        child["path"].startsWith(item["path"]) &&
        child["pathLevel"] === item["pathLevel"] + 1
          ? true
          : false;

      if (isChild) children.push(child);
    });

    item["children"] = children;
  }

  return baseConf;
}
