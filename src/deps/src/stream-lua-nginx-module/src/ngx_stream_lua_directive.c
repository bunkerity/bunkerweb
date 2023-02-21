
/*
 * !!! DO NOT EDIT DIRECTLY !!!
 * This file was automatically generated from the following template:
 *
 * src/subsys/ngx_subsys_lua_directive.c.tt2
 */


/*
 * Copyright (C) Xiaozhe Wang (chaoslawful)
 * Copyright (C) Yichun Zhang (agentzh)
 */


#ifndef DDEBUG
#define DDEBUG 0
#endif
#include "ddebug.h"


#include "ngx_stream_lua_common.h"
#include "ngx_stream_lua_directive.h"
#include "ngx_stream_lua_util.h"
#include "ngx_stream_lua_cache.h"
#include "ngx_stream_lua_contentby.h"
#include "ngx_stream_lua_logby.h"
#include "ngx_stream_lua_initby.h"
#include "ngx_stream_lua_initworkerby.h"
#include "ngx_stream_lua_shdict.h"
#include "ngx_stream_lua_lex.h"
#include "ngx_stream_lua_log.h"
#include "ngx_stream_lua_log_ringbuf.h"
#include "api/ngx_stream_lua_api.h"

#include "ngx_stream_lua_prereadby.h"


typedef struct ngx_stream_lua_block_parser_ctx_s
    ngx_stream_lua_block_parser_ctx_t;



static u_char *ngx_stream_lua_gen_chunk_name(ngx_conf_t *cf, const char *tag,
    size_t tag_len, size_t *chunkname_len);
static ngx_int_t ngx_stream_lua_conf_read_lua_token(ngx_conf_t *cf,
    ngx_stream_lua_block_parser_ctx_t *ctx);
static u_char *ngx_stream_lua_strlstrn(u_char *s1, u_char *last, u_char *s2,
    size_t n);


struct ngx_stream_lua_block_parser_ctx_s {
    ngx_uint_t  start_line;
    int         token_len;
};


enum {
    FOUND_LEFT_CURLY = 0,
    FOUND_RIGHT_CURLY,
    FOUND_LEFT_LBRACKET_STR,
    FOUND_LBRACKET_STR = FOUND_LEFT_LBRACKET_STR,
    FOUND_LEFT_LBRACKET_CMT,
    FOUND_LBRACKET_CMT = FOUND_LEFT_LBRACKET_CMT,
    FOUND_RIGHT_LBRACKET,
    FOUND_COMMENT_LINE,
    FOUND_DOUBLE_QUOTED,
    FOUND_SINGLE_QUOTED
};


char *
ngx_stream_lua_shared_dict(ngx_conf_t *cf, ngx_command_t *cmd, void *conf)
{
    ngx_stream_lua_main_conf_t         *lmcf = conf;
    ngx_str_t                          *value, name;
    ngx_shm_zone_t                     *zone;
    ngx_shm_zone_t                    **zp;
    ngx_stream_lua_shdict_ctx_t        *ctx;
    ssize_t                             size;

    if (lmcf->shdict_zones == NULL) {
        lmcf->shdict_zones = ngx_palloc(cf->pool, sizeof(ngx_array_t));
        if (lmcf->shdict_zones == NULL) {
            return NGX_CONF_ERROR;
        }

        if (ngx_array_init(lmcf->shdict_zones, cf->pool, 2,
                           sizeof(ngx_shm_zone_t *))
            != NGX_OK)
        {
            return NGX_CONF_ERROR;
        }
    }

    value = cf->args->elts;

    ctx = NULL;

    if (value[1].len == 0) {
        ngx_conf_log_error(NGX_LOG_EMERG, cf, 0,
                           "invalid lua shared dict name \"%V\"", &value[1]);
        return NGX_CONF_ERROR;
    }

    name = value[1];

    size = ngx_parse_size(&value[2]);

    if (size <= 8191) {
        ngx_conf_log_error(NGX_LOG_EMERG, cf, 0,
                           "invalid lua shared dict size \"%V\"", &value[2]);
        return NGX_CONF_ERROR;
    }

    ctx = ngx_pcalloc(cf->pool, sizeof(ngx_stream_lua_shdict_ctx_t));
    if (ctx == NULL) {
        return NGX_CONF_ERROR;
    }

    ctx->name = name;
    ctx->main_conf = lmcf;
    ctx->log = &cf->cycle->new_log;

    zone = ngx_stream_lua_shared_memory_add(cf, &name, (size_t) size,
                                            &ngx_stream_lua_module);
    if (zone == NULL) {
        return NGX_CONF_ERROR;
    }

    if (zone->data) {
        ctx = zone->data;

        ngx_conf_log_error(NGX_LOG_EMERG, cf, 0,
                           "lua_shared_dict \"%V\" is already defined as "
                           "\"%V\"", &name, &ctx->name);
        return NGX_CONF_ERROR;
    }

    zone->init = ngx_stream_lua_shdict_init_zone;
    zone->data = ctx;

    zp = ngx_array_push(lmcf->shdict_zones);
    if (zp == NULL) {
        return NGX_CONF_ERROR;
    }

    *zp = zone;

    lmcf->requires_shm = 1;

    return NGX_CONF_OK;
}


