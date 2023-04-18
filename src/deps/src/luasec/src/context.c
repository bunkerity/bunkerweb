/*--------------------------------------------------------------------------
 * LuaSec 1.3.1
 *
 * Copyright (C) 2014-2023 Kim Alvefur, Paul Aurich, Tobias Markmann, Matthew Wild
 * Copyright (C) 2006-2023 Bruno Silvestre
 *
 *--------------------------------------------------------------------------*/

#include <string.h>

#if defined(WIN32)
#include <windows.h>
#endif

#include <openssl/ssl.h>
#include <openssl/err.h>
#include <openssl/x509.h>
#include <openssl/x509v3.h>
#include <openssl/x509_vfy.h>
#include <openssl/dh.h>

#include <lua.h>
#include <lauxlib.h>

#include "compat.h"
#include "context.h"
#include "options.h"

#ifndef OPENSSL_NO_EC
#include <openssl/ec.h>
#include "ec.h"
#endif

/*--------------------------- Auxiliary Functions ----------------------------*/

/**
 * Return the context.
 */
static p_context checkctx(lua_State *L, int idx)
{
  return (p_context)luaL_checkudata(L, idx, "SSL:Context");
}

static p_context testctx(lua_State *L, int idx)
{
  return (p_context)luaL_testudata(L, idx, "SSL:Context");
}

/**
 * Prepare the SSL options flag.
 */
static int set_option_flag(const char *opt, unsigned long *flag)
{
  lsec_ssl_option_t *p;
  for (p = lsec_get_ssl_options(); p->name; p++) {
    if (!strcmp(opt, p->name)) {
      *flag |= p->code;
      return 1;
    }
  }
  return 0;
}

#ifndef LSEC_API_OPENSSL_1_1_0
/**
 * Find the protocol.
 */
static const SSL_METHOD* str2method(const char *method, int *vmin, int *vmax)
{
  (void)vmin;
  (void)vmax;
  if (!strcmp(method, "any"))     return SSLv23_method();
  if (!strcmp(method, "sslv23"))  return SSLv23_method();  // deprecated
  if (!strcmp(method, "tlsv1"))   return TLSv1_method();
  if (!strcmp(method, "tlsv1_1")) return TLSv1_1_method();
  if (!strcmp(method, "tlsv1_2")) return TLSv1_2_method();
  return NULL;
}

#else

/**
 * Find the protocol.
 */
static const SSL_METHOD* str2method(const char *method, int *vmin, int *vmax)
{
  if (!strcmp(method, "any") || !strcmp(method, "sslv23")) { // 'sslv23' is deprecated
    *vmin = 0;
    *vmax = 0;
    return TLS_method();
  }
  else if (!strcmp(method, "tlsv1")) {
    *vmin = TLS1_VERSION;
    *vmax = TLS1_VERSION;
    return TLS_method();
  }
  else if (!strcmp(method, "tlsv1_1")) {
    *vmin = TLS1_1_VERSION;
    *vmax = TLS1_1_VERSION;
    return TLS_method();
  }
  else if (!strcmp(method, "tlsv1_2")) {
    *vmin = TLS1_2_VERSION;
    *vmax = TLS1_2_VERSION;
    return TLS_method();
  }
#if defined(TLS1_3_VERSION)
  else if (!strcmp(method, "tlsv1_3")) {
    *vmin = TLS1_3_VERSION;
    *vmax = TLS1_3_VERSION;
    return TLS_method();
  }
#endif
  return NULL;
}
#endif

/**
 * Prepare the SSL handshake verify flag.
 */
static int set_verify_flag(const char *str, int *flag)
{
  if (!strcmp(str, "none")) { 
    *flag |= SSL_VERIFY_NONE;
    return 1;
  }
  if (!strcmp(str, "peer")) {
    *flag |= SSL_VERIFY_PEER;
    return 1;
  }
  if (!strcmp(str, "client_once")) {
    *flag |= SSL_VERIFY_CLIENT_ONCE;
    return 1;
  }
  if (!strcmp(str, "fail_if_no_peer_cert")) { 
    *flag |= SSL_VERIFY_FAIL_IF_NO_PEER_CERT;
    return 1;
  }
  return 0;
}

/**
 * Password callback for reading the private key.
 */
