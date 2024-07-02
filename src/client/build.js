const { execSync } = require("child_process");
const { resolve } = require("path");
const fs = require("fs");

const frontDir = "/vite";
const clientBuildDir = "static";
const appStaticDir = "../ui/static";
const appTempDir = "../ui/templates";

async function moveFile(src, dest) {
  fs.renameSync(src, dest, (err) => {
    if (err) {
      return console.error(err);
    }
  });
}

async function createDirIfNotExists(dir) {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir);
  }
}

async function delElRecursive(path) {
  if (!fs.existsSync(path)) return;
  fs.rmSync(path, { recursive: true }, (err) => {
    if (err) {
      console.log(err);
    }
  });
}

async function copyDir(src, dest) {
  fs.cpSync(src, dest, { recursive: true }, (err) => {
    if (err) {
      console.log(err);
    }
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
async function buildVite() {
  // Install packages
  await runCommand(frontDir, "npm install");
  await runCommand(frontDir, "npm run build");
}

// Change dir structure for flask app
async function updateClientDir() {
  const srcDir = resolve(`./${clientBuildDir}/src/pages`);
  const dirToRem = resolve(`./${clientBuildDir}/src`);
  const staticTemp = resolve(`./${clientBuildDir}/templates`);

  try {
    await copyDir(srcDir, staticTemp);
    await delElRecursive(dirToRem);
    await createDirIfNotExists("./templates");
    await changeOutputTemplates();
  } catch (err) {
    console.log(err);
  }
}

async function changeOutputTemplates() {
  const templateDir = resolve(`./${clientBuildDir}/templates`);
  fs.readdir(templateDir, (err, subdirs) => {
    subdirs.forEach((subdir) => {
      // Get absolute path of current subdir
      const currPath = resolve(`./${clientBuildDir}/templates/${subdir}`);
      // Rename index.html by subdir name
      moveFile(`${currPath}/index.html`, `./templates/${subdir}.html`);
    });
  });
}

async function setBuildTempToUI() {
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
          let updateData = data;
          // I want to remove the first "/" for href="/css", href="/js", href="/img", href="/favicon", src="/assets" or src="/js"
          const regexPaths = /href="\/(css|js|img|favicon)|src="\/(assets|js)/g;
          updateData = data.replace(regexPaths, (match) => {
            return match.replace("/", "");
          });

          // For each <script> tag, I want to add nonce="{{ script_nonce }}" inside it
          const regexScript = /<script/g;
          updateData = updateData.replace(regexScript, (match) => {
            return match.replace(
              "<script",
              '<script nonce="{{ script_nonce }}" '
            );
          });

          // remove everything after <body> tag
          const bodyIndex = updateData.indexOf("<body>");
          // Add attributs

          const attributs = `<body>
<div class="hidden" data-csrf-token="{{ csrf_token() }}"></div>\n
<div class="hidden" data-server-global="{{data_server_global if data_server_global else {}}}"></div>\n
<div class="hidden" data-server-flash="{{data_server_flash if data_server_flash else []}}"></div>\n
<div class="hidden" data-server-builder="{{data_server_builder}}"></div>\n
<div id="app"></div>\n</body>\n</html>`;
          // insert the new content
          updateData = updateData.substring(0, bodyIndex) + attributs;
          fs.writeFileSync(
            `${appTempDir}/${file}`,
            updateData,
            "utf8",
            (err) => {}
          );
        }
      );
    });
    // Delete templates to avoid to add it to static
    delElRecursive("./static/templates");
  });
}

async function moveBuildStaticToUI() {
  // move build static subdir to app ui static dir
  const srcDir = resolve(`./static`);
  const destDir = resolve(appStaticDir);
  fs.readdir(srcDir, (err, dirs) => {
    dirs.forEach((dir) => {
      // Avoid try something on dir templates because it's already moved/removed
      if (dir === "templates") return;
      // Delete prev existing dir
      copyDir(`${srcDir}/${dir}`, `${destDir}/${dir}`);
    });
  });
}

async function build() {
  // Build client and setup
  await buildVite();
  await updateClientDir();
  await setBuildTempToUI();
  await moveBuildStaticToUI();
}

build();