char *
ngx_stream_lua_code_cache(ngx_conf_t *cf, ngx_command_t *cmd, void *conf)
{
    char             *p = conf;
    ngx_flag_t       *fp;
    char             *ret;

    ret = ngx_conf_set_flag_slot(cf, cmd, conf);
    if (ret != NGX_CONF_OK) {
        return ret;
    }

    fp = (ngx_flag_t *) (p + cmd->offset);

    if (!*fp) {
        ngx_conf_log_error(NGX_LOG_ALERT, cf, 0,
                           "stream lua_code_cache is off; this will hurt "
                           "performance");
    }

    return NGX_CONF_OK;
}


char *
ngx_stream_lua_load_resty_core(ngx_conf_t *cf, ngx_command_t *cmd,
    void *conf)
{
    ngx_conf_log_error(NGX_LOG_WARN, cf, 0,
                       "lua_load_resty_core is deprecated (the lua-resty-core "
                       "library is required since "
                       "ngx_stream_lua v0.0.8)");

    return NGX_CONF_OK;
}


char *
ngx_stream_lua_package_cpath(ngx_conf_t *cf, ngx_command_t *cmd, void *conf)
{
    ngx_stream_lua_main_conf_t       *lmcf = conf;

    ngx_str_t        *value;

    if (lmcf->lua_cpath.len != 0) {
        return "is duplicate";
    }

    dd("enter");

    value = cf->args->elts;

    lmcf->lua_cpath.len = value[1].len;
    lmcf->lua_cpath.data = value[1].data;

    return NGX_CONF_OK;
}


char *
ngx_stream_lua_package_path(ngx_conf_t *cf, ngx_command_t *cmd, void *conf)
{
    ngx_stream_lua_main_conf_t       *lmcf = conf;

    ngx_str_t         *value;

    if (lmcf->lua_path.len != 0) {
        return "is duplicate";
    }

    dd("enter");

    value = cf->args->elts;

    lmcf->lua_path.len = value[1].len;
    lmcf->lua_path.data = value[1].data;

    return NGX_CONF_OK;
}








char *
ngx_stream_lua_preread_by_lua_block(ngx_conf_t *cf, ngx_command_t *cmd,
    void *conf)
{
    char        *rv;
    ngx_conf_t   save;

    save = *cf;
    cf->handler = ngx_stream_lua_preread_by_lua;
    cf->handler_conf = conf;

    rv = ngx_stream_lua_conf_lua_block_parse(cf, cmd);

    *cf = save;

    return rv;
}


char *
ngx_stream_lua_preread_by_lua(ngx_conf_t *cf, ngx_command_t *cmd, void *conf)
{
    size_t                                 chunkname_len;
    u_char                                *p, *chunkname;
    ngx_str_t                             *value;
    ngx_stream_lua_main_conf_t            *lmcf;
    ngx_stream_lua_srv_conf_t             *lscf = conf;

    ngx_stream_compile_complex_value_t     ccv;

    dd("enter");

    /*  must specify a content handler */
    if (cmd->post == NULL) {
        return NGX_CONF_ERROR;
    }

    if (lscf->preread_handler) {
        return "is duplicate";
    }

    value = cf->args->elts;

    if (value[1].len == 0) {
        /*  Oops...Invalid server conf */
        ngx_conf_log_error(NGX_LOG_ERR, cf, 0,
                           "invalid server config: no runnable Lua code");

        return NGX_CONF_ERROR;
    }

    if (cmd->post == ngx_stream_lua_preread_handler_inline) {
        chunkname = ngx_stream_lua_gen_chunk_name(cf, "preread_by_lua",
                                                  sizeof("preread_by_lua") - 1,
                                                  &chunkname_len);
        if (chunkname == NULL) {
            return NGX_CONF_ERROR;
        }

        lscf->preread_chunkname = chunkname;

        /* Don't eval nginx variables for inline lua code */

        lscf->preread_src.value = value[1];

        p = ngx_palloc(cf->pool,
                       chunkname_len + NGX_STREAM_LUA_INLINE_KEY_LEN + 1);
        if (p == NULL) {
            return NGX_CONF_ERROR;
        }

        lscf->preread_src_key = p;

        p = ngx_copy(p, chunkname, chunkname_len);
        p = ngx_copy(p, NGX_STREAM_LUA_INLINE_TAG,
                     NGX_STREAM_LUA_INLINE_TAG_LEN);
        p = ngx_stream_lua_digest_hex(p, value[1].data, value[1].len);
        *p = '\0';

    } else {
        ngx_memzero(&ccv, sizeof(ngx_stream_compile_complex_value_t));
        ccv.cf = cf;
        ccv.value = &value[1];
        ccv.complex_value = &lscf->preread_src;

        if (ngx_stream_compile_complex_value(&ccv) != NGX_OK) {
            return NGX_CONF_ERROR;
        }

        if (lscf->preread_src.lengths == NULL) {
            /* no variable found */
            p = ngx_palloc(cf->pool, NGX_STREAM_LUA_FILE_KEY_LEN + 1);
            if (p == NULL) {
                return NGX_CONF_ERROR;
            }

            lscf->preread_src_key = p;

            p = ngx_copy(p, NGX_STREAM_LUA_FILE_TAG,
                         NGX_STREAM_LUA_FILE_TAG_LEN);
            p = ngx_stream_lua_digest_hex(p, value[1].data, value[1].len);
            *p = '\0';
        }
    }

    lscf->preread_handler = (ngx_stream_lua_handler_pt) cmd->post;

    lmcf = ngx_stream_conf_get_module_main_conf(cf, ngx_stream_lua_module);

    lmcf->requires_preread = 1;

    return NGX_CONF_OK;
}