static int passwd_cb(char *buf, int size, int flag, void *udata)
{
  lua_State *L = (lua_State*)udata;
  switch (lua_type(L, 3)) {
  case LUA_TFUNCTION:
    lua_pushvalue(L, 3);
    lua_call(L, 0, 1);
    if (lua_type(L, -1) != LUA_TSTRING) {
       lua_pop(L, 1);  /* Remove the result from the stack */
       return 0;
    }
    /* fallback */
  case LUA_TSTRING:
    strncpy(buf, lua_tostring(L, -1), size);
    lua_pop(L, 1);  /* Remove the result from the stack */
    buf[size-1] = '\0';
    return (int)strlen(buf);
  }
  return 0;
}

/**
 * Add an error related to a depth certificate of the chain.
 */
static void add_cert_error(lua_State *L, SSL *ssl, int err, int depth)
{
  luaL_getmetatable(L, "SSL:Verify:Registry");
  lua_pushlightuserdata(L, (void*)ssl);
  lua_gettable(L, -2);
  if (lua_isnil(L, -1)) {
    lua_pop(L, 1);
    /* Create an error table for this connection */
    lua_newtable(L);
    lua_pushlightuserdata(L, (void*)ssl);
    lua_pushvalue(L, -2);  /* keep the table on stack */
    lua_settable(L, -4);
  }
  lua_rawgeti(L, -1, depth+1);
  /* If the table doesn't exist, create it */
  if (lua_isnil(L, -1)) {
    lua_pop(L, 1);               /* remove 'nil' from stack */
    lua_newtable(L);
    lua_pushvalue(L, -1);        /* keep the table on stack */
    lua_rawseti(L, -3, depth+1);
  }
  lua_pushstring(L, X509_verify_cert_error_string(err));
  lua_rawseti(L, -2, lua_rawlen(L, -2) + 1);
  /* Clear the stack */
  lua_pop(L, 3);
}

/**
 * Call Lua user function to get the DH key.
 */
static DH *dhparam_cb(SSL *ssl, int is_export, int keylength)
{
  BIO *bio;
  lua_State *L;
  SSL_CTX *ctx = SSL_get_SSL_CTX(ssl);
  p_context pctx = (p_context)SSL_CTX_get_app_data(ctx);

  L = pctx->L;

  /* Get the callback */
  luaL_getmetatable(L, "SSL:DH:Registry");
  lua_pushlightuserdata(L, (void*)ctx);
  lua_gettable(L, -2);

  /* Invoke the callback */
  lua_pushboolean(L, is_export);
  lua_pushnumber(L, keylength);
  lua_call(L, 2, 1);

  /* Load parameters from returned value */
  if (lua_type(L, -1) != LUA_TSTRING) {
    lua_pop(L, 2);  /* Remove values from stack */
    return NULL;
  }

  bio = BIO_new_mem_buf((void*)lua_tostring(L, -1), lua_rawlen(L, -1));
  if (bio) {
    pctx->dh_param = PEM_read_bio_DHparams(bio, NULL, NULL, NULL);
    BIO_free(bio);
  }

  lua_pop(L, 2);    /* Remove values from stack */
  return pctx->dh_param;
}

/**
 * Set the "ignore purpose" before to start verifing the certificate chain.
 */
static int cert_verify_cb(X509_STORE_CTX *x509_ctx, void *ptr)
{
  int verify;
  lua_State *L;
  SSL_CTX *ctx = (SSL_CTX*)ptr;
  p_context pctx = (p_context)SSL_CTX_get_app_data(ctx);

  L = pctx->L;

  /* Get verify flags */
  luaL_getmetatable(L, "SSL:Verify:Registry");
  lua_pushlightuserdata(L, (void*)ctx);
  lua_gettable(L, -2);
  verify = (int)lua_tonumber(L, -1);

  lua_pop(L, 2); /* Remove values from stack */

  if (verify & LSEC_VERIFY_IGNORE_PURPOSE) {
    /* Set parameters to ignore the server purpose */
    X509_VERIFY_PARAM *param = X509_STORE_CTX_get0_param(x509_ctx);
    if (param) {
      X509_VERIFY_PARAM_set_purpose(param, X509_PURPOSE_SSL_SERVER);
      X509_VERIFY_PARAM_set_trust(param, X509_TRUST_SSL_SERVER);
    }
  }
  /* Call OpenSSL standard verification function */
  return X509_verify_cert(x509_ctx);
}

/**
 * This callback implements the "continue on error" flag and log the errors.
 */
