
/*
 * !!! DO NOT EDIT DIRECTLY !!!
 * This file was automatically generated from the following template:
 *
 * src/subsys/ngx_subsys_lua_common.h.tt2
 */


/*
 * Copyright (C) Xiaozhe Wang (chaoslawful)
 * Copyright (C) Yichun Zhang (agentzh)
 */


#ifndef _NGX_STREAM_LUA_COMMON_H_INCLUDED_
#define _NGX_STREAM_LUA_COMMON_H_INCLUDED_


#include "ngx_stream_lua_autoconf.h"

#include <nginx.h>
#include <ngx_core.h>
#include <ngx_stream.h>
#include <ngx_md5.h>

#include <setjmp.h>
#include <stdint.h>

#include <luajit.h>
#include <lualib.h>
#include <lauxlib.h>


#include "ngx_stream_lua_request.h"


#if (NGX_PCRE)

#include <pcre.h>

#if (PCRE_MAJOR > 8) || (PCRE_MAJOR == 8 && PCRE_MINOR >= 21)
#   define LUA_HAVE_PCRE_JIT 1
#else
#   define LUA_HAVE_PCRE_JIT 0
#endif

#endif


#if !defined(nginx_version) || nginx_version < 1013006
#error at least nginx 1.13.6 is required but found an older version
#endif




#if LUA_VERSION_NUM != 501
#   error unsupported Lua language version
#endif


#if !defined(LUAJIT_VERSION_NUM) || (LUAJIT_VERSION_NUM < 20000)
#   error unsupported LuaJIT version
#endif


#if (!defined OPENSSL_NO_OCSP && defined SSL_CTRL_SET_TLSEXT_STATUS_REQ_CB)
#   define NGX_STREAM_LUA_USE_OCSP 1
#endif




#ifndef NGX_HAVE_SHA1
#   if defined(nginx_version) && nginx_version >= 1011002
#       define NGX_HAVE_SHA1  1
#   endif
#endif


#ifndef MD5_DIGEST_LENGTH
#define MD5_DIGEST_LENGTH 16
#endif


#ifdef NGX_LUA_USE_ASSERT
#   include <assert.h>
#   define ngx_stream_lua_assert(a)  assert(a)
#else
#   define ngx_stream_lua_assert(a)
#endif


/* Nginx HTTP Lua Inline tag prefix */

#define NGX_STREAM_LUA_INLINE_TAG "nhli_"

#define NGX_STREAM_LUA_INLINE_TAG_LEN                                        \
    (sizeof(NGX_STREAM_LUA_INLINE_TAG) - 1)

#define NGX_STREAM_LUA_INLINE_KEY_LEN                                        \
    (NGX_STREAM_LUA_INLINE_TAG_LEN + 2 * MD5_DIGEST_LENGTH)

/* Nginx HTTP Lua File tag prefix */

#define NGX_STREAM_LUA_FILE_TAG "nhlf_"

#define NGX_STREAM_LUA_FILE_TAG_LEN                                          \
    (sizeof(NGX_STREAM_LUA_FILE_TAG) - 1)

#define NGX_STREAM_LUA_FILE_KEY_LEN                                          \
    (NGX_STREAM_LUA_FILE_TAG_LEN + 2 * MD5_DIGEST_LENGTH)


#define NGX_STREAM_CLIENT_CLOSED_REQUEST     499




#ifndef NGX_STREAM_LUA_MAX_ARGS
#define NGX_STREAM_LUA_MAX_ARGS 100
#endif


/* must be within 16 bit */
#define NGX_STREAM_LUA_CONTEXT_CONTENT                              0x0001
#define NGX_STREAM_LUA_CONTEXT_LOG                                  0x0002
#define NGX_STREAM_LUA_CONTEXT_TIMER                                0x0004
#define NGX_STREAM_LUA_CONTEXT_INIT_WORKER                          0x0008
#define NGX_STREAM_LUA_CONTEXT_BALANCER                             0x0010
#define NGX_STREAM_LUA_CONTEXT_PREREAD                              0x0020
#define NGX_STREAM_LUA_CONTEXT_SSL_CERT                             0x0040
#define NGX_STREAM_LUA_CONTEXT_SSL_CLIENT_HELLO                     0x0080


#define NGX_STREAM_LUA_FFI_NO_REQ_CTX         -100
#define NGX_STREAM_LUA_FFI_BAD_CONTEXT        -101


