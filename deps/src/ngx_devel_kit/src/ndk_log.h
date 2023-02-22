
/* TODO : fix the conf_log macros */

#define NGX_LOG_DEBUG_SCRIPT        NGX_LOG_DEBUG_HTTP      /* TODO : add new section to log/conf directives */

#define ndk_conf_to_log(cf)         ((cf)->log)

#ifndef ndk_request_to_log
#define ndk_request_to_log(r)       ((r)->connection->log)
#endif


/*********************************/

#if (NGX_HAVE_C99_VARIADIC_MACROS)

#define ndk_log_stderr(log,...)                     ngx_log_error (NGX_LOG_STDERR, log, 0, __VA_ARGS__)
#define ndk_log_emerg(log,...)                      ngx_log_error (NGX_LOG_EMERG, log, 0, __VA_ARGS__)
#define ndk_log_alert(log,...)                      ngx_log_error (NGX_LOG_ALERT, log, 0, __VA_ARGS__)
#define ndk_log_crit(log,...)                       ngx_log_error (NGX_LOG_CRIT, log, 0, __VA_ARGS__)
#define ndk_log_err(log,...)                        ngx_log_error (NGX_LOG_ERR, log, 0, __VA_ARGS__)
#define ndk_log_warning(log,...)                    ngx_log_error (NGX_LOG_WARN, log, 0, __VA_ARGS__)
#define ndk_log_notice(log,...)                     ngx_log_error (NGX_LOG_NOTICE, log, 0, __VA_ARGS__)
#define ndk_log_info(log,...)                       ngx_log_error (NGX_LOG_INFO, log, 0, __VA_ARGS__)

#define ndk_conf_log_stderr(cf,...)                 ngx_conf_log_error (NGX_LOG_STDERR, cf, 0, __VA_ARGS__)
#define ndk_conf_log_emerg(cf,...)                  ngx_conf_log_error (NGX_LOG_EMERG, cf, 0, __VA_ARGS__)
#define ndk_conf_log_alert(cf,...)                  ngx_conf_log_error (NGX_LOG_ALERT, cf, 0, __VA_ARGS__)
#define ndk_conf_log_crit(cf,...)                   ngx_conf_log_error (NGX_LOG_CRIT, cf, 0, __VA_ARGS__)
#define ndk_conf_log_err(cf,...)                    ngx_conf_log_error (NGX_LOG_ERR, cf, 0, __VA_ARGS__)
#define ndk_conf_log_warning(cf,...)                ngx_conf_log_error (NGX_LOG_WARN, cf, 0, __VA_ARGS__)
#define ndk_conf_log_notice(cf,...)                 ngx_conf_log_error (NGX_LOG_NOTICE, cf, 0, __VA_ARGS__)
#define ndk_conf_log_info(cf,...)                   ngx_conf_log_error (NGX_LOG_INFO, cf, 0, __VA_ARGS__)

#define ndk_request_log_stderr(r,...)               ndk_log_stderr (ndk_request_to_log(r), __VA_ARGS__)
#define ndk_request_log_emerg(r,...)                ndk_log_emerg (ndk_request_to_log(r), __VA_ARGS__)
#define ndk_request_log_alert(r,...)                ndk_log_alert (ndk_request_to_log(r), __VA_ARGS__)
#define ndk_request_log_crit(r,...)                 ndk_log_crit (ndk_request_to_log(r), __VA_ARGS__)
#define ndk_request_log_err(r,...)                  ndk_log_err (ndk_request_to_log(r), __VA_ARGS__)
#define ndk_request_log_warning(r,...)              ndk_log_warning (ndk_request_to_log(r), __VA_ARGS__)
#define ndk_request_log_notice(r,...)               ndk_log_notice (ndk_request_to_log(r), __VA_ARGS__)
#define ndk_request_log_info(r,...)                 ndk_log_info (ndk_request_to_log(r), __VA_ARGS__)


#if (NGX_DEBUG)

#define ndk_log_debug_core(log,...)                 ngx_log_debug (NGX_LOG_DEBUG_CORE, log, 0, __VA_ARGS__)
#define ndk_log_debug_alloc(log,...)                ngx_log_debug (NGX_LOG_DEBUG_ALLOC, log, 0, __VA_ARGS__)
#define ndk_log_debug_mutex(log,...)                ngx_log_debug (NGX_LOG_DEBUG_MUTEX, log, 0, __VA_ARGS__)
#define ndk_log_debug_event(log,...)                ngx_log_debug (NGX_LOG_DEBUG_EVENT, log, 0, __VA_ARGS__)
#define ndk_log_debug_http(log,...)                 ngx_log_debug (NGX_LOG_DEBUG_HTTP, log, 0, __VA_ARGS__)
#define ndk_log_debug_mail(log,...)                 ngx_log_debug (NGX_LOG_DEBUG_MAIL, log, 0, __VA_ARGS__)
#define ndk_log_debug_mysql(log,...)                ngx_log_debug (NGX_LOG_DEBUG_MYSQL, log, 0, __VA_ARGS__)