static int verify_cb(int preverify_ok, X509_STORE_CTX *x509_ctx)
{
  int err;
  int verify;
  SSL *ssl;
  SSL_CTX *ctx;
  p_context pctx;
  lua_State *L;

  /* Short-circuit optimization */
  if (preverify_ok)
    return 1;

  ssl = X509_STORE_CTX_get_ex_data(x509_ctx,
    SSL_get_ex_data_X509_STORE_CTX_idx());
  ctx = SSL_get_SSL_CTX(ssl);
  pctx = (p_context)SSL_CTX_get_app_data(ctx);
  L = pctx->L;

  /* Get verify flags */
  luaL_getmetatable(L, "SSL:Verify:Registry");
  lua_pushlightuserdata(L, (void*)ctx);
  lua_gettable(L, -2);
  verify = (int)lua_tonumber(L, -1);

  lua_pop(L, 2); /* Remove values from stack */

  err = X509_STORE_CTX_get_error(x509_ctx);
  if (err != X509_V_OK)
    add_cert_error(L, ssl, err, X509_STORE_CTX_get_error_depth(x509_ctx));

  return (verify & LSEC_VERIFY_CONTINUE ? 1 : preverify_ok);
}

/*------------------------------ Lua Functions -------------------------------*/

/**
 * Create a SSL context.
 */
static int create(lua_State *L)
{
  p_context ctx;
  const char *str_method;
  const SSL_METHOD *method;
  int vmin, vmax;

  str_method = luaL_checkstring(L, 1);
  method = str2method(str_method, &vmin, &vmax);
  if (!method) {
    lua_pushnil(L);
    lua_pushfstring(L, "invalid protocol (%s)", str_method);
    return 2;
  }
  ctx = (p_context) lua_newuserdata(L, sizeof(t_context));
  if (!ctx) {
    lua_pushnil(L);
    lua_pushstring(L, "error creating context");
    return 2;
  }
  memset(ctx, 0, sizeof(t_context));
  ctx->context = SSL_CTX_new(method);
  if (!ctx->context) {
    lua_pushnil(L);
    lua_pushfstring(L, "error creating context (%s)",
      ERR_reason_error_string(ERR_get_error()));
    return 2;
  }
#ifdef LSEC_API_OPENSSL_1_1_0
  SSL_CTX_set_min_proto_version(ctx->context, vmin);
  SSL_CTX_set_max_proto_version(ctx->context, vmax);
#endif
  ctx->mode = LSEC_MODE_INVALID;
  ctx->L = L;
  luaL_getmetatable(L, "SSL:Context");
  lua_setmetatable(L, -2);

  /* No session support */
  SSL_CTX_set_session_cache_mode(ctx->context, SSL_SESS_CACHE_OFF);
  /* Link LuaSec context with the OpenSSL context */
  SSL_CTX_set_app_data(ctx->context, ctx);

  return 1;
}

/**
 * Load the trusting certificates.
 */
static int load_locations(lua_State *L)
{
  SSL_CTX *ctx = lsec_checkcontext(L, 1);
  const char *cafile = luaL_optstring(L, 2, NULL);
  const char *capath = luaL_optstring(L, 3, NULL);
  if (SSL_CTX_load_verify_locations(ctx, cafile, capath) != 1) {
    lua_pushboolean(L, 0);
    lua_pushfstring(L, "error loading CA locations (%s)",
      ERR_reason_error_string(ERR_get_error()));
    return 2;
  }
  lua_pushboolean(L, 1);
  return 1;
}

/**
 * Load the certificate file.
 */
static int load_cert(lua_State *L)
{
  SSL_CTX *ctx = lsec_checkcontext(L, 1);
  const char *filename = luaL_checkstring(L, 2);
  if (SSL_CTX_use_certificate_chain_file(ctx, filename) != 1) {
    lua_pushboolean(L, 0);
    lua_pushfstring(L, "error loading certificate (%s)",
      ERR_reason_error_string(ERR_get_error()));
    return 2;
  }
  lua_pushboolean(L, 1);
  return 1;
}

/**
 * Load the key file -- only in PEM format.
 */
