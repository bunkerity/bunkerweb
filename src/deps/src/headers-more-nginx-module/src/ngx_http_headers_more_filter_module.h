
/*
 * Copyright (c) Yichun Zhang (agentzh)
 */


#ifndef NGX_HTTP_HEADERS_MORE_FILTER_MODULE_H
#define NGX_HTTP_HEADERS_MORE_FILTER_MODULE_H


#include <ngx_core.h>
#include <ngx_http.h>
#include <assert.h>


typedef enum {
    ngx_http_headers_more_opcode_set,
    ngx_http_headers_more_opcode_clear
} ngx_http_headers_more_opcode_t;


typedef struct {
    ngx_array_t                       *types; /* of ngx_str_t */
    ngx_array_t                       *statuses; /* of ngx_uint_t */
    ngx_array_t                       *headers; /* of ngx_http_header_val_t */
    ngx_flag_t                         is_input;
} ngx_http_headers_more_cmd_t;


typedef struct {
    ngx_array_t             *cmds; /* of ngx_http_headers_more_cmd_t */
} ngx_http_headers_more_loc_conf_t;


typedef struct {
    ngx_int_t              postponed_to_phase_end;
    ngx_int_t              requires_filter;
    ngx_int_t              requires_handler;
} ngx_http_headers_more_main_conf_t;


typedef struct ngx_http_headers_more_header_val_s
    ngx_http_headers_more_header_val_t;


typedef ngx_int_t (*ngx_http_headers_more_set_header_pt)(ngx_http_request_t *r,
    ngx_http_headers_more_header_val_t *hv, ngx_str_t *value);


typedef struct {
    ngx_str_t                               name;
    ngx_uint_t                              offset;
    ngx_http_headers_more_set_header_pt     handler;
} ngx_http_headers_more_set_header_t;


struct ngx_http_headers_more_header_val_s {
    ngx_http_complex_value_t                value;
    ngx_uint_t                              hash;
    ngx_str_t                               key;
    ngx_http_headers_more_set_header_pt     handler;
    ngx_uint_t                              offset;
    ngx_flag_t                              replace;
    ngx_flag_t                              wildcard;
};


extern ngx_module_t  ngx_http_headers_more_filter_module;


#ifndef ngx_str_set
#define ngx_str_set(str, text)                                               \
        (str)->len = sizeof(text) - 1; (str)->data = (u_char *) text
#endif


#define ngx_http_headers_more_assert(a)  assert(a)


#endif /* NGX_HTTP_HEADERS_MORE_FILTER_MODULE_H */