#if (NGX_PTR_SIZE >= 8 && !defined(_WIN64))
#define ngx_stream_lua_lightudata_mask(ludata)                               \
    ((void *) ((uintptr_t) (&ngx_stream_lua_##ludata) & ((1UL << 47) - 1)))

#else
#define ngx_stream_lua_lightudata_mask(ludata)                               \
    (&ngx_stream_lua_##ludata)
#endif


typedef struct ngx_stream_lua_main_conf_s  ngx_stream_lua_main_conf_t;
typedef struct ngx_stream_lua_srv_conf_s  ngx_stream_lua_srv_conf_t;


typedef struct ngx_stream_lua_balancer_peer_data_s
    ngx_stream_lua_balancer_peer_data_t;


typedef struct ngx_stream_lua_sema_mm_s  ngx_stream_lua_sema_mm_t;


typedef ngx_int_t (*ngx_stream_lua_main_conf_handler_pt)(ngx_log_t *log,
    ngx_stream_lua_main_conf_t *lmcf, lua_State *L);
typedef ngx_int_t (*ngx_stream_lua_srv_conf_handler_pt)(
    ngx_stream_lua_request_t *r, ngx_stream_lua_srv_conf_t *lscf, lua_State *L);


typedef struct {
    u_char              *package;
    lua_CFunction        loader;
} ngx_stream_lua_preload_hook_t;


struct ngx_stream_lua_main_conf_s {
    lua_State           *lua;
    ngx_pool_cleanup_t  *vm_cleanup;

    ngx_str_t            lua_path;
    ngx_str_t            lua_cpath;

    ngx_cycle_t         *cycle;
    ngx_pool_t          *pool;

    ngx_int_t            max_pending_timers;
    ngx_int_t            pending_timers;

    ngx_int_t            max_running_timers;
    ngx_int_t            running_timers;

    ngx_connection_t    *watcher;  /* for watching the process exit event */

#if (NGX_PCRE)
    ngx_int_t            regex_cache_entries;
    ngx_int_t            regex_cache_max_entries;
    ngx_int_t            regex_match_limit;

#if (LUA_HAVE_PCRE_JIT)
    pcre_jit_stack      *jit_stack;
#endif

#endif

    ngx_array_t         *shm_zones;  /* of ngx_shm_zone_t* */

    ngx_array_t         *shdict_zones; /* shm zones of "shdict" */

    ngx_array_t         *preload_hooks; /* of ngx_stream_lua_preload_hook_t */

    ngx_flag_t           postponed_to_preread_phase_end;

    ngx_stream_lua_main_conf_handler_pt          init_handler;
    ngx_str_t                                    init_src;

    ngx_stream_lua_main_conf_handler_pt          init_worker_handler;
    ngx_str_t                                    init_worker_src;

    ngx_stream_lua_balancer_peer_data_t          *balancer_peer_data;
                    /* neither yielding nor recursion is possible in
                     * balancer_by_lua*, so there cannot be any races among
                     * concurrent requests and it is safe to store the peer
                     * data pointer in the main conf.
                     */

    ngx_uint_t                      shm_zones_inited;

    ngx_stream_lua_sema_mm_t               *sema_mm;

    ngx_uint_t           malloc_trim_cycle;  /* a cycle is defined as the number
                                                of reqeusts */
    ngx_uint_t           malloc_trim_req_count;


    ngx_flag_t           set_sa_restart;

    unsigned             requires_preread:1;

    unsigned             requires_log:1;
    unsigned             requires_shm:1;
    unsigned             requires_capture_log:1;
};




struct ngx_stream_lua_srv_conf_s {
#if (NGX_STREAM_SSL)
    ngx_ssl_t              *ssl;  /* shared by SSL cosockets */
    ngx_uint_t              ssl_protocols;
    ngx_str_t               ssl_ciphers;
    ngx_uint_t              ssl_verify_depth;
    ngx_str_t               ssl_trusted_certificate;
    ngx_str_t               ssl_crl;
#if (nginx_version >= 1019004)
    ngx_array_t            *ssl_conf_commands;
#endif

    struct {
        ngx_stream_lua_srv_conf_handler_pt           ssl_cert_handler;
        ngx_str_t                                    ssl_cert_src;
        u_char                                      *ssl_cert_src_key;

        ngx_stream_lua_srv_conf_handler_pt           ssl_client_hello_handler;
        ngx_str_t                                    ssl_client_hello_src;
        u_char                                      *ssl_client_hello_src_key;
    } srv;
#endif

    ngx_flag_t              enable_code_cache; /* whether to enable
                                                  code cache */

    ngx_stream_lua_handler_pt           preread_handler;

    ngx_stream_lua_handler_pt           content_handler;
    ngx_stream_lua_handler_pt           log_handler;

    u_char                      *preread_chunkname;
    ngx_stream_complex_value_t   preread_src;     /* access_by_lua
                                                inline script/script
                                                file path */

    u_char                  *preread_src_key; /* cached key for access_src */

    u_char                  *content_chunkname;

    ngx_stream_complex_value_t       content_src;
                                                  /* content_by_lua
                                                   * inline script/script
                                                   * file path */

    u_char                 *content_src_key; /* cached key for content_src */

    u_char                           *log_chunkname;
    ngx_stream_complex_value_t        log_src;
                                              /* log_by_lua inline script/script
                                               * file path */

    u_char                                 *log_src_key;
    /* cached key for log_src */


    ngx_msec_t                       keepalive_timeout;
    ngx_msec_t                       connect_timeout;
    ngx_msec_t                       send_timeout;
    ngx_msec_t                       read_timeout;

    size_t                           send_lowat;
    size_t                           buffer_size;

    ngx_uint_t                       pool_size;


    ngx_flag_t                       log_socket_errors;
    ngx_flag_t                       check_client_abort;


    struct {
        ngx_str_t           src;
        u_char             *src_key;

        ngx_stream_lua_srv_conf_handler_pt        handler;
    } balancer;

};

typedef ngx_stream_lua_srv_conf_t ngx_stream_lua_loc_conf_t;


typedef enum {
    NGX_STREAM_LUA_USER_CORO_NOP      = 0,
    NGX_STREAM_LUA_USER_CORO_RESUME   = 1,
    NGX_STREAM_LUA_USER_CORO_YIELD    = 2,
    NGX_STREAM_LUA_USER_THREAD_RESUME = 3
} ngx_stream_lua_user_coro_op_t;


typedef enum {
    NGX_STREAM_LUA_CO_RUNNING   = 0, /* coroutine running */
    NGX_STREAM_LUA_CO_SUSPENDED = 1, /* coroutine suspended */
    NGX_STREAM_LUA_CO_NORMAL    = 2, /* coroutine normal */
    NGX_STREAM_LUA_CO_DEAD      = 3, /* coroutine dead */
    NGX_STREAM_LUA_CO_ZOMBIE    = 4, /* coroutine zombie */
} ngx_stream_lua_co_status_t;


typedef struct ngx_stream_lua_co_ctx_s  ngx_stream_lua_co_ctx_t;

typedef struct ngx_stream_lua_posted_thread_s  ngx_stream_lua_posted_thread_t;

struct ngx_stream_lua_posted_thread_s {
    ngx_stream_lua_co_ctx_t                     *co_ctx;
    ngx_stream_lua_posted_thread_t              *next;
};




struct ngx_stream_lua_co_ctx_s {
    void                    *data;      /* user state for cosockets */

    lua_State                       *co;
    ngx_stream_lua_co_ctx_t         *parent_co_ctx;

    ngx_stream_lua_posted_thread_t          *zombie_child_threads;

    ngx_stream_lua_cleanup_pt      cleanup;


    ngx_event_t              sleep;  /* used for ngx.sleep */

    ngx_queue_t              sem_wait_queue;

#ifdef NGX_LUA_USE_ASSERT
    int                      co_top; /* stack top after yielding/creation,
                                        only for sanity checks */
#endif

    int                      co_ref; /*  reference to anchor the thread
                                         coroutines (entry coroutine and user
                                         threads) in the Lua registry,
                                         preventing the thread coroutine
                                         from beging collected by the
                                         Lua GC */

    unsigned                 waited_by_parent:1;  /* whether being waited by
                                                     a parent coroutine */

    unsigned                 co_status:3;  /* the current coroutine's status */

    unsigned                 flushing:1; /* indicates whether the current
                                            coroutine is waiting for
                                            ngx.flush(true) */

    unsigned                 is_uthread:1; /* whether the current coroutine is
                                              a user thread */

    unsigned                 thread_spawn_yielded:1; /* yielded from
                                                        the ngx.thread.spawn()
                                                        call */
    unsigned                 sem_resume_status:1;

    unsigned                 is_wrap:1; /* set when creating coroutines via
                                           coroutine.wrap */

    unsigned                 propagate_error:1; /* set when propagating an error
                                                   from a coroutine to its
                                                   parent */
};


typedef struct {
    lua_State       *vm;
    ngx_int_t        count;
} ngx_stream_lua_vm_state_t;


typedef struct ngx_stream_lua_ctx_s {
    /* for lua_coce_cache off: */
    ngx_stream_lua_vm_state_t           *vm_state;

    ngx_stream_lua_request_t            *request;
    ngx_stream_lua_handler_pt            resume_handler;

    ngx_stream_lua_co_ctx_t             *cur_co_ctx;
                                    /* co ctx for the current coroutine */

    /* FIXME: we should use rbtree here to prevent O(n) lookup overhead */
    ngx_list_t              *user_co_ctx; /* coroutine contexts for user
                                             coroutines */

    ngx_stream_lua_co_ctx_t    entry_co_ctx; /* coroutine context for the
                                              entry coroutine */

    ngx_stream_lua_co_ctx_t   *on_abort_co_ctx; /* coroutine context for the
                                                 on_abort thread */

    int                      ctx_ref;  /*  reference to anchor
                                           request ctx data in lua
                                           registry */

    unsigned                 flushing_coros; /* number of coroutines waiting on
                                                ngx.flush(true) */

    ngx_chain_t             *out;  /* buffered output chain for HTTP 1.0 */
    ngx_chain_t             *free_bufs;
    ngx_chain_t             *busy_bufs;
    ngx_chain_t             *free_recv_bufs;

    ngx_stream_lua_cleanup_pt  *cleanup;
    ngx_stream_lua_cleanup_t   *free_cleanup; /* free list of cleanup records */



    ngx_int_t                exit_code;

    void                    *downstream;
                                    /* can be either
                                     * ngx_stream_lua_socket_tcp_upstream_t
                                     * or ngx_stream_lua_co_ctx_t */


    ngx_stream_lua_posted_thread_t         *posted_threads;

    int                      uthreads; /* number of active user threads */

    uint16_t                 context;   /* the current running directive context
                                           (or running phase) for the current
                                           Lua chunk */


    unsigned                 waiting_more_body:1;   /* 1: waiting for more
                                                       request body data;
                                                       0: no need to wait */

    unsigned         co_op:2; /*  coroutine API operation */

    unsigned         exited:1;

    unsigned         eof:1;             /*  1: last_buf has been sent;
                                            0: last_buf not sent yet */

    unsigned         capture:1;  /*  1: response body of current request
                                        is to be captured by the lua
                                        capture filter,
                                     0: not to be captured */


    unsigned         read_body_done:1;      /* 1: request body has been all
                                               read; 0: body has not been
                                               all read */

    unsigned         headers_set:1; /* whether the user has set custom
                                       response headers */

    unsigned         entered_preread_phase:1;

    unsigned         entered_content_phase:1;

    unsigned         buffering:1; /* HTTP 1.0 response body buffering flag */

    unsigned         no_abort:1; /* prohibit "world abortion" via ngx.exit()
                                    and etc */

    unsigned         header_sent:1; /* r->header_sent is not sufficient for
                                     * this because special header filters
                                     * like ngx_image_filter may intercept
                                     * the header. so we should always test
                                     * both flags. see the test case in
                                     * t/020-subrequest.t */

    unsigned         seen_last_in_filter:1;  /* used by body_filter_by_lua* */
    unsigned         seen_last_for_subreq:1; /* used by body capture filter */
    unsigned         writing_raw_req_socket:1; /* used by raw downstream
                                                  socket */
    unsigned         acquired_raw_req_socket:1;  /* whether a raw req socket
                                                    is acquired */
    unsigned         seen_body_data:1;
    unsigned         peek_needs_more_data:1; /* whether req socket is waiting
                                               for more data in preread buf */
} ngx_stream_lua_ctx_t;




extern ngx_module_t ngx_stream_lua_module;



#endif /* _NGX_STREAM_LUA_COMMON_H_INCLUDED_ */

/* vi:set ft=c ts=4 sw=4 et fdm=marker: */