static int load_key(lua_State *L)
{
  int ret = 1;
  SSL_CTX *ctx = lsec_checkcontext(L, 1);
  const char *filename = luaL_checkstring(L, 2);
  switch (lua_type(L, 3)) {
  case LUA_TSTRING:
  case LUA_TFUNCTION:
    SSL_CTX_set_default_passwd_cb(ctx, passwd_cb);
    SSL_CTX_set_default_passwd_cb_userdata(ctx, L);
    /* fallback */
  case LUA_TNIL: 
    if (SSL_CTX_use_PrivateKey_file(ctx, filename, SSL_FILETYPE_PEM) == 1)
      lua_pushboolean(L, 1);
    else {
      ret = 2;
      lua_pushboolean(L, 0);
      lua_pushfstring(L, "error loading private key (%s)",
        ERR_reason_error_string(ERR_get_error()));
    }
    SSL_CTX_set_default_passwd_cb(ctx, NULL);
    SSL_CTX_set_default_passwd_cb_userdata(ctx, NULL);
    break;
  default:
    lua_pushstring(L, "invalid callback value");
    lua_error(L);
  }
  return ret;
}

/**
 * Check that the certificate public key matches the private key
 */

static int check_key(lua_State *L)
{
  SSL_CTX *ctx = lsec_checkcontext(L, 1);
  lua_pushboolean(L, SSL_CTX_check_private_key(ctx));
  return 1;
}

/**
 * Set the cipher list.
 */
static int set_cipher(lua_State *L)
{
  SSL_CTX *ctx = lsec_checkcontext(L, 1);
  const char *list = luaL_checkstring(L, 2);
  if (SSL_CTX_set_cipher_list(ctx, list) != 1) {
    lua_pushboolean(L, 0);
    lua_pushfstring(L, "error setting cipher list (%s)", ERR_reason_error_string(ERR_get_error()));
    return 2;
  }
  lua_pushboolean(L, 1);
  return 1;
}

/**
 * Set the cipher suites.
 */
static int set_ciphersuites(lua_State *L)
{
#if defined(TLS1_3_VERSION)
  SSL_CTX *ctx = lsec_checkcontext(L, 1);
  const char *list = luaL_checkstring(L, 2);
  if (SSL_CTX_set_ciphersuites(ctx, list) != 1) {
    lua_pushboolean(L, 0);
    lua_pushfstring(L, "error setting cipher list (%s)", ERR_reason_error_string(ERR_get_error()));
    return 2;
  }
#endif
  lua_pushboolean(L, 1);
  return 1;
}

/**
 * Set the depth for certificate checking.
 */
static int set_depth(lua_State *L)
{
  SSL_CTX *ctx = lsec_checkcontext(L, 1);
  SSL_CTX_set_verify_depth(ctx, (int)luaL_checkinteger(L, 2));
  lua_pushboolean(L, 1);
  return 1;
}

/**
 * Set the handshake verify options.
 */
static int set_verify(lua_State *L)
{
  int i;
  const char *str;
  int flag = 0;
  SSL_CTX *ctx = lsec_checkcontext(L, 1);
  int max = lua_gettop(L);
  for (i = 2; i <= max; i++) {
    str = luaL_checkstring(L, i);
    if (!set_verify_flag(str, &flag)) {
      lua_pushboolean(L, 0);
      lua_pushfstring(L, "invalid verify option (%s)", str);
      return 2;
    }
  }
  if (flag) SSL_CTX_set_verify(ctx, flag, NULL);
  lua_pushboolean(L, 1);
  return 1;
}

/**
 * Set the protocol options.
 */
static int set_options(lua_State *L)
{
  int i;
  const char *str;
  unsigned long flag = 0L;
  SSL_CTX *ctx = lsec_checkcontext(L, 1);
  int max = lua_gettop(L);
  /* any option? */
  if (max > 1) {
    for (i = 2; i <= max; i++) {
      str = luaL_checkstring(L, i);
      if (!set_option_flag(str, &flag)) {
        lua_pushboolean(L, 0);
        lua_pushfstring(L, "invalid option (%s)", str);
        return 2;
      }
    }
    SSL_CTX_set_options(ctx, flag);
  }
  lua_pushboolean(L, 1);
  return 1;
}

/**
 * Set the context mode.
 */
static int set_mode(lua_State *L)
{
  p_context ctx = checkctx(L, 1);
  const char *str = luaL_checkstring(L, 2);
  if (!strcmp("server", str)) {
    ctx->mode = LSEC_MODE_SERVER;
    lua_pushboolean(L, 1);
    return 1;
  }
  if (!strcmp("client", str)) {
    ctx->mode = LSEC_MODE_CLIENT;
    lua_pushboolean(L, 1);
    return 1;
  }
  lua_pushboolean(L, 0);
  lua_pushfstring(L, "invalid mode (%s)", str);
  return 1;
}   

/**
 * Configure DH parameters.
 */
