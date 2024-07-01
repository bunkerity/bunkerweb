
#include <ndk_hash.h>



/* openssl hashes */

#define     NDK_OPENSSL_HASH(type,ctxt_type,upper)                  \
    u_char              md [ctxt_type ## _DIGEST_LENGTH];           \
    ctxt_type ##_CTX    c;                                          \
                                                                    \
    type ## _Init (&c);                                             \
    type ## _Update (&c, data, len);                                \
    type ## _Final (md, &c);                                        \
                                                                    \
    ndk_hex_dump (p, (u_char *) md, ctxt_type ## _DIGEST_LENGTH);   \
    if (upper) {                                                    \
        ndk_strtoupper (p, (ctxt_type ## _DIGEST_LENGTH) *2);       \
    }


#ifdef NDK_MD5

void
ndk_md5_hash (u_char *p, char *data, size_t len)
{
    NDK_OPENSSL_HASH (MD5, MD5, 0);
}

void
ndk_md5_hash_upper (u_char *p, char *data, size_t len)
{
    NDK_OPENSSL_HASH (MD5, MD5, 1);
}

#endif
#ifdef NDK_SHA1

void
ndk_sha1_hash (u_char *p, char *data, size_t len)
{
    NDK_OPENSSL_HASH (SHA1, SHA, 0);
}

void
ndk_sha1_hash_upper (u_char *p, char *data, size_t len)
{
    NDK_OPENSSL_HASH (SHA1, SHA, 1);
}

#endif



/* non-openssl hashes */

#ifdef NDK_MURMUR2

#include    "hash/murmurhash2.c"

void
ndk_murmur2_hash (u_char *p, char *data, size_t len)
{
    uint32_t    hash;

    hash = MurmurHash2 (data, len, 47);

    ndk_hex_dump (p, (u_char*) &hash, 4);
}

void
ndk_murmur2_hash_upper (u_char *p, char *data, size_t len)
{
    uint32_t    hash;

    hash = MurmurHash2 (data, len, 47);

    ndk_hex_dump (p, (u_char*) &hash, 4);
    ndk_strtoupper (p, 8);
}

#endif
