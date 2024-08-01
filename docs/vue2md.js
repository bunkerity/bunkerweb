const fs = require("fs");
const path = require("path");

// Merge all components md on this file name
const finalFile = "ui-components.md";
// Where we have all SFC components
// Where we want to output md components file
const ouputFolder = path.join(__dirname, "components");

// Format merge file
function formatMd() {
  // Create a md file to merge
  const merge = path.join(finalFile);

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
                .replace(`${title}/`, "")}`,
            );
            isTitleSet = true;
            return;
          }

          if (line.includes(`${title}/`)) {
            data = data.replace(
              line,
              line.replace(tag, "#" + tag).replace(`${title}/`, ""),
            );
          }
          return;
        }
      });
    });
  }

  // Update the child of .vue component title to keep title levels consistency
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
  // Update the data with split
  data = dataSplit.join("\n");

  // Add title and description
  const title = "# UI Components";
  const description =
    "This page contains all the UI components used in the application.";
  data = `${title}\n\n${description}\n\n${data}`;

  fs.writeFileSync(merge, data, "utf8");
}

formatMd();