static int set_dhparam(lua_State *L)
{
  SSL_CTX *ctx = lsec_checkcontext(L, 1);
  SSL_CTX_set_tmp_dh_callback(ctx, dhparam_cb);

  /* Save callback */
  luaL_getmetatable(L, "SSL:DH:Registry");
  lua_pushlightuserdata(L, (void*)ctx);
  lua_pushvalue(L, 2);
  lua_settable(L, -3);

  return 0;
}

#if !defined(OPENSSL_NO_EC)
/**
 * Set elliptic curve.
 */
static int set_curve(lua_State *L)
{
  long ret;
  EC_KEY *key = NULL;
  SSL_CTX *ctx = lsec_checkcontext(L, 1);
  const char *str = luaL_checkstring(L, 2);

  SSL_CTX_set_options(ctx, SSL_OP_SINGLE_ECDH_USE);

  key = lsec_find_ec_key(L, str);

  if (!key) {
    lua_pushboolean(L, 0);
    lua_pushfstring(L, "elliptic curve '%s' not supported", str);
    return 2;
  }

  ret = SSL_CTX_set_tmp_ecdh(ctx, key);
  /* SSL_CTX_set_tmp_ecdh takes its own reference */
  EC_KEY_free(key);

  if (!ret) {
    lua_pushboolean(L, 0);
    lua_pushfstring(L, "error setting elliptic curve (%s)",
      ERR_reason_error_string(ERR_get_error()));
    return 2;
  }

  lua_pushboolean(L, 1);
  return 1;
}

/**
 * Set elliptic curves list.
 */
static int set_curves_list(lua_State *L)
{
  SSL_CTX *ctx = lsec_checkcontext(L, 1);
  const char *str = luaL_checkstring(L, 2);

  SSL_CTX_set_options(ctx, SSL_OP_SINGLE_ECDH_USE);

  if (SSL_CTX_set1_curves_list(ctx, str) != 1) {
    lua_pushboolean(L, 0);
    lua_pushfstring(L, "unknown elliptic curve in \"%s\"", str);
    return 2;
  }

#if defined(LIBRESSL_VERSION_NUMBER) || !defined(LSEC_API_OPENSSL_1_1_0)
  (void)SSL_CTX_set_ecdh_auto(ctx, 1);
#endif

  lua_pushboolean(L, 1);
  return 1;
}
#endif

/**
 * Set the protocols a client should send for ALPN.
 */
static int set_alpn(lua_State *L)
{
  long ret;
  size_t len;
  p_context ctx = checkctx(L, 1);
  const char *str = luaL_checklstring(L, 2, &len);

  ret = SSL_CTX_set_alpn_protos(ctx->context, (const unsigned char*)str, len);
  if (ret) {
    lua_pushboolean(L, 0);
    lua_pushfstring(L, "error setting ALPN (%s)", ERR_reason_error_string(ERR_get_error()));
    return 2;
  }
  lua_pushboolean(L, 1);
  return 1;
}

/**
 * This standard callback calls the server's callback in Lua sapce.
 * The server has to return a list in wire-format strings.
 * This function uses a helper function to match server and client lists.
 */
static int alpn_cb(SSL *s, const unsigned char **out, unsigned char *outlen,
                   const unsigned char *in, unsigned int inlen, void *arg)
{
  int ret;
  size_t server_len;
  const char *server;
  p_context ctx = (p_context)arg;
  lua_State *L = ctx->L;

  luaL_getmetatable(L, "SSL:ALPN:Registry");
  lua_pushlightuserdata(L, (void*)ctx->context);
  lua_gettable(L, -2);

  lua_pushlstring(L, (const char*)in, inlen);

  lua_call(L, 1, 1);

  if (!lua_isstring(L, -1)) {
    lua_pop(L, 2);
    return SSL_TLSEXT_ERR_NOACK;
  }

  // Protocol list from server in wire-format string
  server = luaL_checklstring(L, -1, &server_len);
  ret  = SSL_select_next_proto((unsigned char**)out, outlen, (const unsigned char*)server,
                               server_len, in, inlen);
  if (ret != OPENSSL_NPN_NEGOTIATED) {
    lua_pop(L, 2);
    return SSL_TLSEXT_ERR_NOACK;
  } 

  // Copy the result because lua_pop() can collect the pointer
  ctx->alpn = malloc(*outlen);
  memcpy(ctx->alpn, (void*)*out, *outlen);
  *out = (const unsigned char*)ctx->alpn;

  lua_pop(L, 2);

  return SSL_TLSEXT_ERR_OK;
}

