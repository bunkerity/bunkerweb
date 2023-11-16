

/* TODO : organize and add */
/* TODO : check - should it be r->main? */

#define     ndk_http_uri(r)                         (r)->uri
#define     ndk_http_request_uri(r)                 (r)->unparsed_uri

#define     ndk_http_header_in(r,name)              ((r)->headers_in.name ? &(r)->headers_in.name->value : NULL)
#define     ndk_http_header_out(r,name)             ((r)->headers_out.name ? &(r)->headers_out.name->value : NULL)

#define     ndk_http_host_header(r)                 ndk_http_header_in (r, host)
#define     ndk_http_connection_header(r)           ndk_http_header_in (r, connection)
#define     ndk_http_if_modified_since_header(r)    ndk_http_header_in (r, if_modified_since)
#define     ndk_http_user_agent_header(r)           ndk_http_header_in (r, user_agent)
#define     ndk_http_referer_header(r)              ndk_http_header_in (r, referer)
#define     ndk_http_content_length_header(r)       ndk_http_header_in (r, content_length)
#define     ndk_http_content_type_header(r)         ndk_http_header_in (r, content_type)
#define     ndk_http_range_header(r)                ndk_http_header_in (r, range)
#define     ndk_http_if_range_header(r)             ndk_http_header_in (r, if_range)
#define     ndk_http_transfer_encoding_header(r)    ndk_http_header_in (r, transfer_encoding)
#define     ndk_http_expect_header(r)               ndk_http_header_in (r, expect)
#define     ndk_http_accept_encoding_header(r)      ndk_http_header_in (r, accept_encoding)
#define     ndk_http_via_header(r)                  ndk_http_header_in (r, via)
#define     ndk_http_authorization_header(r)        ndk_http_header_in (r, authorization)
#define     ndk_http_keep_alive_header(r)           ndk_http_header_in (r, keep_alive)
#define     ndk_http_x_forwarded_for_header(r)      ndk_http_header_in (r, x_forwarded_for)
#define     ndk_http_x_real_ip_header(r)            ndk_http_header_in (r, x_real_ip)
#define     ndk_http_accept_header(r)               ndk_http_header_in (r, accept)
#define     ndk_http_accept_language_header(r)      ndk_http_header_in (r, accept_language)
#define     ndk_http_depth_header(r)                ndk_http_header_in (r, depth)
#define     ndk_http_destination_header(r)          ndk_http_header_in (r, destination)
#define     ndk_http_overwrite_header(r)            ndk_http_header_in (r, overwrite)
#define     ndk_http_date_header(r)                 ndk_http_header_in (r, date)

