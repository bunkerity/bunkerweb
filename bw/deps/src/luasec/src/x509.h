/*--------------------------------------------------------------------------
 * LuaSec 1.0.2
 *
 * Copyright (C) 2014-2021 Kim Alvefur, Paul Aurich, Tobias Markmann
 *                         Matthew Wild, Bruno Silvestre.
 *
 *--------------------------------------------------------------------------*/

#ifndef LSEC_X509_H
#define LSEC_X509_H

#include <openssl/x509v3.h>
#include <lua.h>

#include "compat.h"

/* We do not support UniversalString nor BMPString as ASN.1 String types */
enum { LSEC_AI5_STRING, LSEC_UTF8_STRING };

typedef struct t_x509_ {
  X509 *cert;
  int  encode;
} t_x509;
typedef t_x509* p_x509;

void  lsec_pushx509(lua_State* L, X509* cert);
X509* lsec_checkx509(lua_State* L, int idx);

LSEC_API int luaopen_ssl_x509(lua_State *L);

#endif
