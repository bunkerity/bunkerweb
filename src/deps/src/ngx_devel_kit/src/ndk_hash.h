
#ifndef NDK_HASH_H
#define NDK_HASH_H

#ifdef NDK_HASH_ALL

#ifndef NDK_MD5
#define NDK_MD5
#endif

#ifndef NDK_MURMUR2
#define NDK_MURMUR2
#endif

#ifndef NDK_SHA1
#define NDK_SHA1
#endif

#endif

#include <ngx_config.h>
#include <ngx_core.h>
typedef void (*ndk_hash_pt) (u_char *p, char *data, size_t len);


#ifdef NDK_MD5
#include <ngx_md5.h>
void    ndk_md5_hash            (u_char *p, char *data, size_t len);
void    ndk_md5_hash_upper      (u_char *p, char *data, size_t len);
#endif

#ifdef NDK_MURMUR2
#define MURMURHASH2_DIGEST_LENGTH   4
void    ndk_murmur2_hash        (u_char *p, char *data, size_t len);
void    ndk_murmur2_hash_upper  (u_char *p, char *data, size_t len);
#endif

#ifdef NDK_SHA1
#include <ngx_sha1.h>
void    ndk_sha1_hash           (u_char *p, char *data, size_t len);
void    ndk_sha1_hash_upper     (u_char *p, char *data, size_t len);
#endif

#endif /* NDK_HASH_H */

