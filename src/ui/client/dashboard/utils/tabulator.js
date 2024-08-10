/**
 *  @name utils/tabulator.js
 *  @description This file contains utils to work with the tabulator library and Vue instance.
 */

/**
 *  @name addSorter
 *  @description This is a wrapper that will execute every sorter function in order to add a new sorter to the tabulator library.
 *  @example { title: "Icon", field: "icon", formatter: "icons" }
 *  @param {object} column -  The column object to update in case we have the right format.
 *  @param {formatName} column - Check if the current column format is the right one.
 *  @returns {void}
 */
function addSorter(column, formatName) {
  sortIcons(column, formatName);
  sortText(column, formatName);
}

/**
 *  @name sortIcons
 *  @description Add sorter for Icons components in the tabulator.
 *  @example { title: "Icon", field: "icon", formatter: "icons" }
 *  @param {object} column -  The column object to update in case we have the right format.
 *  @param {formatName} column - Check if the current column format is the right one.
 *  @returns {void}
 */
function sortIcons(column, formatName) {
  if (formatName !== "icons") return;
  column.sorter = (a, b, aRow, bRow, column, dir, params) => {
    const aName = a.iconName;
    const bName = b.iconName;
    let alignEmptyValues = params.alignEmptyValues;
    let emptyAlign = 0;
    let locale;

    if (aName && bName) {
      locale =
        typeof params.locale == "boolean" ? this.langLocale() : params.locale;

      return String(aName)
        .toLowerCase()
        .localeCompare(String(bName).toLowerCase(), locale);
    }

    if (!aName) emptyAlign = !bName ? 0 : -1;
    if (!bName) emptyAlign = 1;

    //fix empty values in position
    if (
      (alignEmptyValues === "top" && dir === "desc") ||
      (alignEmptyValues === "bottom" && dir === "asc")
    ) {
      emptyAlign *= -1;
    }

    return emptyAlign;
  };
}

/**
 *  @name sortText
 *  @description Add sorter for Text components in the tabulator. Under the hood, this will use the default tabulator sorter for strings.
 *  @example { title: "Icon", field: "icon", formatter: "icons" }
 *  @param {object} column -  The column object to update in case we have the right format.
 *  @param {formatName} column - Check if the current column format is the right one.
 *  @returns {void}
 */
function sortText(column, formatName) {
  if (formatName !== "text") return;
  column.sorter = "string";
}

export { addSorter, sortIcons, sortText };
