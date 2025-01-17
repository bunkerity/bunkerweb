#include "lua.h"
#include "lauxlib.h"

#define CR '\xD'
#define LF '\xA'
#define CRLF "\xD\xA"

#define candidate(c) (c == CR || c == LF)
static int pushchar(int c, int last, const char *marker, 
    luaL_Buffer *buffer) {
  if (candidate(c)) {
    if (candidate(last)) {
      if (c == last) 
        luaL_addstring(buffer, marker);
      return 0;
    } else {
      luaL_addstring(buffer, marker);
      return c;
    }
  } else {
    luaL_putchar(buffer, c);
    return 0;
  }
}

static int eol(lua_State *L) {
  int context = luaL_checkint(L, 1);
  size_t isize = 0;
  const char *input = luaL_optlstring(L, 2, NULL, &isize);
  const char *last = input + isize;
  const char *marker = luaL_optstring(L, 3, CRLF);
  luaL_Buffer buffer;
  luaL_buffinit(L, &buffer);
  if (!input) {
    lua_pushnil(L);
    lua_pushnumber(L, 0);
    return 2;
  }
  while (input < last)
    context = pushchar(*input++, context, marker, &buffer);
  luaL_pushresult(&buffer);
  lua_pushnumber(L, context);
  return 2;
}

static luaL_reg func[] = {
    { "eol", eol },
    { NULL, NULL }
};

int luaopen_gem(lua_State *L) {
    luaL_openlib(L, "gem", func, 0);
	return 0;
}
