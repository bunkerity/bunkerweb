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

// Change dir structure for flask app
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

    // Create template dir if not exist
    if (!fs.existsSync(resolve("./templates"))) {
      fs.mkdirSync(resolve("./templates"));
    }

    fs.readdir(templateDir, (err, subdirs) => {
      subdirs.forEach((subdir) => {
        // Get absolute path of current subdir
        const currPath = resolve(`./${clientBuildDir}/templates/${subdir}`);
        // Rename index.html by subdir name
        fs.renameSync(`${currPath}/index.html`, `${currPath}/${subdir}.html`);
        // Copy file to move it from /template/page to /template
        fs.copyFileSync(
          `${currPath}/${subdir}.html`,
          resolve(`./templates/${subdir}.html`)
        );
      });
    });
    // Delete useless dir
    fs.rmSync(currPath, { recursive: true, force: true });
    fs.rmSync(`./${clientBuildDir}/templates/`, {
      recursive: true,
      force: true,
    });
  } catch (err) {
    isErr = true;
  }
  return isErr;
}

function setFlaskData() {
  // Run all files in /templates and get data
  fs.readdir(resolve("./templates"), (err, files) => {
    // Read content
    files.forEach((file) => {
      let updateData = "";
      const data = fs.readFileSync(resolve(`./templates/${file}`), {
        encoding: "utf8",
        flag: "r",
      });
      try {
        // match every attribute starting with data- and ending with a ' or a "
        const matches = data.match(/data-[^"']+["']/g);
        // remove content between <body> and </body>
        updateData = data.replace(/<body>[\s\S]*<\/body>/g, "");
        // get the <body> index to insert the new content
        const bodyIndex = data.indexOf("<body>");

        let attributs = "";
        matches.forEach((match) => {
          const matchFormat = match.replace('="', "").replace("='", "");
          attributs += `<div class="hidden" ${matchFormat}={{${matchFormat.replaceAll(
            "-",
            "_"
          )}}}></div>\n`;
        });
        // insert the new content
        updateData =
          data.slice(0, bodyIndex) +
          `\n<body>\n` +
          `<div class="hidden" data-csrf-token={{ csrf_token() }}></div>\n` +
          attributs +
          `<div id="app"></div>\n</body>\n</html>`;
      } catch (e) {
        console.log(e);
        updateData = "";
      }
      // Write the new content to the file
      if (updateData)
        fs.writeFileSync(resolve(`./templates/${file}`), updateData, "utf8");
    });
  });
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
  console.log("Error while building client. Impossible to continue.");
// Change client dir structure
const isUpdateDirErr = updateClientDir();
if (isUpdateDirErr)
  console.log(
    "Error while changing client dir structure. Impossible to continue."
  );
const setFlskData = setFlaskData();
