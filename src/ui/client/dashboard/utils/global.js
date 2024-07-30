import { v4 as uuidv4 } from "uuid";

/**
  @name utils/global.js
  @description This file contains global utils that will be used in the application by default.
  This file contains functions related to accessibilities, cookies, and other global utils.
*/

/**
  @name useUUID
  @description This function return a unique identifier using uuidv4 and a random number.
  Adding random number to avoid duplicate uuids when some components are rendered at the same time.
  We can pass a possible existing id, the function will only generate one if the id is empty.
  @param {string} [id=""] - Possible existing id, check if it's empty to generate a new one.
  @returns {string} - The unique identifier.
*/
function useUUID(id = "") {
  if (id) return id;
  // Generate a random number between 0 and 10000 to avoid duplicate uuids when some components are rendered at the same time
  const random = Math.floor(Math.random() * 10000);

  return uuidv4() + random;
}

/**
  @name useEqualStr
  @description Get the type of a widget and format it to lowercase if possible. Else return an empty string.
  @param {any} type - Try to convert the type to a string in lowercase to compare it with wanted value.
  @param {string} compare - The value to compare with, in general the component name.
  @returns {boolean} - True if matching, false if not.
*/
function useEqualStr(type, compare) {
  // Check if valid string or can be converted to string
  try {
    return String(type).toLowerCase() === compare.toLowerCase() ? true : false;
  } catch (e) {
    console.log(e);
    return false;
  }
}

export { useUUID, useEqualStr };