#define ndk_conf_log_debug_core(r,...)              ndk_log_debug_core (ndk_conf_to_log(r), __VA_ARGS__)
#define ndk_conf_log_debug_alloc(r,...)             ndk_log_debug_alloc (ndk_conf_to_log(r), __VA_ARGS__)
#define ndk_conf_log_debug_mutex(r,...)             ndk_log_debug_mutex (ndk_conf_to_log(r), __VA_ARGS__)
#define ndk_conf_log_debug_event(r,...)             ndk_log_debug_event (ndk_conf_to_log(r), __VA_ARGS__)
#define ndk_conf_log_debug_http(r,...)              ndk_log_debug_http (ndk_conf_to_log(r), __VA_ARGS__)
#define ndk_conf_log_debug_mail(r,...)              ndk_log_debug_mail (ndk_conf_to_log(r), __VA_ARGS__)
#define ndk_conf_log_debug_mysql(r,...)             ndk_log_debug_mysql (ndk_conf_to_log(r), __VA_ARGS__)

#define ndk_request_log_debug_core(r,...)           ndk_log_debug_core (ndk_request_to_log(r), __VA_ARGS__)
#define ndk_request_log_debug_alloc(r,...)          ndk_log_debug_alloc (ndk_request_to_log(r), __VA_ARGS__)
#define ndk_request_log_debug_mutex(r,...)          ndk_log_debug_mutex (ndk_request_to_log(r), __VA_ARGS__)
#define ndk_request_log_debug_event(r,...)          ndk_log_debug_event (ndk_request_to_log(r), __VA_ARGS__)
#define ndk_request_log_debug_http(r,...)           ndk_log_debug_http (ndk_request_to_log(r), __VA_ARGS__)
#define ndk_request_log_debug_mail(r,...)           ndk_log_debug_mail (ndk_request_to_log(r), __VA_ARGS__)
#define ndk_request_log_debug_mysql(r,...)          ndk_log_debug_mysql (ndk_request_to_log(r), __VA_ARGS__)

#else 

#define ndk_log_debug_core(log,...)
#define ndk_log_debug_alloc(log,...)
#define ndk_log_debug_mutex(log,...)
#define ndk_log_debug_event(log,...)
#define ndk_log_debug_http(log,...)
#define ndk_log_debug_mail(log,...)
#define ndk_log_debug_mysql(log,...)

#define ndk_conf_log_debug_core(r,...)
#define ndk_conf_log_debug_alloc(r,...)
#define ndk_conf_log_debug_mutex(r,...)
#define ndk_conf_log_debug_event(r,...)
#define ndk_conf_log_debug_http(r,...)
#define ndk_conf_log_debug_mail(r,...)
#define ndk_conf_log_debug_mysql(r,...)

#define ndk_request_log_debug_core(r,...)
#define ndk_request_log_debug_alloc(r,...)
#define ndk_request_log_debug_mutex(r,...)
#define ndk_request_log_debug_event(r,...)
#define ndk_request_log_debug_http(r,...)
#define ndk_request_log_debug_mail(r,...)
#define ndk_request_log_debug_mysql(r,...)

#endif


/*********************************/

#elif (NGX_HAVE_GCC_VARIADIC_MACROS)

#define ndk_log_stderr(log,args...)                 ngx_log_error (NGX_LOG_STDERR, log, 0, args)
#define ndk_log_emerg(log,args...)                  ngx_log_error (NGX_LOG_EMERG, log, 0, args)
#define ndk_log_alert(log,args...)                  ngx_log_error (NGX_LOG_ALERT, log, 0, args)
#define ndk_log_crit(log,args...)                   ngx_log_error (NGX_LOG_CRIT, log, 0, args)
#define ndk_log_err(log,args...)                    ngx_log_error (NGX_LOG_ERR, log, 0, args)
#define ndk_log_warning(log,args...)                ngx_log_error (NGX_LOG_WARN, log, 0, args)
#define ndk_log_notice(log,args...)                 ngx_log_error (NGX_LOG_NOTICE, log, 0, args)
#define ndk_log_info(log,args...)                   ngx_log_error (NGX_LOG_INFO, log, 0, args)