char *
ngx_stream_lua_content_by_lua_block(ngx_conf_t *cf, ngx_command_t *cmd,
    void *conf)
{
    char        *rv;
    ngx_conf_t   save;

    save = *cf;
    cf->handler = ngx_stream_lua_content_by_lua;
    cf->handler_conf = conf;

    rv = ngx_stream_lua_conf_lua_block_parse(cf, cmd);

    *cf = save;

    return rv;
}


char *
ngx_stream_lua_content_by_lua(ngx_conf_t *cf, ngx_command_t *cmd, void *conf)
{
    size_t                         chunkname_len;
    u_char                        *p;
    u_char                        *chunkname;
    ngx_str_t                     *value;

    ngx_stream_core_srv_conf_t    *cxcf;


    ngx_stream_compile_complex_value_t               ccv;

    ngx_stream_lua_loc_conf_t             *llcf = conf;

    dd("enter");

    /*  must specify a content handler */
    if (cmd->post == NULL) {
        return NGX_CONF_ERROR;
    }

    if (llcf->content_handler) {
        return "is duplicate";
    }

    value = cf->args->elts;

    dd("value[0]: %.*s", (int) value[0].len, value[0].data);
    dd("value[1]: %.*s", (int) value[1].len, value[1].data);

    if (value[1].len == 0) {
        /*  Oops...Invalid location conf */
        ngx_conf_log_error(NGX_LOG_ERR, cf, 0,
                           "invalid location config: no runnable Lua code");
        return NGX_CONF_ERROR;
    }

    if (cmd->post == ngx_stream_lua_content_handler_inline) {
        chunkname = ngx_stream_lua_gen_chunk_name(cf, "content_by_lua",
                                                  sizeof("content_by_lua") - 1,
                                                  &chunkname_len);
        if (chunkname == NULL) {
            return NGX_CONF_ERROR;
        }

        llcf->content_chunkname = chunkname;

        dd("chunkname: %s", chunkname);

        /* Don't eval nginx variables for inline lua code */

        llcf->content_src.value = value[1];

        p = ngx_palloc(cf->pool,
                       chunkname_len + NGX_STREAM_LUA_INLINE_KEY_LEN + 1);
        if (p == NULL) {
            return NGX_CONF_ERROR;
        }

        llcf->content_src_key = p;

        p = ngx_copy(p, chunkname, chunkname_len);
        p = ngx_copy(p, NGX_STREAM_LUA_INLINE_TAG,
                     NGX_STREAM_LUA_INLINE_TAG_LEN);
        p = ngx_stream_lua_digest_hex(p, value[1].data, value[1].len);
        *p = '\0';

    } else {

        ngx_memzero(&ccv, sizeof(ngx_stream_compile_complex_value_t));
        ccv.cf = cf;
        ccv.value = &value[1];
        ccv.complex_value = &llcf->content_src;

        if (ngx_stream_compile_complex_value(&ccv) != NGX_OK) {
            return NGX_CONF_ERROR;
        }

        if (llcf->content_src.lengths == NULL) {
            /* no variable found */
            p = ngx_palloc(cf->pool, NGX_STREAM_LUA_FILE_KEY_LEN + 1);
            if (p == NULL) {
                return NGX_CONF_ERROR;
            }

            llcf->content_src_key = p;

            p = ngx_copy(p, NGX_STREAM_LUA_FILE_TAG,
                         NGX_STREAM_LUA_FILE_TAG_LEN);
            p = ngx_stream_lua_digest_hex(p, value[1].data, value[1].len);
            *p = '\0';
        }
    }

    llcf->content_handler = (ngx_stream_lua_handler_pt) cmd->post;


    /*  register location content handler */
    cxcf = ngx_stream_conf_get_module_srv_conf(cf, ngx_stream_core_module);
    if (cxcf == NULL) {
        return NGX_CONF_ERROR;
    }

    cxcf->handler = ngx_stream_lua_content_handler;

    return NGX_CONF_OK;
}


