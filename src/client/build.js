const { execSync } = require("child_process");
const { resolve } = require("path");
const fs = require("fs");

const frontDir = "/vite";
const clientBuildDir = "static";
const setupBuildDir = "setup/output";
const appStaticDir = "../ui/static";
const appTempDir = "../ui/templates";

async function moveFile(src, dest) {
  fs.renameSync(src, dest, (err) => {
    if (err) {
      return console.error(err);
    }
  });
}

async function createDir(dir) {
  fs.promises
    .access(dir, fs.constants.F_OK)
    .then(() => true)
    .catch(() =>
      fs.mkdir(dir, (err) => {
        if (err) {
          return console.error(err);
        }
      })
    );
}

async function deleteDir(dir) {
  fs.rm(
    dir,
    {
      recursive: true,
    },
    (error) => {
      if (error) {
        console.log(error);
      } else {
      }
    }
  );
}

async function copyDir(src, dest) {
  fs.cpSync(src, dest, { recursive: true }, (err) => {
    /* callback */
  });
}

async function copyFile(src, dest) {
  fs.copyFileSync(src, dest, { recursive: true }, (err) => {
    /* callback */
  });
}

// Run subprocess command on specific dir
async function runCommand(dir, command) {
  try {
    execSync(
      command,
      { cwd: resolve(__dirname + dir) },
      function (err, stdout, stderr) {
        console.log(stdout);
        console.log(stderr);
        if (err !== null) {
          console.log(`exec error: ${err}`);
        }
      }
    );
  } catch (err) {
    console.log(err);
  }
}

// Install deps and build vite (work for client and setup)
async function buildVite(dir) {
  // Install packages
  await runCommand(dir, "npm install");
  await runCommand(dir, "npm run build");
}

// Change dir structure for flask app
async function updateClientDir() {
  const srcDir = resolve(`./${clientBuildDir}/src/pages`);
  const dirToRem = resolve(`./${clientBuildDir}/src`);
  const staticTemp = resolve(`./${clientBuildDir}/templates`);

  try {
    const changeDirHtml = await copyDir(srcDir, staticTemp);
    // Remove prev dir
    const removePrevDir = await deleteDir(dirToRem);
    // Create template dir if not exist
    const createTemp = await createDir("./templates");
    // Change output templates
    const changeOutputTemp = await changeOutputTemplates();
    const removeTemp = await deleteDir(staticTemp);
  } catch (err) {
    console.log(err);
  }
}

async function changeOutputTemplates() {
  const templateDir = resolve(`./${clientBuildDir}/templates`);
  console.log(templateDir);
  fs.readdir(templateDir, async (err, subdirs) => {
    subdirs.forEach(async (subdir) => {
      // Get absolute path of current subdir
      const currPath = resolve(`./${clientBuildDir}/templates/${subdir}`);
      // Rename index.html by subdir name
      await moveFile(
        `${currPath}/index.html`,
        resolve(`./templates/${subdir}.html`)
      );
    });
  });
}

async function setFlaskData() {
  // Run all files in /templates and get data
  fs.readdir(resolve("./templates"), (err, files) => {
    // Read content
    files.forEach((file) => {
      const data = fs.readFile(
        resolve(`./templates/${file}`),
        {
          encoding: "utf8",
          flag: "r",
        },
        (err, data) => {
          if (err) {
            console.log(err);
          }
          let updateData = "";
          // remove everything after <body> tag
          const bodyIndex = data.indexOf("<body>");
          // Add attributs

          const attributs = `<body>
                        <div class="hidden" data-csrf-token={{ csrf_token() }}></div>\n
                        <div class="hidden" data-server-global={{data_server_global}}></div>\n
                        <div class="hidden" data-server-flash={{data_server_flash}}></div>\n
                        <div class="hidden" data-server-builder={{data_server_builder}}></div>\n
                        <div id="app"></div>\n</body>\n</html>`;
          // insert the new content
          updateData = updateData = data.substring(0, bodyIndex) + attributs;
          fs.writeFile(
            `${appTempDir}/${file}`,
            updateData,
            "utf8",
            (err) => {}
          );
        }
      );
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

async function moveDir() {
  // move build static subdir to app ui static dir
  const srcDir = resolve(`./static`);
  const destDir = resolve(appStaticDir);
  fs.readdir(srcDir, (err, dirs) => {
    dirs.forEach((dir) => {
      fs.rmSync(`${destDir}/${dir}`, { recursive: true }, (err) => {
        if (err) {
          console.log(err);
        }
      });
      fs.renameSync(
        `${srcDir}/${dir}`,
        `${destDir}/${dir}`,
        { recursive: true },
        (err) => {
          if (err) {
            console.log(err);
          }
        }
      );
    });
  });
}

async function build() {
  // Build client and setup
  const build = await buildVite(frontDir);
  // Change client dir structure
  const update = await updateClientDir();

  const setFlskData = await setFlaskData();
  const moveDirs = await moveDir();
}

build();