#define ndk_log_debug_core(log,args...)             ngx_log_debug (NGX_LOG_DEBUG_CORE, log, 0, args)
#define ndk_log_debug_alloc(log,args...)            ngx_log_debug (NGX_LOG_DEBUG_ALLOC, log, 0, args)
#define ndk_log_debug_mutex(log,args...)            ngx_log_debug (NGX_LOG_DEBUG_MUTEX, log, 0, args)
#define ndk_log_debug_event(log,args...)            ngx_log_debug (NGX_LOG_DEBUG_EVENT, log, 0, args)
#define ndk_log_debug_http(log,args...)             ngx_log_debug (NGX_LOG_DEBUG_HTTP, log, 0, args)
#define ndk_log_debug_mail(log,args...)             ngx_log_debug (NGX_LOG_DEBUG_MAIL, log, 0, args)
#define ndk_log_debug_mysql(log,args...)            ngx_log_debug (NGX_LOG_DEBUG_MYSQL, log, 0, args)
#define ndk_log_debug_script(log,args...)           ngx_log_debug (NGX_LOG_DEBUG_SCRIPT, log, 0, args)

#define ndk_conf_log_stderr(cf,args...)             ngx_conf_log_error (NGX_LOG_STDERR, cf, 0, args)
#define ndk_conf_log_emerg(cf,args...)              ngx_conf_log_error (NGX_LOG_EMERG, cf, 0, args)
#define ndk_conf_log_alert(cf,args...)              ngx_conf_log_error (NGX_LOG_ALERT, cf, 0, args)
#define ndk_conf_log_crit(cf,args...)               ngx_conf_log_error (NGX_LOG_CRIT, cf, 0, args)
#define ndk_conf_log_err(cf,args...)                ngx_conf_log_error (NGX_LOG_ERR, cf, 0, args)
#define ndk_conf_log_warning(cf,args...)            ngx_conf_log_error (NGX_LOG_WARN, cf, 0, args)
#define ndk_conf_log_notice(cf,args...)             ngx_conf_log_error (NGX_LOG_NOTICE, cf, 0, args)
#define ndk_conf_log_info(cf,args...)               ngx_conf_log_error (NGX_LOG_INFO, cf, 0, args)

#define ndk_conf_log_debug_core(r,args...)          ndk_log_debug_core (ndk_conf_to_log(r), args)
#define ndk_conf_log_debug_alloc(r,args...)         ndk_log_debug_alloc (ndk_conf_to_log(r), args)
#define ndk_conf_log_debug_mutex(r,args...)         ndk_log_debug_mutex (ndk_conf_to_log(r), args)
#define ndk_conf_log_debug_event(r,args...)         ndk_log_debug_event (ndk_conf_to_log(r), args)
#define ndk_conf_log_debug_http(r,args...)          ndk_log_debug_http (ndk_conf_to_log(r), args)
#define ndk_conf_log_debug_mail(r,args...)          ndk_log_debug_mail (ndk_conf_to_log(r), args)
#define ndk_conf_log_debug_mysql(r,args...)         ndk_log_debug_mysql (ndk_conf_to_log(r), args)
#define ndk_conf_log_debug_script(r,args...)        ndk_log_debug_script (ndk_conf_to_log(r), args)

#define ndk_request_log_stderr(r,args...)           ndk_log_stderr (ndk_request_to_log(r), args)
#define ndk_request_log_emerg(r,args...)            ndk_log_emerg (ndk_request_to_log(r), args)
#define ndk_request_log_alert(r,args...)            ndk_log_alert (ndk_request_to_log(r), args)
#define ndk_request_log_crit(r,args...)             ndk_log_crit (ndk_request_to_log(r), args)
#define ndk_request_log_err(r,args...)              ndk_log_err (ndk_request_to_log(r), args)
#define ndk_request_log_warning(r,args...)          ndk_log_warning (ndk_request_to_log(r), args)
#define ndk_request_log_notice(r,args...)           ndk_log_notice (ndk_request_to_log(r), args)
#define ndk_request_log_info(r,args...)             ndk_log_info (ndk_request_to_log(r), args)

#define ndk_request_log_debug_core(r,args...)       ndk_log_debug_core (ndk_request_to_log(r), args)
#define ndk_request_log_debug_alloc(r,args...)      ndk_log_debug_alloc (ndk_request_to_log(r), args)
#define ndk_request_log_debug_mutex(r,args...)      ndk_log_debug_mutex (ndk_request_to_log(r), args)
#define ndk_request_log_debug_event(r,args...)      ndk_log_debug_event (ndk_request_to_log(r), args)
#define ndk_request_log_debug_http(r,args...)       ndk_log_debug_http (ndk_request_to_log(r), args)
#define ndk_request_log_debug_mail(r,args...)       ndk_log_debug_mail (ndk_request_to_log(r), args)
#define ndk_request_log_debug_mysql(r,args...)      ndk_log_debug_mysql (ndk_request_to_log(r), args)
#define ndk_request_log_debug_script(r,args...)     ndk_log_debug_script (ndk_request_to_log(r), args)

/*********************************/

#else /* NO VARIADIC MACROS */

/* #warning does not work on Windows */
#pragma message("Nginx Devel Kit logging without variadic macros not yet implemented")

#endif /* VARIADIC MACROS */