char *
ngx_stream_lua_log_by_lua_block(ngx_conf_t *cf, ngx_command_t *cmd,
    void *conf)
{
    char        *rv;
    ngx_conf_t   save;

    save = *cf;
    cf->handler = ngx_stream_lua_log_by_lua;
    cf->handler_conf = conf;

    rv = ngx_stream_lua_conf_lua_block_parse(cf, cmd);

    *cf = save;

    return rv;
}


char *
ngx_stream_lua_log_by_lua(ngx_conf_t *cf, ngx_command_t *cmd, void *conf)
{
    size_t                                     chunkname_len;
    u_char                                    *p, *chunkname;
    ngx_str_t                                 *value;
    ngx_stream_lua_main_conf_t                *lmcf;
    ngx_stream_lua_loc_conf_t                 *llcf = conf;
    ngx_stream_compile_complex_value_t         ccv;

    dd("enter");

    /*  must specify a log handler */
    if (cmd->post == NULL) {
        return NGX_CONF_ERROR;
    }

    if (llcf->log_handler) {
        return "is duplicate";
    }

    value = cf->args->elts;

    if (value[1].len == 0) {
        /*  Oops...Invalid location conf */
        ngx_conf_log_error(NGX_LOG_ERR, cf, 0,
                           "invalid location config: no runnable Lua code");

        return NGX_CONF_ERROR;
    }

    if (cmd->post == ngx_stream_lua_log_handler_inline) {
        chunkname = ngx_stream_lua_gen_chunk_name(cf, "log_by_lua",
                                                  sizeof("log_by_lua") - 1,
                                                  &chunkname_len);
        if (chunkname == NULL) {
            return NGX_CONF_ERROR;
        }

        llcf->log_chunkname = chunkname;

        /* Don't eval nginx variables for inline lua code */

        llcf->log_src.value = value[1];

        p = ngx_palloc(cf->pool,
                       chunkname_len + NGX_STREAM_LUA_INLINE_KEY_LEN + 1);
        if (p == NULL) {
            return NGX_CONF_ERROR;
        }

        llcf->log_src_key = p;

        p = ngx_copy(p, chunkname, chunkname_len);
        p = ngx_copy(p, NGX_STREAM_LUA_INLINE_TAG,
                     NGX_STREAM_LUA_INLINE_TAG_LEN);
        p = ngx_stream_lua_digest_hex(p, value[1].data, value[1].len);
        *p = '\0';

    } else {
        ngx_memzero(&ccv, sizeof(ngx_stream_compile_complex_value_t));
        ccv.cf = cf;
        ccv.value = &value[1];
        ccv.complex_value = &llcf->log_src;

        if (ngx_stream_compile_complex_value(&ccv) != NGX_OK) {
            return NGX_CONF_ERROR;
        }

        if (llcf->log_src.lengths == NULL) {
            /* no variable found */
            p = ngx_palloc(cf->pool, NGX_STREAM_LUA_FILE_KEY_LEN + 1);
            if (p == NULL) {
                return NGX_CONF_ERROR;
            }

            llcf->log_src_key = p;

            p = ngx_copy(p, NGX_STREAM_LUA_FILE_TAG,
                         NGX_STREAM_LUA_FILE_TAG_LEN);
            p = ngx_stream_lua_digest_hex(p, value[1].data, value[1].len);
            *p = '\0';
        }
    }

    llcf->log_handler = (ngx_stream_lua_handler_pt) cmd->post;

    lmcf = ngx_stream_conf_get_module_main_conf(cf, ngx_stream_lua_module);

    lmcf->requires_log = 1;

    return NGX_CONF_OK;
}




char *
ngx_stream_lua_init_by_lua_block(ngx_conf_t *cf, ngx_command_t *cmd,
    void *conf)
{
    char        *rv;
    ngx_conf_t   save;

    save = *cf;
    cf->handler = ngx_stream_lua_init_by_lua;
    cf->handler_conf = conf;

    rv = ngx_stream_lua_conf_lua_block_parse(cf, cmd);

    *cf = save;

    return rv;
}


