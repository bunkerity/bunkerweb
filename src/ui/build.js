const { execSync } = require("child_process");
const { resolve } = require("path");
const fs = require("fs");

const clientBuildDir = "static";
const setupBuildDir = "setup/output";
const corePluginsPath = resolve("../common/core");

// Run subprocess command on specific dir
function runCommand(dir, command) {
  let isErr = false;
  try {
    execSync(
      command,
      { cwd: resolve(__dirname + dir) },
      function (err, stdout, stderr) {
        console.log(stdout);
        console.log(stderr);
        if (err !== null) {
          isErr = true;
          console.log(`exec error: ${err}`);
        }
      }
    );
  } catch (err) {
    isErr = true;
  }

  return isErr;
}

// Install deps and build vite (work for client and setup)
function buildVite(dir) {
  let isErr = false;
  // Install packages
  isErr = runCommand(dir, "npm install");
  if (isErr) return isErr;
  // Build vite
  isErr = runCommand(dir, "npm run build");
  return isErr;
}

// CLIENT : Change dir structure
function updateClientDir() {
  let isErr = false;
  const srcDir = resolve(`./${clientBuildDir}/src/pages`);
  const destDir = resolve(`./${clientBuildDir}/templates`);
  const dirToRem = resolve(`./${clientBuildDir}/src`);

  try {
    // Change dir position for html
    fs.cpSync(srcDir, destDir, {
      force: true,
      recursive: true,
    });
    // Remove prev dir
    fs.rmSync(dirToRem, { recursive: true, force: true });
    // Change templates/page/index.html by templates/{page_name}.html
    // And move from static to templates
    const templateDir = resolve(`./${clientBuildDir}/templates`);

    fs.readdir(templateDir, (err, subdirs) => {
      subdirs.forEach((subdir) => {
        // Get absolute path of current subdir
        const currPath = resolve(`./${clientBuildDir}/templates/${subdir}`);
        // Rename index.html by subdir name
        fs.renameSync(`${currPath}/index.html`, `${currPath}/${subdir}.html`);
        // Copy file to move it from /template/page to /template
        fs.copyFileSync(
          `${currPath}/${subdir}.html`,
          resolve(`./static/${subdir}.html`)
        );
      });
      fs.rmSync(templateDir, { recursive: true, force: true });
    });
  } catch (err) {
    isErr = true;
  }
  return isErr;
}

// SETUP : rename and move to /static as html file
function setSetup() {
  let isErr = false;
  const srcDir = resolve(`./${setupBuildDir}`);
  const destDir = resolve(`./${clientBuildDir}`);

  try {
    // Copy file from src to dest
    fs.copyFileSync(`${srcDir}/index.html`, `${destDir}/setup.html`);
  } catch (err) {
    isErr = true;
  }
  return isErr;
}

// CORE PLUGINS TEMPLATES : rename and move to /static html file
function setCorePlugins() {
  let isErr = false;
  const destDir = resolve(`./${clientBuildDir}`);

  // Loop inside every core plugins
  fs.readdirSync(corePluginsPath).forEach((coreDir) => {
    const coreFolderName = coreDir; // need to be same as core plugin id
    const corePath = resolve(corePluginsPath, `./${coreFolderName}`);
    const coreTemplate = resolve(corePath, "./ui/index.html");

    if (!fs.existsSync(coreTemplate)) return;

    try {
      // Copy file from src to dest
      fs.copyFileSync(coreTemplate, `${destDir}/${coreFolderName}.html`);
    } catch (err) {
      isErr = true;
    }
  });

  return isErr;
}

// Build client and setup
const buildClientErr = buildVite("/client");
if (buildClientErr)
  return console.log("Error while building client. Impossible to continue.");
const buildSetupErr = buildVite("/setup");
if (buildSetupErr)
  return console.log("Error while building client. Impossible to continue.");
// Change client dir structure
const isUpdateDirErr = updateClientDir();
if (isUpdateDirErr)
  return console.log(
    "Error while changing client dir structure. Impossible to continue."
  );
const isUpdateSetupErr = setSetup();
if (isUpdateSetupErr)
  return console.log(
    "Error while changing setup dir structure. Impossible to continue."
  );
const setCore = setCorePlugins();
if (setCore) {
  return console.log("Error while getting core plugins templates.");
}
