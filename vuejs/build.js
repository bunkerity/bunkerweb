const { execSync } = require("child_process");
const { resolve } = require("path");
const fs = require("fs");

const clientBuildDir = "static";
const setupBuildDir = "setup/output";

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
      },
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
          resolve(`./static/templates/${subdir}.html`),
        );
        fs.rmSync(currPath, { recursive: true, force: true });
      });
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


// Build client and setup
const buildClientErr = buildVite("/client");
if (buildClientErr)
  return console.log("Error while building client. Impossible to continue.");
// Change client dir structure
const isUpdateDirErr = updateClientDir();
if (isUpdateDirErr)
  return console.log(
    "Error while changing client dir structure. Impossible to continue.",
  );