char *
ngx_stream_lua_init_by_lua(ngx_conf_t *cf, ngx_command_t *cmd,
    void *conf)
{
    u_char                              *name;
    ngx_str_t                           *value;
    ngx_stream_lua_main_conf_t          *lmcf = conf;

    dd("enter");

    /*  must specify a content handler */
    if (cmd->post == NULL) {
        return NGX_CONF_ERROR;
    }

    if (lmcf->init_handler) {
        return "is duplicate";
    }

    value = cf->args->elts;

    if (value[1].len == 0) {
        /*  Oops...Invalid location conf */
        ngx_conf_log_error(NGX_LOG_ERR, cf, 0,
                           "invalid location config: no runnable Lua code");
        return NGX_CONF_ERROR;
    }

    lmcf->init_handler = (ngx_stream_lua_main_conf_handler_pt) cmd->post;

    if (cmd->post == ngx_stream_lua_init_by_file) {
        name = ngx_stream_lua_rebase_path(cf->pool, value[1].data,
                                          value[1].len);
        if (name == NULL) {
            return NGX_CONF_ERROR;
        }

        lmcf->init_src.data = name;
        lmcf->init_src.len = ngx_strlen(name);

    } else {
        lmcf->init_src = value[1];
    }

    return NGX_CONF_OK;
}


char *
ngx_stream_lua_init_worker_by_lua_block(ngx_conf_t *cf, ngx_command_t *cmd,
    void *conf)
{
    char        *rv;
    ngx_conf_t   save;

    save = *cf;
    cf->handler = ngx_stream_lua_init_worker_by_lua;
    cf->handler_conf = conf;

    rv = ngx_stream_lua_conf_lua_block_parse(cf, cmd);

    *cf = save;

    return rv;
}


char *
ngx_stream_lua_init_worker_by_lua(ngx_conf_t *cf, ngx_command_t *cmd,
    void *conf)
{
    u_char                      *name;
    ngx_str_t                   *value;

    ngx_stream_lua_main_conf_t          *lmcf = conf;

    dd("enter");

    /*  must specify a content handler */
    if (cmd->post == NULL) {
        return NGX_CONF_ERROR;
    }

    if (lmcf->init_worker_handler) {
        return "is duplicate";
    }

    value = cf->args->elts;

    lmcf->init_worker_handler = (ngx_stream_lua_main_conf_handler_pt) cmd->post;

    if (cmd->post == ngx_stream_lua_init_worker_by_file) {
        name = ngx_stream_lua_rebase_path(cf->pool, value[1].data,
                                          value[1].len);
        if (name == NULL) {
            return NGX_CONF_ERROR;
        }

        lmcf->init_worker_src.data = name;
        lmcf->init_worker_src.len = ngx_strlen(name);

    } else {
        lmcf->init_worker_src = value[1];
    }

    return NGX_CONF_OK;
}




static u_char *
ngx_stream_lua_gen_chunk_name(ngx_conf_t *cf, const char *tag, size_t tag_len,
    size_t *chunkname_len)
{
    u_char      *p, *out;
    size_t       len;

    len = sizeof("=(:)") - 1 + tag_len + cf->conf_file->file.name.len
          + NGX_INT64_LEN + 1;

    out = ngx_palloc(cf->pool, len);
    if (out == NULL) {
        return NULL;
    }

    if (cf->conf_file->file.name.len) {
        p = cf->conf_file->file.name.data + cf->conf_file->file.name.len;
        while (--p >= cf->conf_file->file.name.data) {
            if (*p == '/' || *p == '\\') {
                p++;
                goto found;
            }
        }

        p++;

    } else {
        p = cf->conf_file->file.name.data;
    }

found:

    p = ngx_snprintf(out, len, "=%*s(%*s:%d)%Z",
                     tag_len, tag, cf->conf_file->file.name.data
                     + cf->conf_file->file.name.len - p,
                     p, cf->conf_file->line);

    *chunkname_len = p - out - 1;  /* exclude the trailing '\0' byte */

    return out;
}


