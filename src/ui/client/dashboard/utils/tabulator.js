/**
 *  @name utils/tabulator.js
 *  @description This file contains utils to work with the tabulator library and Vue instance.
 */

/**
 *  @name addColumnsWidth
 *  @description Add min and max width to the column object in case we have the right format.
 *  @param {object} column -  The column object to update in case we have the right format.
 *  @param {string|number} [colMinWidth=0] - The minimum width for the column. Case 0 or invalid, will be ignored.
 *  @param {string|number} [colMaxWidth=0] - The minimum width for the column. Case 0 or invalid, will be ignored.
 *  @returns {void}
 */
function addColumnsWidth(column, colMinWidth = 0, colMaxWidth = 0) {
  try {
    if (+colMinWidth > 0) column.minWidth = colMinWidth;
    if (+colMaxWidth > 0) column.maxWidth = colMaxWidth;
  } catch (e) {
    console.error(e);
  }
}

/**
 *  @name addColumnsSorter
 *  @description This is a wrapper that will execute every sorter function in order to add a new sorter to the tabulator library.
 *  @example { title: "Icon", field: "icon", formatter: "icons" }
 *  @param {object} column -  The column object to update in case we have the right format.
 *  @param {formatName} column - Check if the current column format is the right one.
 *  @returns {void}
 */
function addColumnsSorter(column) {
  if (!("formatter" in column)) return;
  const formatName = column.formatter.toLowerCase();
  _sortIcons(column, formatName);
  _sortText(column, formatName);
}

/**
 *  @name _sortIcons
 *  @description Add sorter for Icons components in the tabulator.
 *  @example { title: "Icon", field: "icon", formatter: "icons" }
 *  @param {object} column -  The column object to update in case we have the right format.
 *  @param {formatName} column - Check if the current column format is the right one.
 *  @returns {void}
 */
function _sortIcons(column, formatName) {
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
 *  @name _sortText
 *  @description Add sorter for Text components in the tabulator. Under the hood, this will use the default tabulator sorter for strings.
 *  @example { title: "Icon", field: "icon", formatter: "icons" }
 *  @param {object} column -  The column object to update in case we have the right format.
 *  @param {formatName} column - Check if the current column format is the right one.
 *  @returns {void}
 */
function _sortText(column, formatName) {
  if (formatName !== "text") return;
  column.sorter = "string";
}

export { addColumnsSorter, addColumnsWidth };