/**
 * Set a callback a server can use to select the next protocol with ALPN.
 */
static int set_alpn_cb(lua_State *L)
{
  p_context ctx = checkctx(L, 1);

  luaL_getmetatable(L, "SSL:ALPN:Registry");
  lua_pushlightuserdata(L, (void*)ctx->context);
  lua_pushvalue(L, 2);
  lua_settable(L, -3);

  SSL_CTX_set_alpn_select_cb(ctx->context, alpn_cb, ctx);

  lua_pushboolean(L, 1);
  return 1;
}

#if defined(LSEC_ENABLE_PSK)
/**
 * Callback to select the PSK.
 */
static unsigned int server_psk_cb(SSL *ssl, const char *identity, unsigned char *psk,
  unsigned int max_psk_len)
{
  size_t psk_len;
  const char *ret_psk;
  SSL_CTX *ctx = SSL_get_SSL_CTX(ssl);
  p_context pctx = (p_context)SSL_CTX_get_app_data(ctx);
  lua_State *L = pctx->L;

  luaL_getmetatable(L, "SSL:PSK:Registry");
  lua_pushlightuserdata(L, (void*)pctx->context);
  lua_gettable(L, -2);

  lua_pushstring(L, identity);
  lua_pushinteger(L, max_psk_len);

  lua_call(L, 2, 1);

  if (!lua_isstring(L, -1)) {
    lua_pop(L, 2);
    return 0;
  }

  ret_psk = lua_tolstring(L, -1, &psk_len);

  if (psk_len == 0 || psk_len > max_psk_len)
    psk_len = 0;
  else
    memcpy(psk, ret_psk, psk_len);

  lua_pop(L, 2);

  return psk_len;
}

/**
 * Set a PSK callback for server.
 */
static int set_server_psk_cb(lua_State *L)
{
  p_context ctx = checkctx(L, 1);

  luaL_getmetatable(L, "SSL:PSK:Registry");
  lua_pushlightuserdata(L, (void*)ctx->context);
  lua_pushvalue(L, 2);
  lua_settable(L, -3);

  SSL_CTX_set_psk_server_callback(ctx->context, server_psk_cb);

  lua_pushboolean(L, 1);
  return 1;
}

/*
 * Set the PSK indentity hint.
 */
static int set_psk_identity_hint(lua_State *L)
{
  p_context ctx = checkctx(L, 1);
  const char *hint = luaL_checkstring(L, 2);
  int ret = SSL_CTX_use_psk_identity_hint(ctx->context, hint);
  lua_pushboolean(L, ret);
  return 1;
}

/*
 * Client callback to PSK.
 */
static unsigned int client_psk_cb(SSL *ssl, const char *hint, char *identity,
  unsigned int max_identity_len, unsigned char *psk, unsigned int max_psk_len)
{
  size_t psk_len;
  size_t identity_len;
  const char *ret_psk;
  const char *ret_identity;
  SSL_CTX *ctx = SSL_get_SSL_CTX(ssl);
  p_context pctx = (p_context)SSL_CTX_get_app_data(ctx);
  lua_State *L = pctx->L;

  luaL_getmetatable(L, "SSL:PSK:Registry");
  lua_pushlightuserdata(L, (void*)pctx->context);
  lua_gettable(L, -2);

  if (hint)
    lua_pushstring(L, hint);
  else
    lua_pushnil(L);

  // Leave space to '\0'
  lua_pushinteger(L, max_identity_len-1);
  lua_pushinteger(L, max_psk_len);

  lua_call(L, 3, 2);

  if (!lua_isstring(L, -1) || !lua_isstring(L, -2)) {
    lua_pop(L, 3);
    return 0;
  }

  ret_identity = lua_tolstring(L, -2, &identity_len);
  ret_psk = lua_tolstring(L, -1, &psk_len);

  if (identity_len >= max_identity_len || psk_len > max_psk_len)
    psk_len = 0;
  else {
    memcpy(identity, ret_identity, identity_len);
    identity[identity_len] = 0;
    memcpy(psk, ret_psk, psk_len);
  }

  lua_pop(L, 3);

  return psk_len;
}

/**
 * Set a PSK callback for client.
 */
