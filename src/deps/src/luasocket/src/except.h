#ifndef EXCEPT_H
#define EXCEPT_H
/*=========================================================================*\
* Exception control
* LuaSocket toolkit (but completely independent from other modules)
*
* This provides support for simple exceptions in Lua. During the
* development of the HTTP/FTP/SMTP support, it became aparent that
* error checking was taking a substantial amount of the coding. These
* function greatly simplify the task of checking errors.
*
* The main idea is that functions should return nil as their first return
* values when they find an error, and return an error message (or value)
* following nil. In case of success, as long as the first value is not nil,
* the other values don't matter.
*
* The idea is to nest function calls with the "try" function. This function
* checks the first value, and, if it's falsy, wraps the second value in a
* table with metatable and calls "error" on it. Otherwise, it returns all
* values it received. Basically, it works like the Lua "assert" function,
* but it creates errors targeted specifically at "protect".
*
* The "newtry" function is a factory for "try" functions that call a
* finalizer in protected mode before calling "error".
*
* The "protect" function returns a new function that behaves exactly like
* the function it receives, but the new function catches exceptions thrown
* by "try" functions and returns nil followed by the error message instead.
*
* With these three functions, it's easy to write functions that throw
* exceptions on error, but that don't interrupt the user script.
\*=========================================================================*/

#include "luasocket.h"

#ifndef _WIN32
#pragma GCC visibility push(hidden)
#endif

int except_open(lua_State *L);

#ifndef _WIN32
#pragma GCC visibility pop
#endif

#endif
