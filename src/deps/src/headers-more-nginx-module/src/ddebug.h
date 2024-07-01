#ifndef DDEBUG_H
#define DDEBUG_H


#include <ngx_config.h>
#include <ngx_core.h>
#include <ngx_http.h>
#include <nginx.h>


#if defined(DDEBUG) && (DDEBUG)

#   if (NGX_HAVE_VARIADIC_MACROS)

#       define dd(...) fprintf(stderr, "headers-more *** %s: ", __func__); \
            fprintf(stderr, __VA_ARGS__); \
            fprintf(stderr, " at %s line %d.\n", __FILE__, __LINE__)

#   else

#include <stdarg.h>
#include <stdio.h>

#include <stdarg.h>

static ngx_inline void
dd(const char * fmt, ...) {
}

#    endif

#   if DDEBUG > 1

#       define dd_enter() dd_enter_helper(r, __func__)

#       if defined(nginx_version) && nginx_version >= 8011
#           define dd_main_req_count r->main->count
#       else
#           define dd_main_req_count 0
#       endif

static ngx_inline void
dd_enter_helper(ngx_http_request_t *r, const char *func)
{
    ngx_http_posted_request_t       *pr;

    fprintf(stderr, "headers-more *** enter %s %.*s %.*s?%.*s c:%d m:%p r:%p ar:%p pr:%p",
            func,
            (int) r->method_name.len, r->method_name.data,
            (int) r->uri.len, r->uri.data,
            (int) r->args.len, r->args.data,
            (int) dd_main_req_count, r->main,
            r, r->connection->data, r->parent);

    if (r->posted_requests) {
        fprintf(stderr, " posted:");

        for (pr = r->posted_requests; pr; pr = pr->next) {
            fprintf(stderr, "%p,", pr);
        }
    }

    fprintf(stderr, "\n");
}

#   else

#       define dd_enter()

#   endif

#else

#   if (NGX_HAVE_VARIADIC_MACROS)

#       define dd(...)

#       define dd_enter()

#   else

#include <stdarg.h>

static ngx_inline void
dd(const char * fmt, ...) {
}

static ngx_inline void
dd_enter() {
}

#   endif

#endif

#if defined(DDEBUG) && (DDEBUG)

#define dd_check_read_event_handler(r)   \
    dd("r->read_event_handler = %s", \
        r->read_event_handler == ngx_http_block_reading ? \
            "ngx_http_block_reading" : \
        r->read_event_handler == ngx_http_test_reading ? \
            "ngx_http_test_reading" : \
        r->read_event_handler == ngx_http_request_empty_handler ? \
            "ngx_http_request_empty_handler" : "UNKNOWN")

#define dd_check_write_event_handler(r)   \
    dd("r->write_event_handler = %s", \
        r->write_event_handler == ngx_http_handler ? \
            "ngx_http_handler" : \
        r->write_event_handler == ngx_http_core_run_phases ? \
            "ngx_http_core_run_phases" : \
        r->write_event_handler == ngx_http_request_empty_handler ? \
            "ngx_http_request_empty_handler" : "UNKNOWN")

#else

#define dd_check_read_event_handler(r)
#define dd_check_write_event_handler(r)

#endif

#endif /* DDEBUG_H */

