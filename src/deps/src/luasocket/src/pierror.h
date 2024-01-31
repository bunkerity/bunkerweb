#ifndef PIERROR_H
#define PIERROR_H
/*=========================================================================*\
* Error messages
* Defines platform independent error messages
\*=========================================================================*/

#define PIE_HOST_NOT_FOUND "host not found"
#define PIE_ADDRINUSE      "address already in use"
#define PIE_ISCONN         "already connected"
#define PIE_ACCESS         "permission denied"
#define PIE_CONNREFUSED    "connection refused"
#define PIE_CONNABORTED    "closed"
#define PIE_CONNRESET      "closed"
#define PIE_TIMEDOUT       "timeout"
#define PIE_AGAIN          "temporary failure in name resolution"
#define PIE_BADFLAGS       "invalid value for ai_flags"
#define PIE_BADHINTS       "invalid value for hints"
#define PIE_FAIL           "non-recoverable failure in name resolution"
#define PIE_FAMILY         "ai_family not supported"
#define PIE_MEMORY         "memory allocation failure"
#define PIE_NONAME         "host or service not provided, or not known"
#define PIE_OVERFLOW       "argument buffer overflow"
#define PIE_PROTOCOL       "resolved protocol is unknown"
#define PIE_SERVICE        "service not supported for socket type"
#define PIE_SOCKTYPE       "ai_socktype not supported"

#endif
