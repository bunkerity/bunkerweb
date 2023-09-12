// Custom configs types based on NGINX foundation
// Will determine context and order to execute specifig config
export function getTypes() {
  return [
    "http",
    "server-http",
    "default-server-http",
    "modsec-crs",
    "stream",
    "server-stream",
  ];
}

// Base structure for file manager with custom_configs
// For UI we will convert types as base folders where we can create custom conf in it
export function getBaseConfig() {
  const types = getTypes();
  const baseFolders = [];
  const baseConfig = [];
  for (let i = 0; i < types.length; i++) {
    baseFolders.push(generateItem("folder", types[i], false, false, false));
  }
  // We will wrap it on a root element
  baseConfig.push(generateItem("folder", "", false, false, false, baseFolders));
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
  canEdit,
  canDelete,
  children = []
) {
  return {
    type: type,
    path: `root/${path}`,
    canDelete: canDelete,
    canEdit: canEdit,
    canCreateFile: canCreateFile,
    children: children,
  };
}