/* a specialized version of the standard ngx_conf_parse() function */
char *
ngx_stream_lua_conf_lua_block_parse(ngx_conf_t *cf, ngx_command_t *cmd)
{
    ngx_stream_lua_block_parser_ctx_t           ctx;

    int               level = 1;
    char             *rv;
    u_char           *p;
    size_t            len;
    ngx_str_t        *src, *dst;
    ngx_int_t         rc;
    ngx_uint_t        i, start_line;
    ngx_array_t      *saved;
    enum {
        parse_block = 0,
        parse_param
    } type;

    if (cf->conf_file->file.fd != NGX_INVALID_FILE) {

        type = parse_block;

    } else {
        type = parse_param;
    }

    saved = cf->args;

    cf->args = ngx_array_create(cf->temp_pool, 4, sizeof(ngx_str_t));
    if (cf->args == NULL) {
        return NGX_CONF_ERROR;
    }

    ctx.token_len = 0;
    start_line = cf->conf_file->line;

    dd("init start line: %d", (int) start_line);

    ctx.start_line = start_line;

    for ( ;; ) {
        rc = ngx_stream_lua_conf_read_lua_token(cf, &ctx);

        dd("parser start line: %d", (int) start_line);

        switch (rc) {

        case NGX_ERROR:
            goto done;

        case FOUND_LEFT_CURLY:

            ctx.start_line = cf->conf_file->line;

            if (type == parse_param) {
                ngx_conf_log_error(NGX_LOG_EMERG, cf, 0,
                                   "block directives are not supported "
                                   "in -g option");
                goto failed;
            }

            level++;
            dd("seen block start: level=%d", (int) level);
            break;

        case FOUND_RIGHT_CURLY:

            level--;
            dd("seen block done: level=%d", (int) level);

            if (type != parse_block || level < 0) {
                ngx_conf_log_error(NGX_LOG_EMERG, cf, 0,
                                   "unexpected \"}\": level %d, "
                                   "starting at line %ui", level,
                                   start_line);
                goto failed;
            }

            if (level == 0) {
                ngx_stream_lua_assert(cf->handler);

                src = cf->args->elts;

                for (len = 0, i = 0; i < cf->args->nelts; i++) {
                    len += src[i].len;
                }

                dd("saved nelts: %d", (int) saved->nelts);
                dd("temp nelts: %d", (int) cf->args->nelts);
#if 0
                ngx_stream_lua_assert(saved->nelts == 1);
#endif

                dst = ngx_array_push(saved);
                if (dst == NULL) {
                    return NGX_CONF_ERROR;
                }
                dst->len = len;
                dst->len--;  /* skip the trailing '}' block terminator */

                p = ngx_palloc(cf->pool, len);
                if (p == NULL) {
                    return NGX_CONF_ERROR;
                }
                dst->data = p;

                for (i = 0; i < cf->args->nelts; i++) {
                    p = ngx_copy(p, src[i].data, src[i].len);
                }

                p[-1] = '\0';  /* override the last '}' char to null */

                cf->args = saved;

                rv = (*cf->handler)(cf, cmd, cf->handler_conf);
                if (rv == NGX_CONF_OK) {
                    goto done;
                }

                if (rv == NGX_CONF_ERROR) {
                    goto failed;
                }

                ngx_conf_log_error(NGX_LOG_EMERG, cf, 0, rv);

                goto failed;
            }

            break;

        case FOUND_LBRACKET_STR:
        case FOUND_LBRACKET_CMT:
        case FOUND_RIGHT_LBRACKET:
        case FOUND_COMMENT_LINE:
        case FOUND_DOUBLE_QUOTED:
        case FOUND_SINGLE_QUOTED:
            break;

        default:

            ngx_conf_log_error(NGX_LOG_EMERG, cf, 0,
                               "unknown return value from the lexer: %i", rc);
            goto failed;
        }
    }

failed:

    rc = NGX_ERROR;

done:

    if (rc == NGX_ERROR) {
        return NGX_CONF_ERROR;
    }

    return NGX_CONF_OK;
}


