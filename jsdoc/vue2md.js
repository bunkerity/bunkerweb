const fs = require("fs");
const path = require("path");

const inputFolder = path.join(__dirname, "components");
const ouputFolder = path.join(__dirname, "output");

function flatten(lists) {
  return lists.reduce((a, b) => a.concat(b), []);
}

function getDirectories(srcpath) {
  return fs
    .readdirSync(srcpath)
    .map((file) => path.join(srcpath, file))
    .filter((path) => fs.statSync(path).isDirectory());
}

function getDirectoriesRecursive(srcpath) {
  return [
    srcpath,
    ...flatten(getDirectories(srcpath).map(getDirectoriesRecursive)),
  ];
}

// Get the script part of a Vue file and create a JS file
function vue2js() {
  const folders = getDirectoriesRecursive(inputFolder);
  console.log(folders);
  // Read every subfolders from the input folder and get all files
  folders.forEach((folder) => {
    const files = fs.readdirSync(path.join(folder), {
      withFileTypes: true,
    });
    files.forEach((file) => {
      if (file.isFile() && file.name.endsWith(".vue")) {
        const src = path.join(folder, file.name);
        const fileName = file.name.replace(".vue", ".js");
        const data = fs.readFileSync(src, "utf8");
        // Get only the content between <script setup> and </script> tag
        const script = data.match(/<script setup>([\s\S]*?)<\/script>/g);
        // I want to remove the <script setup> and </script> tags
        script[0] = script[0]
          .replace("<script setup>", "")
          .replace("</script>", "");
        // Create a file on the output folder with the same name but with .js extension
        const dest = path.join(ouputFolder, fileName);
        fs.writeFileSync(dest, script[0], "utf8");
      }
    });
  });
}

// Run a command to render markdown from JS files
function js2md() {
  // Get all files from the output folder
  const files = fs.readdirSync(ouputFolder, { withFileTypes: true });
  // Create a markdown file for each JS file
  files.forEach((file) => {
    // Run a process `documentation build <filename> -f md > <filename>.md
    const command = `documentation build ${path.join(
      ouputFolder,
      file.name
    )} -f md > ${path.join(ouputFolder, file.name.replace(".js", ".md"))}`;
    console.log(command + "\n");
    // Run the command
    const { execSync } = require("child_process");
    execSync(command, (error, stdout, stderr) => {
      if (error) {
        console.error(`exec error: ${error}`);
        return;
      }
      console.log(`stdout: ${stdout}`);
      console.error(`stderr: ${stderr}`);
    });
  });
  // Remove all JS files when all processes are done
  files.forEach((file) => {
    fs.unlinkSync(path.join(ouputFolder, file.name));
  });
}

// Format each md file to remove specific content
function formatMd() {
  // Get all files from the output folder
  const files = fs.readdirSync(ouputFolder, { withFileTypes: true });
  files.forEach((file, id) => {
    let data = fs.readFileSync(path.join(ouputFolder, file.name), "utf8");
    // Remove ### Table of contents
    data = data.replace("### Table of Contents", "");
    // In case we have "[1]:", remove everything after
    data = data.replace(/\[\d+\]:[\s\S]*?$/g, "");
    // Remove everything after the first ## tag
    const index = data.indexOf("## ");
    data = data.substring(index);
    fs.writeFileSync(path.join(ouputFolder, file.name), data, "utf8");
  });
}

// Check that input folder exists
if (!fs.existsSync(inputFolder)) {
  console.error("Input folder does not exist");
  process.exit(1);
}

// Create the output folder if it doesn't exist
if (!fs.existsSync(ouputFolder)) {
  fs.mkdirSync(ouputFolder);
}

// Remove previous content of the output folder
fs.readdirSync(ouputFolder).forEach((file) => {
  fs.unlinkSync(path.join(ouputFolder, file));
});

vue2js();
js2md();
formatMd();
