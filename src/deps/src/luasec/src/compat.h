/*--------------------------------------------------------------------------
 * LuaSec 1.3.1
 *
 * Copyright (C) 2006-2023 Bruno Silvestre
 *
 *--------------------------------------------------------------------------*/

#ifndef LSEC_COMPAT_H
#define LSEC_COMPAT_H

#include <openssl/ssl.h>

//------------------------------------------------------------------------------

#if defined(_WIN32)
#define LSEC_API __declspec(dllexport) 
#else
#define LSEC_API extern
#endif

//------------------------------------------------------------------------------

#if (LUA_VERSION_NUM == 501)

#define luaL_testudata(L, ud, tname)  lsec_testudata(L, ud, tname)
#define setfuncs(L, R)    luaL_register(L, NULL, R)
#define lua_rawlen(L, i)  lua_objlen(L, i)

#ifndef luaL_newlib
#define luaL_newlib(L, R) do { lua_newtable(L); luaL_register(L, NULL, R); } while(0)
#endif

#else
#define setfuncs(L, R) luaL_setfuncs(L, R, 0)
#endif

//------------------------------------------------------------------------------

#if (!defined(LIBRESSL_VERSION_NUMBER) && (OPENSSL_VERSION_NUMBER >= 0x1010000fL))
#define LSEC_ENABLE_DANE
#endif

//------------------------------------------------------------------------------

#if !((defined(LIBRESSL_VERSION_NUMBER) && (LIBRESSL_VERSION_NUMBER < 0x2070000fL)) || (OPENSSL_VERSION_NUMBER < 0x1010000fL))
#define LSEC_API_OPENSSL_1_1_0
#endif

//------------------------------------------------------------------------------

#if !defined(LIBRESSL_VERSION_NUMBER) && ((OPENSSL_VERSION_NUMBER & 0xFFFFF000L) == 0x10101000L)
#define LSEC_OPENSSL_1_1_1
#endif

//------------------------------------------------------------------------------

#if !defined(LIBRESSL_VERSION_NUMBER) && !defined(OPENSSL_NO_PSK)
#define LSEC_ENABLE_PSK
#endif

//------------------------------------------------------------------------------

#endif