static ngx_int_t
ngx_stream_lua_conf_read_lua_token(ngx_conf_t *cf,
    ngx_stream_lua_block_parser_ctx_t *ctx)
{
    enum {
        OVEC_SIZE = 2
    };
    int          i, rc;
    int          ovec[OVEC_SIZE];
    u_char      *start, *p, *q, ch;
    off_t        file_size;
    size_t       len, buf_size;
    ssize_t      n, size;
    ngx_uint_t   start_line;
    ngx_str_t   *word;
    ngx_buf_t   *b;
#if defined(nginx_version) && nginx_version >= 1009002
    ngx_buf_t   *dump;
#endif

    b = cf->conf_file->buffer;
#if defined(nginx_version) && nginx_version >= 1009002
    dump = cf->conf_file->dump;
#endif
    start = b->pos;
    start_line = cf->conf_file->line;
    buf_size = b->end - b->start;

    dd("lexer start line: %d", (int) start_line);

    file_size = ngx_file_size(&cf->conf_file->file.info);

    for ( ;; ) {

        if (b->pos >= b->last
            || (b->last - b->pos < (b->end - b->start) / 3
                && cf->conf_file->file.offset < file_size))
        {

            if (cf->conf_file->file.offset >= file_size) {

                cf->conf_file->line = ctx->start_line;

                ngx_conf_log_error(NGX_LOG_EMERG, cf, 0,
                                   "unexpected end of file, expecting "
                                   "terminating characters for lua code "
                                   "block");
                return NGX_ERROR;
            }

            len = b->last - start;

            if (len == buf_size) {

                cf->conf_file->line = start_line;

                ngx_conf_log_error(NGX_LOG_EMERG, cf, 0,
                                   "too long lua code block, probably "
                                   "missing terminating characters");

                return NGX_ERROR;
            }

            if (len) {
                ngx_memmove(b->start, start, len);
            }

            size = (ssize_t) (file_size - cf->conf_file->file.offset);

            if (size > b->end - (b->start + len)) {
                size = b->end - (b->start + len);
            }

            n = ngx_read_file(&cf->conf_file->file, b->start + len, size,
                              cf->conf_file->file.offset);

            if (n == NGX_ERROR) {
                return NGX_ERROR;
            }

            if (n != size) {
                ngx_conf_log_error(NGX_LOG_EMERG, cf, 0,
                                   ngx_read_file_n " returned "
                                   "only %z bytes instead of %z",
                                   n, size);
                return NGX_ERROR;
            }

            b->pos = b->start + (b->pos - start);
            b->last = b->start + len + n;
            start = b->start;

#if defined(nginx_version) && nginx_version >= 1009002
            if (dump) {
                dump->last = ngx_cpymem(dump->last, b->start + len, size);
            }
#endif
        }

        rc = ngx_stream_lua_lex(b->pos, b->last - b->pos, ovec);

        if (rc < 0) {  /* no match */
            /* alas. the lexer does not yet support streaming processing. need
             * more work below */

            if (cf->conf_file->file.offset >= file_size) {

                cf->conf_file->line = ctx->start_line;

                ngx_conf_log_error(NGX_LOG_EMERG, cf, 0,
                                   "unexpected end of file, expecting "
                                   "terminating characters for lua code "
                                   "block");
                return NGX_ERROR;
            }

            len = b->last - b->pos;

            if (len == buf_size) {

                cf->conf_file->line = start_line;

                ngx_conf_log_error(NGX_LOG_EMERG, cf, 0,
                                   "too long lua code block, probably "
                                   "missing terminating characters");

                return NGX_ERROR;
            }

            if (len) {
                ngx_memcpy(b->start, b->pos, len);
            }

            size = (ssize_t) (file_size - cf->conf_file->file.offset);

            if (size > b->end - (b->start + len)) {
                size = b->end - (b->start + len);
            }

            n = ngx_read_file(&cf->conf_file->file, b->start + len, size,
                              cf->conf_file->file.offset);

            if (n == NGX_ERROR) {
                return NGX_ERROR;
            }

            if (n != size) {
                ngx_conf_log_error(NGX_LOG_EMERG, cf, 0,
                                   ngx_read_file_n " returned "
                                   "only %z bytes instead of %z",
                                   n, size);
                return NGX_ERROR;
            }

            b->pos = b->start + len;
            b->last = b->pos + n;
            start = b->start;

            continue;
        }

        if (rc == FOUND_LEFT_LBRACKET_STR || rc == FOUND_LEFT_LBRACKET_CMT) {

            /* we update the line numbers for best error messages when the
             * closing long bracket is missing */

            for (i = 0; i < ovec[0]; i++) {
                ch = b->pos[i];
                if (ch == LF) {
                    cf->conf_file->line++;
                }
            }

            b->pos += ovec[0];
            ovec[1] -= ovec[0];
            ovec[0] = 0;

            if (rc == FOUND_LEFT_LBRACKET_CMT) {
                p = &b->pos[2];     /* we skip the leading "--" prefix */
                rc = FOUND_LBRACKET_CMT;

            } else {
                p = b->pos;
                rc = FOUND_LBRACKET_STR;
            }

            /* we temporarily rewrite [=*[ in the input buffer to ]=*] to
             * construct the pattern for the corresponding closing long
             * bracket without additional buffers. */

            ngx_stream_lua_assert(p[0] == '[');
            p[0] = ']';

            ngx_stream_lua_assert(b->pos[ovec[1] - 1] == '[');
            b->pos[ovec[1] - 1] = ']';

            /* search for the corresponding closing bracket */

            dd("search pattern for the closing long bracket: \"%.*s\" (len=%d)",
               (int) (b->pos + ovec[1] - p), p, (int) (b->pos + ovec[1] - p));

            q = ngx_stream_lua_strlstrn(b->pos + ovec[1], b->last, p,
                                        b->pos + ovec[1] - p - 1);

            if (q == NULL) {
                ngx_conf_log_error(NGX_LOG_EMERG, cf, 0,
                                   "Lua code block missing the closing "
                                   "long bracket \"%*s\"",
                                   b->pos + ovec[1] - p, p);
                return NGX_ERROR;
            }

            /* restore the original opening long bracket */

            p[0] = '[';
            b->pos[ovec[1] - 1] = '[';

            ovec[1] = q - b->pos + b->pos + ovec[1] - p;

            dd("found long bracket token: \"%.*s\"",
               (int) (ovec[1] - ovec[0]), b->pos + ovec[0]);
        }

        for (i = 0; i < ovec[1]; i++) {
            ch = b->pos[i];
            if (ch == LF) {
                cf->conf_file->line++;
            }
        }

        b->pos += ovec[1];
        ctx->token_len = ovec[1] - ovec[0];

        break;
    }

    word = ngx_array_push(cf->args);
    if (word == NULL) {
        return NGX_ERROR;
    }

    word->data = ngx_pnalloc(cf->temp_pool, b->pos - start);
    if (word->data == NULL) {
        return NGX_ERROR;
    }

    len = b->pos - start;
    ngx_memcpy(word->data, start, len);
    word->len = len;

    return rc;
}


