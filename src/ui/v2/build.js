const { execSync } = require("child_process");
const { resolve } = require("path");
const fs = require("fs");
const buildDir = "static";
// Build vite with child process
function buildClient() {
  let isErr = false;
  try {
    execSync(
      "npm run build",
      { cwd: resolve(__dirname + "/client") },
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

// Change dir structure of build
function updateClientDir() {
  let isErr = false;
  const srcDir = resolve(__dirname + `/${buildDir}/src/pages`);
  const destDir = resolve(__dirname + `/${buildDir}/templates`);
  const dirToRem = resolve(__dirname + `/${buildDir}/src`);

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
    const templateDir = resolve(__dirname + `/${buildDir}/templates`);

    fs.readdir(templateDir, (err, subdirs) => {
      subdirs.forEach((subdir) => {
        // Get absolute path of current subdir
        const currPath = resolve(
          __dirname + `/${buildDir}/templates/${subdir}`,
        );
        // Rename index.html by subdir name
        fs.renameSync(`${currPath}/index.html`, `${currPath}/${subdir}.html`);
        // Copy file to move it from /template/page to /template
        fs.copyFileSync(
          `${currPath.replace("/static/templates", "")}/${subdir}.html`,
          resolve(__dirname + `/static/${subdir}.html`),
        );
      });
      fs.rmSync(templateDir, { recursive: true, force: true });
    });
  } catch (err) {
    console.error(err);
    isErr = true;
  }
  return isErr;
}

const isBuildErr = buildClient();
if (isBuildErr)
  return console.log("Error while building client. Impossible to continue.");
const isUpdateDirErr = updateClientDir();
if (isUpdateDirErr)
  return console.log(
    "Error while changing dir structure. Impossible to continue.",
  );
