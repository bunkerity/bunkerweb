/*
** String handling.
** Copyright (C) 2005-2022 Mike Pall. See Copyright Notice in luajit.h
*/

#ifndef _LJ_STR_H
#define _LJ_STR_H

#include <stdarg.h>

#include "lj_obj.h"

/* String helpers. */
LJ_FUNC int32_t LJ_FASTCALL lj_str_cmp(GCstr *a, GCstr *b);
LJ_FUNC const char *lj_str_find(const char *s, const char *f,
				MSize slen, MSize flen);
LJ_FUNC int lj_str_haspattern(GCstr *s);

/* String interning. */
LJ_FUNC void lj_str_resize(lua_State *L, MSize newmask);
LJ_FUNCA GCstr *lj_str_new(lua_State *L, const char *str, size_t len);
LJ_FUNC void LJ_FASTCALL lj_str_free(global_State *g, GCstr *s);
LJ_FUNC void LJ_FASTCALL lj_str_init(lua_State *L);
#define lj_str_freetab(g) \
  (lj_mem_freevec(g, g->str.tab, g->str.mask+1, GCRef))

#define lj_str_newz(L, s)	(lj_str_new(L, s, strlen(s)))
#define lj_str_newlit(L, s)	(lj_str_new(L, "" s, sizeof(s)-1))
#define lj_str_size(len)	(sizeof(GCstr) + (((len)+4) & ~(MSize)3))

#ifdef LJ_HAS_OPTIMISED_HASH
typedef StrHash (*str_sparse_hashfn) (uint64_t, const char *, MSize);
extern str_sparse_hashfn hash_sparse;

#if LUAJIT_SECURITY_STRHASH
typedef StrHash (*str_dense_hashfn) (uint64_t, StrHash, const char *, MSize);
extern str_dense_hashfn hash_dense;
#endif

extern void str_hash_init_sse42 (void);
#endif

#endif
