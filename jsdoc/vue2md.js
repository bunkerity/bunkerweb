const fs = require("fs");
const path = require("path");

const finalFile = "COMPONENTS.md";
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

    // Run the command
    const { execSync } = require("child_process");
    execSync(command, (error, stdout, stderr) => {
      if (error) {
        // console.error(`exec error: ${error}`);
        return;
      }
      // console.log(`stdout: ${stdout}`);
      // console.error(`stderr: ${stderr}`);
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

  // Create order using the tag title path of each file
  const order = [];
  files.forEach((file, id) => {
    // Get the title from first line
    const data = fs.readFileSync(path.join(ouputFolder, file.name), "utf8");
    const filePath = data.split("\n")[0].replace("## ", "");
    order.push({ path: filePath, file: file });
  });

  // Sort order by path
  order.sort((a, b) => {
    return a.path.localeCompare(b.path);
  });

  // Create a md file to merge
  const merge = path.join(ouputFolder, finalFile);
  fs.writeFileSync(merge, "", "utf8");
  // Append each file in the order
  order.forEach((item) => {
    let data = fs.readFileSync(path.join(ouputFolder, item.file.name), "utf8");
    fs.appendFileSync(merge, data, "utf8");
  });

  // Get data from merge
  let data = fs.readFileSync(merge, "utf8");
  let isLevel = true;
  let currAttemps = 0;
  const maxAttemps = 6;
  while (isLevel && currAttemps < maxAttemps) {
    currAttemps++;
    const titles = [];
    let tag = "#";
    for (let i = 0; i < currAttemps; i++) {
      tag += "#";
    }
    tag += " ";

    // Each time, get the first level title and add it to the titles array
    data.split("\n").forEach((line) => {
      if (line.startsWith(tag) && line.includes("/")) {
        const firstLevel = line.split("/")[0];
        if (!titles.includes(firstLevel.replace(tag, "").trim()))
          titles.push(firstLevel.replace(tag, ""));
      }
    });
    // Create a top title at the first occurrence
    // And remove from component the first level string
    titles.forEach((title) => {
      let isTitleSet = false;
      data.split("\n").forEach((line) => {
        // For title
        if (line.startsWith(tag) && line.includes("/")) {
          // Add a top title before the current line
          if (!isTitleSet && line.includes(`${title}/`)) {
            data = data.replace(
              line,
              `${tag} ${title}\n\n${line
                .replace(tag, "#" + tag)
                .replace(`${title}/`, "")}`
            );
            isTitleSet = true;
            return;
          }

          if (line.includes(`${title}/`)) {
            data = data.replace(
              line,
              line.replace(tag, "#" + tag).replace(`${title}/`, "")
            );
          }
          return;
        }
      });
    });
  }

  // Update the child of .vue component title
  let componentTag = "";
  let dataSplit = data.split("\n");
  data.split("\n").forEach((line, id) => {
    if (line.startsWith("#") && line.includes(".vue")) {
      componentTag = line.split(" ")[0];
      return;
    }

    if (
      (line.startsWith("#") && line.includes("Parameters")) ||
      (line.startsWith("#") && line.includes("Examples"))
    ) {
      const elTag = line.split(" ")[0];
      // get line per id
      const updateLine = line.replace(elTag, `${componentTag}#`);
      dataSplit[id] = updateLine;
    }
  });
  // Update the data adn merge
  data = dataSplit.join("\n");

  // Remove 3 first lines
  data = data.split("\n").slice(3).join("\n");

  fs.writeFileSync(merge, data, "utf8");
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