static int set_client_psk_cb(lua_State *L) {
  p_context ctx = checkctx(L, 1);

  luaL_getmetatable(L, "SSL:PSK:Registry");
  lua_pushlightuserdata(L, (void*)ctx->context);
  lua_pushvalue(L, 2);
  lua_settable(L, -3);

  SSL_CTX_set_psk_client_callback(ctx->context, client_psk_cb);

  lua_pushboolean(L, 1);
  return 1;
}
#endif

#if defined(LSEC_ENABLE_DANE)
/*
 * DANE
 */
static int dane_options[] = {
  /* TODO move into options.c
   * however this symbol is not from openssl/ssl.h but rather from
   * openssl/x509_vfy.h
   * */
#ifdef DANE_FLAG_NO_DANE_EE_NAMECHECKS
  DANE_FLAG_NO_DANE_EE_NAMECHECKS,
#endif
  0
};
static const char *dane_option_names[] = {
#ifdef DANE_FLAG_NO_DANE_EE_NAMECHECKS
  "no_ee_namechecks",
#endif
  NULL
};

static int set_dane(lua_State *L)
{
  int ret, i;
  SSL_CTX *ctx = lsec_checkcontext(L, 1);
  ret = SSL_CTX_dane_enable(ctx);
  for (i = 2; ret > 0 && i <= lua_gettop(L); i++) {
    ret = SSL_CTX_dane_set_flags(ctx, dane_options[luaL_checkoption(L, i, NULL, dane_option_names)]);
  }
  lua_pushboolean(L, (ret > 0));
  return 1;
}
#endif

/**
 * Package functions
 */
static luaL_Reg funcs[] = {
  {"create",          create},
  {"locations",       load_locations},
  {"loadcert",        load_cert},
  {"loadkey",         load_key},
  {"checkkey",        check_key},
  {"setalpn",         set_alpn},
  {"setalpncb",       set_alpn_cb},
  {"setcipher",       set_cipher},
  {"setciphersuites", set_ciphersuites},
  {"setdepth",        set_depth},
  {"setdhparam",      set_dhparam},
  {"setverify",       set_verify},
  {"setoptions",      set_options},
#if defined(LSEC_ENABLE_PSK)
  {"setpskhint",      set_psk_identity_hint},
  {"setserverpskcb",  set_server_psk_cb},
  {"setclientpskcb",  set_client_psk_cb},
#endif
  {"setmode",         set_mode},
#if !defined(OPENSSL_NO_EC)
  {"setcurve",        set_curve},
  {"setcurveslist",   set_curves_list},
#endif
#if defined(LSEC_ENABLE_DANE)
  {"setdane",         set_dane},
#endif
  {NULL, NULL}
};

/*-------------------------------- Metamethods -------------------------------*/

/**
 * Collect SSL context -- GC metamethod.
 */
static int meth_destroy(lua_State *L)
{
  p_context ctx = checkctx(L, 1);
  if (ctx->context) {
    /* Clear registries */
    luaL_getmetatable(L, "SSL:DH:Registry");
    lua_pushlightuserdata(L, (void*)ctx->context);
    lua_pushnil(L);
    lua_settable(L, -3);
    luaL_getmetatable(L, "SSL:Verify:Registry");
    lua_pushlightuserdata(L, (void*)ctx->context);
    lua_pushnil(L);
    lua_settable(L, -3);
    luaL_getmetatable(L, "SSL:ALPN:Registry");
    lua_pushlightuserdata(L, (void*)ctx->context);
    lua_pushnil(L);
    lua_settable(L, -3);
    luaL_getmetatable(L, "SSL:PSK:Registry");
    lua_pushlightuserdata(L, (void*)ctx->context);
    lua_pushnil(L);
    lua_settable(L, -3);

    SSL_CTX_free(ctx->context);
    ctx->context = NULL;
  }
  return 0;
}

/**
 * Object information -- tostring metamethod.
 */
static int meth_tostring(lua_State *L)
{
  p_context ctx = checkctx(L, 1);
  lua_pushfstring(L, "SSL context: %p", ctx);
  return 1;
}

/**
 * Set extra flags for handshake verification.
 */