char *
ngx_stream_lua_capture_error_log(ngx_conf_t *cf, ngx_command_t *cmd,
    void *conf)
{
#ifndef HAVE_INTERCEPT_ERROR_LOG_PATCH
    return "not found: missing the capture error log patch for nginx";
#else
    ngx_str_t                     *value;
    ssize_t                        size;
    u_char                        *data;
    ngx_cycle_t                   *cycle;

    ngx_stream_lua_main_conf_t            *lmcf = conf;
    ngx_stream_lua_log_ringbuf_t          *ringbuf;

    value = cf->args->elts;
    cycle = cf->cycle;

    if (lmcf->requires_capture_log) {
        return "is duplicate";
    }

    if (value[1].len == 0) {
        ngx_conf_log_error(NGX_LOG_EMERG, cf, 0,
                           "invalid capture error log size \"%V\"",
                           &value[1]);
        return NGX_CONF_ERROR;
    }

    size = ngx_parse_size(&value[1]);

    if (size < NGX_MAX_ERROR_STR) {
        ngx_conf_log_error(NGX_LOG_EMERG, cf, 0,
                           "invalid capture error log size \"%V\", "
                           "minimum size is %d", &value[1],
                           NGX_MAX_ERROR_STR);
        return NGX_CONF_ERROR;
    }

    if (cycle->intercept_error_log_handler) {
        return "capture error log handler has been hooked";
    }

    ringbuf = (ngx_stream_lua_log_ringbuf_t *)
              ngx_palloc(cf->pool, sizeof(ngx_stream_lua_log_ringbuf_t));
    if (ringbuf == NULL) {
        return NGX_CONF_ERROR;
    }

    data = ngx_palloc(cf->pool, size);
    if (data == NULL) {
        return NGX_CONF_ERROR;
    }

    ngx_stream_lua_log_ringbuf_init(ringbuf, data, size);

    lmcf->requires_capture_log = 1;
    cycle->intercept_error_log_handler = (ngx_log_intercept_pt)
                                         ngx_stream_lua_capture_log_handler;
    cycle->intercept_error_log_data = ringbuf;

    return NGX_CONF_OK;
#endif
}


/*
 * ngx_stream_lua_strlstrn() is intended to search for static substring
 * with known length in string until the argument last. The argument n
 * must be length of the second substring - 1.
 */

static u_char *
ngx_stream_lua_strlstrn(u_char *s1, u_char *last, u_char *s2, size_t n)
{
    ngx_uint_t  c1, c2;

    c2 = (ngx_uint_t) *s2++;
    last -= n;

    do {
        do {
            if (s1 >= last) {
                return NULL;
            }

            c1 = (ngx_uint_t) *s1++;

            dd("testing char '%c' vs '%c'", (int) c1, (int) c2);

        } while (c1 != c2);

        dd("testing against pattern \"%.*s\"", (int) n, s2);

    } while (ngx_strncmp(s1, s2, n) != 0);

    return --s1;
}


static ngx_int_t
ngx_stream_lua_undefined_var(ngx_stream_session_t *s,
    ngx_stream_variable_value_t *v, uintptr_t data)
{
    v->not_found = 1;

    return NGX_OK;
}


char *
ngx_stream_lua_add_variable(ngx_conf_t *cf, ngx_command_t *cmd,
    void *conf)
{
    ngx_stream_variable_t           *var;
    ngx_str_t                       *value;
    ngx_int_t                        ret;

    value = cf->args->elts;

    if (value[1].data[0] != '$') {
        ngx_conf_log_error(NGX_LOG_EMERG, cf, 0,
                           "invalid variable name \"%V\"", &value[1]);
        return NGX_CONF_ERROR;
    }

    value[1].len--;
    value[1].data++;

    var = ngx_stream_add_variable(cf, value + 1, NGX_STREAM_VAR_CHANGEABLE
                                  |NGX_STREAM_VAR_WEAK);
    if (var == NULL) {
        return NGX_CONF_ERROR;
    }

    if (var->get_handler == NULL) {
        var->get_handler = ngx_stream_lua_undefined_var;
    }

    ret = ngx_stream_get_variable_index(cf, value + 1);
    if (ret == NGX_ERROR) {
        return NGX_CONF_ERROR;
    }

    return NGX_CONF_OK;
}


/* vi:set ft=c ts=4 sw=4 et fdm=marker: */