static int meth_set_verify_ext(lua_State *L)
{
  int i;
  const char *str;
  int crl_flag = 0;
  int lsec_flag = 0;
  SSL_CTX *ctx = lsec_checkcontext(L, 1);
  int max = lua_gettop(L);
  for (i = 2; i <= max; i++) {
    str = luaL_checkstring(L, i);
    if (!strcmp(str, "lsec_continue")) {
      lsec_flag |= LSEC_VERIFY_CONTINUE;
    } else if (!strcmp(str, "lsec_ignore_purpose")) {
      lsec_flag |= LSEC_VERIFY_IGNORE_PURPOSE;
    } else if (!strcmp(str, "crl_check")) {
      crl_flag |= X509_V_FLAG_CRL_CHECK;
    } else if (!strcmp(str, "crl_check_chain")) {
      crl_flag |= X509_V_FLAG_CRL_CHECK_ALL;
    } else {
      lua_pushboolean(L, 0);
      lua_pushfstring(L, "invalid verify option (%s)", str);
      return 2;
    }
  }
  /* Set callback? */
  if (lsec_flag) {
    SSL_CTX_set_verify(ctx, SSL_CTX_get_verify_mode(ctx), verify_cb);
    SSL_CTX_set_cert_verify_callback(ctx, cert_verify_cb, (void*)ctx);
    /* Save flag */
    luaL_getmetatable(L, "SSL:Verify:Registry");
    lua_pushlightuserdata(L, (void*)ctx);
    lua_pushnumber(L, lsec_flag);
    lua_settable(L, -3);
  } else {
    SSL_CTX_set_verify(ctx, SSL_CTX_get_verify_mode(ctx), NULL);
    SSL_CTX_set_cert_verify_callback(ctx, NULL, NULL);
    /* Remove flag */
    luaL_getmetatable(L, "SSL:Verify:Registry");
    lua_pushlightuserdata(L, (void*)ctx);
    lua_pushnil(L);
    lua_settable(L, -3);
  }

  /* X509 flag */
  X509_STORE_set_flags(SSL_CTX_get_cert_store(ctx), crl_flag);

  /* Ok */
  lua_pushboolean(L, 1);
  return 1;
}

/**
 * Context metamethods.
 */
static luaL_Reg meta[] = {
  {"__close",    meth_destroy},
  {"__gc",       meth_destroy},
  {"__tostring", meth_tostring},
  {NULL, NULL}
};

/**
 * Index metamethods.
 */
static luaL_Reg meta_index[] = {
  {"setverifyext", meth_set_verify_ext},
  {NULL, NULL}
};


/*----------------------------- Public Functions  ---------------------------*/

/**
 * Retrieve the SSL context from the Lua stack.
 */
SSL_CTX* lsec_checkcontext(lua_State *L, int idx)
{
  p_context ctx = checkctx(L, idx);
  return ctx->context;
}

SSL_CTX* lsec_testcontext(lua_State *L, int idx)
{
  p_context ctx = testctx(L, idx);
  return (ctx) ? ctx->context : NULL;
}

/**
 * Retrieve the mode from the context in the Lua stack.
 */
int lsec_getmode(lua_State *L, int idx)
{
  p_context ctx = checkctx(L, idx);
  return ctx->mode;
}

/*-- Compat - Lua 5.1 --*/
#if (LUA_VERSION_NUM == 501)

void *lsec_testudata (lua_State *L, int ud, const char *tname) {
  void *p = lua_touserdata(L, ud);
  if (p != NULL) {  /* value is a userdata? */
    if (lua_getmetatable(L, ud)) {  /* does it have a metatable? */
      luaL_getmetatable(L, tname);  /* get correct metatable */
      if (!lua_rawequal(L, -1, -2))  /* not the same? */
        p = NULL;  /* value is a userdata with wrong metatable */
      lua_pop(L, 2);  /* remove both metatables */
      return p;
    }
  }
  return NULL;  /* value is not a userdata with a metatable */
}

#endif

/*------------------------------ Initialization ------------------------------*/

/**
 * Registre the module.
 */
LSEC_API int luaopen_ssl_context(lua_State *L)
{
  luaL_newmetatable(L, "SSL:DH:Registry");        /* Keep all DH callbacks   */
  luaL_newmetatable(L, "SSL:ALPN:Registry");      /* Keep all ALPN callbacks */
  luaL_newmetatable(L, "SSL:PSK:Registry");       /* Keep all PSK callbacks */
  luaL_newmetatable(L, "SSL:Verify:Registry");    /* Keep all verify flags   */
  luaL_newmetatable(L, "SSL:Context");
  setfuncs(L, meta);

  /* Create __index metamethods for context */
  luaL_newlib(L, meta_index);
  lua_setfield(L, -2, "__index");

  lsec_load_curves(L);

  /* Return the module */
  luaL_newlib(L, funcs);

  return 1;
}
