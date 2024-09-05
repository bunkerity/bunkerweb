# components-configuration-crypto.sh
#
# Copyright The Mbed TLS Contributors
# SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later

# This file contains test components that are executed by all.sh

################################################################
#### Configuration Testing - Crypto
################################################################

component_test_psa_crypto_key_id_encodes_owner () {
    msg "build: full config + PSA_CRYPTO_KEY_ID_ENCODES_OWNER, cmake, gcc, ASan"
    scripts/config.py full
    scripts/config.py set MBEDTLS_PSA_CRYPTO_KEY_ID_ENCODES_OWNER
    CC=gcc cmake -D CMAKE_BUILD_TYPE:String=Asan .
    make

    msg "test: full config - USE_PSA_CRYPTO + PSA_CRYPTO_KEY_ID_ENCODES_OWNER, cmake, gcc, ASan"
    make test
}

component_test_psa_assume_exclusive_buffers () {
    msg "build: full config + MBEDTLS_PSA_ASSUME_EXCLUSIVE_BUFFERS, cmake, gcc, ASan"
    scripts/config.py full
    scripts/config.py set MBEDTLS_PSA_ASSUME_EXCLUSIVE_BUFFERS
    CC=gcc cmake -D CMAKE_BUILD_TYPE:String=Asan .
    make

    msg "test: full config + MBEDTLS_PSA_ASSUME_EXCLUSIVE_BUFFERS, cmake, gcc, ASan"
    make test
}

# check_renamed_symbols HEADER LIB
# Check that if HEADER contains '#define MACRO ...' then MACRO is not a symbol
# name in LIB.
check_renamed_symbols () {
    ! nm "$2" | sed 's/.* //' |
      grep -x -F "$(sed -n 's/^ *# *define  *\([A-Z_a-z][0-9A-Z_a-z]*\)..*/\1/p' "$1")"
}

component_build_psa_crypto_spm () {
    msg "build: full config + PSA_CRYPTO_KEY_ID_ENCODES_OWNER + PSA_CRYPTO_SPM, make, gcc"
    scripts/config.py full
    scripts/config.py unset MBEDTLS_PSA_CRYPTO_BUILTIN_KEYS
    scripts/config.py set MBEDTLS_PSA_CRYPTO_KEY_ID_ENCODES_OWNER
    scripts/config.py set MBEDTLS_PSA_CRYPTO_SPM
    # We can only compile, not link, since our test and sample programs
    # aren't equipped for the modified names used when MBEDTLS_PSA_CRYPTO_SPM
    # is active.
    make CC=gcc CFLAGS='-Werror -Wall -Wextra -I../tests/include/spe' lib

    # Check that if a symbol is renamed by crypto_spe.h, the non-renamed
    # version is not present.
    echo "Checking for renamed symbols in the library"
    check_renamed_symbols tests/include/spe/crypto_spe.h library/libmbedcrypto.a
}

# Get a list of library-wise undefined symbols and ensure that they only
# belong to psa_xxx() functions and not to mbedtls_yyy() ones.
# This function is a common helper used by both:
# - component_test_default_psa_crypto_client_without_crypto_provider
# - component_build_full_psa_crypto_client_without_crypto_provider.
common_check_mbedtls_missing_symbols () {
    nm library/libmbedcrypto.a | grep ' [TRrDC] ' | grep -Eo '(mbedtls_|psa_).*' | sort -u > sym_def.txt
    nm library/libmbedcrypto.a | grep ' U ' | grep -Eo '(mbedtls_|psa_).*' | sort -u > sym_undef.txt
    comm sym_def.txt sym_undef.txt -13 > linking_errors.txt
    not grep mbedtls_ linking_errors.txt

    rm sym_def.txt sym_undef.txt linking_errors.txt
}

component_test_default_psa_crypto_client_without_crypto_provider () {
    msg "build: default config - PSA_CRYPTO_C + PSA_CRYPTO_CLIENT"

    scripts/config.py unset MBEDTLS_PSA_CRYPTO_C
    scripts/config.py unset MBEDTLS_PSA_CRYPTO_STORAGE_C
    scripts/config.py unset MBEDTLS_PSA_ITS_FILE_C
    scripts/config.py unset MBEDTLS_SSL_PROTO_TLS1_3
    scripts/config.py set MBEDTLS_PSA_CRYPTO_CLIENT
    scripts/config.py unset MBEDTLS_LMS_C

    make

    msg "check missing symbols: default config - PSA_CRYPTO_C + PSA_CRYPTO_CLIENT"
    common_check_mbedtls_missing_symbols

    msg "test: default config - PSA_CRYPTO_C + PSA_CRYPTO_CLIENT"
    make test
}

component_build_full_psa_crypto_client_without_crypto_provider () {
    msg "build: full config - PSA_CRYPTO_C"

    # Use full config which includes USE_PSA and CRYPTO_CLIENT.
    scripts/config.py full

    scripts/config.py unset MBEDTLS_PSA_CRYPTO_C
    scripts/config.py unset MBEDTLS_PSA_CRYPTO_STORAGE_C
    # Dynamic secure element support is a deprecated feature and it is not
    # available when CRYPTO_C and PSA_CRYPTO_STORAGE_C are disabled.
    scripts/config.py unset MBEDTLS_PSA_CRYPTO_SE_C

    # Since there is no crypto provider in this build it is not possible to
    # build all the test executables and progrems due to missing PSA functions
    # at link time. Therefore we will just build libraries and we'll check
    # that symbols of interest are there.
    make lib

    msg "check missing symbols: full config - PSA_CRYPTO_C"

    common_check_mbedtls_missing_symbols

    # Ensure that desired functions are included into the build (extend the
    # following list as required).
    grep mbedtls_pk_get_psa_attributes library/libmbedcrypto.a
    grep mbedtls_pk_import_into_psa library/libmbedcrypto.a
    grep mbedtls_pk_copy_from_psa library/libmbedcrypto.a
}

component_test_psa_crypto_rsa_no_genprime () {
    msg "build: default config minus MBEDTLS_GENPRIME"
    scripts/config.py unset MBEDTLS_GENPRIME
    make

    msg "test: default config minus MBEDTLS_GENPRIME"
    make test
}

component_test_no_pem_no_fs () {
    msg "build: Default + !MBEDTLS_PEM_PARSE_C + !MBEDTLS_FS_IO (ASan build)"
    scripts/config.py unset MBEDTLS_PEM_PARSE_C
    scripts/config.py unset MBEDTLS_FS_IO
    scripts/config.py unset MBEDTLS_PSA_ITS_FILE_C # requires a filesystem
    scripts/config.py unset MBEDTLS_PSA_CRYPTO_STORAGE_C # requires PSA ITS
    CC=$ASAN_CC cmake -D CMAKE_BUILD_TYPE:String=Asan .
    make

    msg "test: !MBEDTLS_PEM_PARSE_C !MBEDTLS_FS_IO - main suites (inc. selftests) (ASan build)" # ~ 50s
    make test

    msg "test: !MBEDTLS_PEM_PARSE_C !MBEDTLS_FS_IO - ssl-opt.sh (ASan build)" # ~ 6 min
    tests/ssl-opt.sh
}

component_test_rsa_no_crt () {
    msg "build: Default + RSA_NO_CRT (ASan build)" # ~ 6 min
    scripts/config.py set MBEDTLS_RSA_NO_CRT
    CC=$ASAN_CC cmake -D CMAKE_BUILD_TYPE:String=Asan .
    make

    msg "test: RSA_NO_CRT - main suites (inc. selftests) (ASan build)" # ~ 50s
    make test

    msg "test: RSA_NO_CRT - RSA-related part of ssl-opt.sh (ASan build)" # ~ 5s
    tests/ssl-opt.sh -f RSA

    msg "test: RSA_NO_CRT - RSA-related part of compat.sh (ASan build)" # ~ 3 min
    tests/compat.sh -t RSA

    msg "test: RSA_NO_CRT - RSA-related part of context-info.sh (ASan build)" # ~ 15 sec
    tests/context-info.sh
}

component_test_no_ctr_drbg_classic () {
    msg "build: Full minus CTR_DRBG, classic crypto in TLS"
    scripts/config.py full
    scripts/config.py unset MBEDTLS_CTR_DRBG_C
    scripts/config.py unset MBEDTLS_USE_PSA_CRYPTO
    scripts/config.py unset MBEDTLS_SSL_PROTO_TLS1_3

    CC=$ASAN_CC cmake -D CMAKE_BUILD_TYPE:String=Asan .
    make

    msg "test: Full minus CTR_DRBG, classic crypto - main suites"
    make test

    # In this configuration, the TLS test programs use HMAC_DRBG.
    # The SSL tests are slow, so run a small subset, just enough to get
    # confidence that the SSL code copes with HMAC_DRBG.
    msg "test: Full minus CTR_DRBG, classic crypto - ssl-opt.sh (subset)"
    tests/ssl-opt.sh -f 'Default\|SSL async private.*delay=\|tickets enabled on server'

    msg "test: Full minus CTR_DRBG, classic crypto - compat.sh (subset)"
    tests/compat.sh -m tls12 -t 'ECDSA PSK' -V NO -p OpenSSL
}

component_test_no_ctr_drbg_use_psa () {
    msg "build: Full minus CTR_DRBG, PSA crypto in TLS"
    scripts/config.py full
    scripts/config.py unset MBEDTLS_CTR_DRBG_C
    scripts/config.py set MBEDTLS_USE_PSA_CRYPTO

    CC=$ASAN_CC cmake -D CMAKE_BUILD_TYPE:String=Asan .
    make

    msg "test: Full minus CTR_DRBG, USE_PSA_CRYPTO - main suites"
    make test

    # In this configuration, the TLS test programs use HMAC_DRBG.
    # The SSL tests are slow, so run a small subset, just enough to get
    # confidence that the SSL code copes with HMAC_DRBG.
    msg "test: Full minus CTR_DRBG, USE_PSA_CRYPTO - ssl-opt.sh (subset)"
    tests/ssl-opt.sh -f 'Default\|SSL async private.*delay=\|tickets enabled on server'

    msg "test: Full minus CTR_DRBG, USE_PSA_CRYPTO - compat.sh (subset)"
    tests/compat.sh -m tls12 -t 'ECDSA PSK' -V NO -p OpenSSL
}

component_test_no_hmac_drbg_classic () {
    msg "build: Full minus HMAC_DRBG, classic crypto in TLS"
    scripts/config.py full
    scripts/config.py unset MBEDTLS_HMAC_DRBG_C
    scripts/config.py unset MBEDTLS_ECDSA_DETERMINISTIC # requires HMAC_DRBG
    scripts/config.py unset MBEDTLS_USE_PSA_CRYPTO
    scripts/config.py unset MBEDTLS_SSL_PROTO_TLS1_3

    CC=$ASAN_CC cmake -D CMAKE_BUILD_TYPE:String=Asan .
    make

    msg "test: Full minus HMAC_DRBG, classic crypto - main suites"
    make test

    # Normally our ECDSA implementation uses deterministic ECDSA. But since
    # HMAC_DRBG is disabled in this configuration, randomized ECDSA is used
    # instead.
    # Test SSL with non-deterministic ECDSA. Only test features that
    # might be affected by how ECDSA signature is performed.
    msg "test: Full minus HMAC_DRBG, classic crypto - ssl-opt.sh (subset)"
    tests/ssl-opt.sh -f 'Default\|SSL async private: sign'

    # To save time, only test one protocol version, since this part of
    # the protocol is identical in (D)TLS up to 1.2.
    msg "test: Full minus HMAC_DRBG, classic crypto - compat.sh (ECDSA)"
    tests/compat.sh -m tls12 -t 'ECDSA'
}

component_test_no_hmac_drbg_use_psa () {
    msg "build: Full minus HMAC_DRBG, PSA crypto in TLS"
    scripts/config.py full
    scripts/config.py unset MBEDTLS_HMAC_DRBG_C
    scripts/config.py unset MBEDTLS_ECDSA_DETERMINISTIC # requires HMAC_DRBG
    scripts/config.py set MBEDTLS_USE_PSA_CRYPTO

    CC=$ASAN_CC cmake -D CMAKE_BUILD_TYPE:String=Asan .
    make

    msg "test: Full minus HMAC_DRBG, USE_PSA_CRYPTO - main suites"
    make test

    # Normally our ECDSA implementation uses deterministic ECDSA. But since
    # HMAC_DRBG is disabled in this configuration, randomized ECDSA is used
    # instead.
    # Test SSL with non-deterministic ECDSA. Only test features that
    # might be affected by how ECDSA signature is performed.
    msg "test: Full minus HMAC_DRBG, USE_PSA_CRYPTO - ssl-opt.sh (subset)"
    tests/ssl-opt.sh -f 'Default\|SSL async private: sign'

    # To save time, only test one protocol version, since this part of
    # the protocol is identical in (D)TLS up to 1.2.
    msg "test: Full minus HMAC_DRBG, USE_PSA_CRYPTO - compat.sh (ECDSA)"
    tests/compat.sh -m tls12 -t 'ECDSA'
}

component_test_psa_external_rng_no_drbg_classic () {
    msg "build: PSA_CRYPTO_EXTERNAL_RNG minus *_DRBG, classic crypto in TLS"
    scripts/config.py full
    scripts/config.py unset MBEDTLS_USE_PSA_CRYPTO
    scripts/config.py unset MBEDTLS_SSL_PROTO_TLS1_3
    scripts/config.py set MBEDTLS_PSA_CRYPTO_EXTERNAL_RNG
    scripts/config.py unset MBEDTLS_ENTROPY_C
    scripts/config.py unset MBEDTLS_ENTROPY_NV_SEED
    scripts/config.py unset MBEDTLS_PLATFORM_NV_SEED_ALT
    scripts/config.py unset MBEDTLS_CTR_DRBG_C
    scripts/config.py unset MBEDTLS_HMAC_DRBG_C
    scripts/config.py unset MBEDTLS_ECDSA_DETERMINISTIC # requires HMAC_DRBG
    # When MBEDTLS_USE_PSA_CRYPTO is disabled and there is no DRBG,
    # the SSL test programs don't have an RNG and can't work. Explicitly
    # make them use the PSA RNG with -DMBEDTLS_TEST_USE_PSA_CRYPTO_RNG.
    make CC=$ASAN_CC CFLAGS="$ASAN_CFLAGS -DMBEDTLS_TEST_USE_PSA_CRYPTO_RNG" LDFLAGS="$ASAN_CFLAGS"

    msg "test: PSA_CRYPTO_EXTERNAL_RNG minus *_DRBG, classic crypto - main suites"
    make test

    msg "test: PSA_CRYPTO_EXTERNAL_RNG minus *_DRBG, classic crypto - ssl-opt.sh (subset)"
    tests/ssl-opt.sh -f 'Default'
}

component_test_psa_external_rng_no_drbg_use_psa () {
    msg "build: PSA_CRYPTO_EXTERNAL_RNG minus *_DRBG, PSA crypto in TLS"
    scripts/config.py full
    scripts/config.py set MBEDTLS_PSA_CRYPTO_EXTERNAL_RNG
    scripts/config.py unset MBEDTLS_ENTROPY_C
    scripts/config.py unset MBEDTLS_ENTROPY_NV_SEED
    scripts/config.py unset MBEDTLS_PLATFORM_NV_SEED_ALT
    scripts/config.py unset MBEDTLS_CTR_DRBG_C
    scripts/config.py unset MBEDTLS_HMAC_DRBG_C
    scripts/config.py unset MBEDTLS_ECDSA_DETERMINISTIC # requires HMAC_DRBG
    make CC=$ASAN_CC CFLAGS="$ASAN_CFLAGS" LDFLAGS="$ASAN_CFLAGS"

    msg "test: PSA_CRYPTO_EXTERNAL_RNG minus *_DRBG, PSA crypto - main suites"
    make test

    msg "test: PSA_CRYPTO_EXTERNAL_RNG minus *_DRBG, PSA crypto - ssl-opt.sh (subset)"
    tests/ssl-opt.sh -f 'Default\|opaque'
}

component_test_psa_external_rng_use_psa_crypto () {
    msg "build: full + PSA_CRYPTO_EXTERNAL_RNG + USE_PSA_CRYPTO minus CTR_DRBG"
    scripts/config.py full
    scripts/config.py set MBEDTLS_PSA_CRYPTO_EXTERNAL_RNG
    scripts/config.py set MBEDTLS_USE_PSA_CRYPTO
    scripts/config.py unset MBEDTLS_CTR_DRBG_C
    make CC=$ASAN_CC CFLAGS="$ASAN_CFLAGS" LDFLAGS="$ASAN_CFLAGS"

    msg "test: full + PSA_CRYPTO_EXTERNAL_RNG + USE_PSA_CRYPTO minus CTR_DRBG"
    make test

    msg "test: full + PSA_CRYPTO_EXTERNAL_RNG + USE_PSA_CRYPTO minus CTR_DRBG"
    tests/ssl-opt.sh -f 'Default\|opaque'
}

component_test_psa_inject_entropy () {
    msg "build: full + MBEDTLS_PSA_INJECT_ENTROPY"
    scripts/config.py full
    scripts/config.py set MBEDTLS_PSA_INJECT_ENTROPY
    scripts/config.py set MBEDTLS_ENTROPY_NV_SEED
    scripts/config.py set MBEDTLS_NO_DEFAULT_ENTROPY_SOURCES
    scripts/config.py unset MBEDTLS_PLATFORM_NV_SEED_ALT
    scripts/config.py unset MBEDTLS_PLATFORM_STD_NV_SEED_READ
    scripts/config.py unset MBEDTLS_PLATFORM_STD_NV_SEED_WRITE
    make CC=$ASAN_CC CFLAGS="$ASAN_CFLAGS '-DMBEDTLS_USER_CONFIG_FILE=\"../tests/configs/user-config-for-test.h\"'" LDFLAGS="$ASAN_CFLAGS"

    msg "test: full + MBEDTLS_PSA_INJECT_ENTROPY"
    make test
}

component_full_no_pkparse_pkwrite () {
    msg "build: full without pkparse and pkwrite"

    scripts/config.py crypto_full
    scripts/config.py unset MBEDTLS_PK_PARSE_C
    scripts/config.py unset MBEDTLS_PK_WRITE_C

    make CFLAGS="$ASAN_CFLAGS" LDFLAGS="$ASAN_CFLAGS"

    # Ensure that PK_[PARSE|WRITE]_C were not re-enabled accidentally (additive config).
    not grep mbedtls_pk_parse_key library/pkparse.o
    not grep mbedtls_pk_write_key_der library/pkwrite.o

    msg "test: full without pkparse and pkwrite"
    make test
}

component_test_crypto_full_md_light_only () {
    msg "build: crypto_full with only the light subset of MD"
    scripts/config.py crypto_full
    scripts/config.py unset MBEDTLS_PSA_CRYPTO_CONFIG
    # Disable MD
    scripts/config.py unset MBEDTLS_MD_C
    # Disable direct dependencies of MD_C
    scripts/config.py unset MBEDTLS_HKDF_C
    scripts/config.py unset MBEDTLS_HMAC_DRBG_C
    scripts/config.py unset MBEDTLS_PKCS7_C
    # Disable indirect dependencies of MD_C
    scripts/config.py unset MBEDTLS_ECDSA_DETERMINISTIC # needs HMAC_DRBG
    # Disable things that would auto-enable MD_C
    scripts/config.py unset MBEDTLS_PKCS5_C

    # Note: MD-light is auto-enabled in build_info.h by modules that need it,
    # which we haven't disabled, so no need to explicitly enable it.
    make CC=$ASAN_CC CFLAGS="$ASAN_CFLAGS" LDFLAGS="$ASAN_CFLAGS"

    # Make sure we don't have the HMAC functions, but the hashing functions
    not grep mbedtls_md_hmac library/md.o
    grep mbedtls_md library/md.o

    msg "test: crypto_full with only the light subset of MD"
    make test
}

component_test_full_no_cipher_no_psa_crypto () {
    msg "build: full no CIPHER no PSA_CRYPTO_C"
    scripts/config.py full
    scripts/config.py unset MBEDTLS_CIPHER_C
    # Don't pull in cipher via PSA mechanisms
    # (currently ignored anyway because we completely disable PSA)
    scripts/config.py unset MBEDTLS_PSA_CRYPTO_CONFIG
    # Disable features that depend on CIPHER_C
    scripts/config.py unset MBEDTLS_CMAC_C
    scripts/config.py unset MBEDTLS_NIST_KW_C
    scripts/config.py unset MBEDTLS_PSA_CRYPTO_C
    scripts/config.py unset MBEDTLS_PSA_CRYPTO_CLIENT
    scripts/config.py unset MBEDTLS_SSL_TLS_C
    scripts/config.py unset MBEDTLS_SSL_TICKET_C
    # Disable features that depend on PSA_CRYPTO_C
    scripts/config.py unset MBEDTLS_PSA_CRYPTO_SE_C
    scripts/config.py unset MBEDTLS_PSA_CRYPTO_STORAGE_C
    scripts/config.py unset MBEDTLS_USE_PSA_CRYPTO
    scripts/config.py unset MBEDTLS_LMS_C
    scripts/config.py unset MBEDTLS_LMS_PRIVATE

    msg "test: full no CIPHER no PSA_CRYPTO_C"
    make test
}

# This is a common configurator and test function that is used in:
# - component_test_full_no_cipher_with_psa_crypto
# - component_test_full_no_cipher_with_psa_crypto_config
# It accepts 2 input parameters:
# - $1: boolean value which basically reflects status of MBEDTLS_PSA_CRYPTO_CONFIG
# - $2: a text string which describes the test component
common_test_full_no_cipher_with_psa_crypto () {
    USE_CRYPTO_CONFIG="$1"
    COMPONENT_DESCRIPTION="$2"

    msg "build: $COMPONENT_DESCRIPTION"

    scripts/config.py full
    scripts/config.py unset MBEDTLS_CIPHER_C

    if [ "$USE_CRYPTO_CONFIG" -eq 1 ]; then
        # The built-in implementation of the following algs/key-types depends
        # on CIPHER_C so we disable them.
        # This does not hold for KEY_TYPE_CHACHA20 and ALG_CHACHA20_POLY1305
        # so we keep them enabled.
        scripts/config.py -f $CRYPTO_CONFIG_H unset PSA_WANT_ALG_CCM_STAR_NO_TAG
        scripts/config.py -f $CRYPTO_CONFIG_H unset PSA_WANT_ALG_CMAC
        scripts/config.py -f $CRYPTO_CONFIG_H unset PSA_WANT_ALG_CBC_NO_PADDING
        scripts/config.py -f $CRYPTO_CONFIG_H unset PSA_WANT_ALG_CBC_PKCS7
        scripts/config.py -f $CRYPTO_CONFIG_H unset PSA_WANT_ALG_CFB
        scripts/config.py -f $CRYPTO_CONFIG_H unset PSA_WANT_ALG_CTR
        scripts/config.py -f $CRYPTO_CONFIG_H unset PSA_WANT_ALG_ECB_NO_PADDING
        scripts/config.py -f $CRYPTO_CONFIG_H unset PSA_WANT_ALG_OFB
        scripts/config.py -f $CRYPTO_CONFIG_H unset PSA_WANT_ALG_PBKDF2_AES_CMAC_PRF_128
        scripts/config.py -f $CRYPTO_CONFIG_H unset PSA_WANT_ALG_STREAM_CIPHER
        scripts/config.py -f $CRYPTO_CONFIG_H unset PSA_WANT_KEY_TYPE_DES
    else
        # Don't pull in cipher via PSA mechanisms
        scripts/config.py unset MBEDTLS_PSA_CRYPTO_CONFIG
        # Disable cipher modes/keys that make PSA depend on CIPHER_C.
        # Keep CHACHA20 and CHACHAPOLY enabled since they do not depend on CIPHER_C.
        scripts/config.py unset-all MBEDTLS_CIPHER_MODE
    fi
    # The following modules directly depends on CIPHER_C
    scripts/config.py unset MBEDTLS_CMAC_C
    scripts/config.py unset MBEDTLS_NIST_KW_C

    make

    # Ensure that CIPHER_C was not re-enabled
    not grep mbedtls_cipher_init library/cipher.o

    msg "test: $COMPONENT_DESCRIPTION"
    make test
}

component_test_full_no_cipher_with_psa_crypto () {
    common_test_full_no_cipher_with_psa_crypto 0 "full no CIPHER no CRYPTO_CONFIG"
}

component_test_full_no_cipher_with_psa_crypto_config () {
    common_test_full_no_cipher_with_psa_crypto 1 "full no CIPHER"
}

component_test_full_no_ccm () {
    msg "build: full no PSA_WANT_ALG_CCM"

    # Full config enables:
    # - USE_PSA_CRYPTO so that TLS code dispatches cipher/AEAD to PSA
    # - CRYPTO_CONFIG so that PSA_WANT config symbols are evaluated
    scripts/config.py full

    # Disable PSA_WANT_ALG_CCM so that CCM is not supported in PSA. CCM_C is still
    # enabled, but not used from TLS since USE_PSA is set.
    # This is helpful to ensure that TLS tests below have proper dependencies.
    #
    # Note: also PSA_WANT_ALG_CCM_STAR_NO_TAG is enabled, but it does not cause
    # PSA_WANT_ALG_CCM to be re-enabled.
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_CCM

    make

    msg "test: full no PSA_WANT_ALG_CCM"
    make test
}

component_test_full_no_ccm_star_no_tag () {
    msg "build: full no PSA_WANT_ALG_CCM_STAR_NO_TAG"

    # Full config enables CRYPTO_CONFIG so that PSA_WANT config symbols are evaluated
    scripts/config.py full

    # Disable CCM_STAR_NO_TAG, which is the target of this test, as well as all
    # other components that enable MBEDTLS_PSA_BUILTIN_CIPHER internal symbol.
    # This basically disables all unauthenticated ciphers on the PSA side, while
    # keeping AEADs enabled.
    #
    # Note: PSA_WANT_ALG_CCM is enabled, but it does not cause
    # PSA_WANT_ALG_CCM_STAR_NO_TAG to be re-enabled.
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_CCM_STAR_NO_TAG
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_STREAM_CIPHER
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_CTR
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_CFB
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_OFB
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_ECB_NO_PADDING
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_CBC_NO_PADDING
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_CBC_PKCS7

    make

    # Ensure MBEDTLS_PSA_BUILTIN_CIPHER was not enabled
    not grep mbedtls_psa_cipher library/psa_crypto_cipher.o

    msg "test: full no PSA_WANT_ALG_CCM_STAR_NO_TAG"
    make test
}

component_test_full_no_bignum () {
    msg "build: full minus bignum"
    scripts/config.py full
    scripts/config.py unset MBEDTLS_BIGNUM_C
    # Direct dependencies of bignum
    scripts/config.py unset MBEDTLS_ECP_C
    scripts/config.py unset MBEDTLS_RSA_C
    scripts/config.py unset MBEDTLS_DHM_C
    # Direct dependencies of ECP
    scripts/config.py unset MBEDTLS_ECDH_C
    scripts/config.py unset MBEDTLS_ECDSA_C
    scripts/config.py unset MBEDTLS_ECJPAKE_C
    scripts/config.py unset MBEDTLS_ECP_RESTARTABLE
    # Disable what auto-enables ECP_LIGHT
    scripts/config.py unset MBEDTLS_PK_PARSE_EC_EXTENDED
    scripts/config.py unset MBEDTLS_PK_PARSE_EC_COMPRESSED
    # Indirect dependencies of ECP
    scripts/config.py unset MBEDTLS_KEY_EXCHANGE_ECDH_ECDSA_ENABLED
    scripts/config.py unset MBEDTLS_KEY_EXCHANGE_ECDH_RSA_ENABLED
    scripts/config.py unset MBEDTLS_KEY_EXCHANGE_ECDHE_PSK_ENABLED
    scripts/config.py unset MBEDTLS_KEY_EXCHANGE_ECDHE_RSA_ENABLED
    scripts/config.py unset MBEDTLS_KEY_EXCHANGE_ECDHE_ECDSA_ENABLED
    scripts/config.py unset MBEDTLS_KEY_EXCHANGE_ECJPAKE_ENABLED
    scripts/config.py unset MBEDTLS_SSL_TLS1_3_KEY_EXCHANGE_MODE_EPHEMERAL_ENABLED
    scripts/config.py unset MBEDTLS_SSL_TLS1_3_KEY_EXCHANGE_MODE_PSK_EPHEMERAL_ENABLED
    # Direct dependencies of DHM
    scripts/config.py unset MBEDTLS_KEY_EXCHANGE_DHE_PSK_ENABLED
    # Direct dependencies of RSA
    scripts/config.py unset MBEDTLS_KEY_EXCHANGE_DHE_RSA_ENABLED
    scripts/config.py unset MBEDTLS_KEY_EXCHANGE_RSA_PSK_ENABLED
    scripts/config.py unset MBEDTLS_KEY_EXCHANGE_RSA_ENABLED
    scripts/config.py unset MBEDTLS_X509_RSASSA_PSS_SUPPORT
    # PK and its dependencies
    scripts/config.py unset MBEDTLS_PK_C
    scripts/config.py unset MBEDTLS_PK_PARSE_C
    scripts/config.py unset MBEDTLS_PK_WRITE_C
    scripts/config.py unset MBEDTLS_X509_USE_C
    scripts/config.py unset MBEDTLS_X509_CRT_PARSE_C
    scripts/config.py unset MBEDTLS_X509_CRL_PARSE_C
    scripts/config.py unset MBEDTLS_X509_CSR_PARSE_C
    scripts/config.py unset MBEDTLS_X509_CREATE_C
    scripts/config.py unset MBEDTLS_X509_CRT_WRITE_C
    scripts/config.py unset MBEDTLS_X509_CSR_WRITE_C
    scripts/config.py unset MBEDTLS_PKCS7_C
    scripts/config.py unset MBEDTLS_SSL_SERVER_NAME_INDICATION
    scripts/config.py unset MBEDTLS_SSL_ASYNC_PRIVATE
    scripts/config.py unset MBEDTLS_X509_TRUSTED_CERTIFICATE_CALLBACK

    make

    msg "test: full minus bignum"
    make test
}

component_build_dhm_alt () {
    msg "build: MBEDTLS_DHM_ALT" # ~30s
    scripts/config.py full
    scripts/config.py set MBEDTLS_DHM_ALT
    # debug.c currently references mbedtls_dhm_context fields directly.
    scripts/config.py unset MBEDTLS_DEBUG_C
    # We can only compile, not link, since we don't have any implementations
    # suitable for testing with the dummy alt headers.
    make CFLAGS='-Werror -Wall -Wextra -I../tests/include/alt-dummy' lib
}

component_test_everest () {
    msg "build: Everest ECDH context (ASan build)" # ~ 6 min
    scripts/config.py set MBEDTLS_ECDH_VARIANT_EVEREST_ENABLED
    CC=clang cmake -D CMAKE_BUILD_TYPE:String=Asan .
    make

    msg "test: Everest ECDH context - main suites (inc. selftests) (ASan build)" # ~ 50s
    make test

    msg "test: metatests (clang, ASan)"
    tests/scripts/run-metatests.sh any asan poison

    msg "test: Everest ECDH context - ECDH-related part of ssl-opt.sh (ASan build)" # ~ 5s
    tests/ssl-opt.sh -f ECDH

    msg "test: Everest ECDH context - compat.sh with some ECDH ciphersuites (ASan build)" # ~ 3 min
    # Exclude some symmetric ciphers that are redundant here to gain time.
    tests/compat.sh -f ECDH -V NO -e 'ARIA\|CAMELLIA\|CHACHA'
}

component_test_everest_curve25519_only () {
    msg "build: Everest ECDH context, only Curve25519" # ~ 6 min
    scripts/config.py set MBEDTLS_ECDH_VARIANT_EVEREST_ENABLED
    scripts/config.py unset MBEDTLS_ECDSA_C
    scripts/config.py unset MBEDTLS_KEY_EXCHANGE_ECDH_ECDSA_ENABLED
    scripts/config.py unset MBEDTLS_KEY_EXCHANGE_ECDHE_ECDSA_ENABLED
    scripts/config.py unset MBEDTLS_ECJPAKE_C
    # Disable all curves
    scripts/config.py unset-all "MBEDTLS_ECP_DP_[0-9A-Z_a-z]*_ENABLED"
    scripts/config.py set MBEDTLS_ECP_DP_CURVE25519_ENABLED

    make CC=$ASAN_CC CFLAGS="$ASAN_CFLAGS" LDFLAGS="$ASAN_CFLAGS"

    msg "test: Everest ECDH context, only Curve25519" # ~ 50s
    make test
}

component_test_psa_collect_statuses () {
  msg "build+test: psa_collect_statuses" # ~30s
  scripts/config.py full
  tests/scripts/psa_collect_statuses.py
  # Check that psa_crypto_init() succeeded at least once
  grep -q '^0:psa_crypto_init:' tests/statuses.log
  rm -f tests/statuses.log
}

# Check that the specified libraries exist and are empty.
are_empty_libraries () {
  nm "$@" >/dev/null 2>/dev/null
  ! nm "$@" 2>/dev/null | grep -v ':$' | grep .
}

component_build_crypto_default () {
  msg "build: make, crypto only"
  scripts/config.py crypto
  make CFLAGS='-O1 -Werror'
  are_empty_libraries library/libmbedx509.* library/libmbedtls.*
}

component_build_crypto_full () {
  msg "build: make, crypto only, full config"
  scripts/config.py crypto_full
  make CFLAGS='-O1 -Werror'
  are_empty_libraries library/libmbedx509.* library/libmbedtls.*
}

component_test_crypto_for_psa_service () {
  msg "build: make, config for PSA crypto service"
  scripts/config.py crypto
  scripts/config.py set MBEDTLS_PSA_CRYPTO_KEY_ID_ENCODES_OWNER
  # Disable things that are not needed for just cryptography, to
  # reach a configuration that would be typical for a PSA cryptography
  # service providing all implemented PSA algorithms.
  # System stuff
  scripts/config.py unset MBEDTLS_ERROR_C
  scripts/config.py unset MBEDTLS_TIMING_C
  scripts/config.py unset MBEDTLS_VERSION_FEATURES
  # Crypto stuff with no PSA interface
  scripts/config.py unset MBEDTLS_BASE64_C
  # Keep MBEDTLS_CIPHER_C because psa_crypto_cipher, CCM and GCM need it.
  scripts/config.py unset MBEDTLS_HKDF_C # PSA's HKDF is independent
  # Keep MBEDTLS_MD_C because deterministic ECDSA needs it for HMAC_DRBG.
  scripts/config.py unset MBEDTLS_NIST_KW_C
  scripts/config.py unset MBEDTLS_PEM_PARSE_C
  scripts/config.py unset MBEDTLS_PEM_WRITE_C
  scripts/config.py unset MBEDTLS_PKCS12_C
  scripts/config.py unset MBEDTLS_PKCS5_C
  # MBEDTLS_PK_PARSE_C and MBEDTLS_PK_WRITE_C are actually currently needed
  # in PSA code to work with RSA keys. We don't require users to set those:
  # they will be reenabled in build_info.h.
  scripts/config.py unset MBEDTLS_PK_C
  scripts/config.py unset MBEDTLS_PK_PARSE_C
  scripts/config.py unset MBEDTLS_PK_WRITE_C
  make CFLAGS='-O1 -Werror' all test
  are_empty_libraries library/libmbedx509.* library/libmbedtls.*
}

component_build_crypto_baremetal () {
  msg "build: make, crypto only, baremetal config"
  scripts/config.py crypto_baremetal
  make CFLAGS="-O1 -Werror -I$PWD/tests/include/baremetal-override/"
  are_empty_libraries library/libmbedx509.* library/libmbedtls.*
}

support_build_crypto_baremetal () {
    support_build_baremetal "$@"
}

# depends.py family of tests
component_test_depends_py_cipher_id () {
    msg "test/build: depends.py cipher_id (gcc)"
    tests/scripts/depends.py cipher_id --unset-use-psa
}

component_test_depends_py_cipher_chaining () {
    msg "test/build: depends.py cipher_chaining (gcc)"
    tests/scripts/depends.py cipher_chaining --unset-use-psa
}

component_test_depends_py_cipher_padding () {
    msg "test/build: depends.py cipher_padding (gcc)"
    tests/scripts/depends.py cipher_padding --unset-use-psa
}

component_test_depends_py_curves () {
    msg "test/build: depends.py curves (gcc)"
    tests/scripts/depends.py curves --unset-use-psa
}

component_test_depends_py_hashes () {
    msg "test/build: depends.py hashes (gcc)"
    tests/scripts/depends.py hashes --unset-use-psa
}

component_test_depends_py_pkalgs () {
    msg "test/build: depends.py pkalgs (gcc)"
    tests/scripts/depends.py pkalgs --unset-use-psa
}

# PSA equivalents of the depends.py tests
component_test_depends_py_cipher_id_psa () {
    msg "test/build: depends.py cipher_id (gcc) with MBEDTLS_USE_PSA_CRYPTO defined"
    tests/scripts/depends.py cipher_id
}

component_test_depends_py_cipher_chaining_psa () {
    msg "test/build: depends.py cipher_chaining (gcc) with MBEDTLS_USE_PSA_CRYPTO defined"
    tests/scripts/depends.py cipher_chaining
}

component_test_depends_py_cipher_padding_psa () {
    msg "test/build: depends.py cipher_padding (gcc) with MBEDTLS_USE_PSA_CRYPTO defined"
    tests/scripts/depends.py cipher_padding
}

component_test_depends_py_curves_psa () {
    msg "test/build: depends.py curves (gcc) with MBEDTLS_USE_PSA_CRYPTO defined"
    tests/scripts/depends.py curves
}

component_test_depends_py_hashes_psa () {
    msg "test/build: depends.py hashes (gcc) with MBEDTLS_USE_PSA_CRYPTO defined"
    tests/scripts/depends.py hashes
}

component_test_depends_py_pkalgs_psa () {
    msg "test/build: depends.py pkalgs (gcc) with MBEDTLS_USE_PSA_CRYPTO defined"
    tests/scripts/depends.py pkalgs
}

component_test_psa_crypto_config_ffdh_2048_only () {
    msg "build: full config - only DH 2048"

    scripts/config.py full

    # Disable all DH groups other than 2048.
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_DH_RFC7919_3072
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_DH_RFC7919_4096
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_DH_RFC7919_6144
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_DH_RFC7919_8192

    make CFLAGS="$ASAN_CFLAGS -Werror" LDFLAGS="$ASAN_CFLAGS"

    msg "test: full config - only DH 2048"
    make test

    msg "ssl-opt: full config - only DH 2048"
    tests/ssl-opt.sh -f "ffdh"
}

component_build_no_pk_rsa_alt_support () {
    msg "build: !MBEDTLS_PK_RSA_ALT_SUPPORT" # ~30s

    scripts/config.py full
    scripts/config.py unset MBEDTLS_PK_RSA_ALT_SUPPORT
    scripts/config.py set MBEDTLS_RSA_C
    scripts/config.py set MBEDTLS_X509_CRT_WRITE_C

    # Only compile - this is primarily to test for compile issues
    make CFLAGS='-Werror -Wall -Wextra -I../tests/include/alt-dummy'
}

component_build_module_alt () {
    msg "build: MBEDTLS_XXX_ALT" # ~30s
    scripts/config.py full

    # Disable options that are incompatible with some ALT implementations:
    # aesni.c and padlock.c reference mbedtls_aes_context fields directly.
    scripts/config.py unset MBEDTLS_AESNI_C
    scripts/config.py unset MBEDTLS_PADLOCK_C
    scripts/config.py unset MBEDTLS_AESCE_C
    # MBEDTLS_ECP_RESTARTABLE is documented as incompatible.
    scripts/config.py unset MBEDTLS_ECP_RESTARTABLE
    # You can only have one threading implementation: alt or pthread, not both.
    scripts/config.py unset MBEDTLS_THREADING_PTHREAD
    # The SpecifiedECDomain parsing code accesses mbedtls_ecp_group fields
    # directly and assumes the implementation works with partial groups.
    scripts/config.py unset MBEDTLS_PK_PARSE_EC_EXTENDED
    # MBEDTLS_SHA256_*ALT can't be used with MBEDTLS_SHA256_USE_ARMV8_A_CRYPTO_*
    scripts/config.py unset MBEDTLS_SHA256_USE_ARMV8_A_CRYPTO_IF_PRESENT
    scripts/config.py unset MBEDTLS_SHA256_USE_ARMV8_A_CRYPTO_ONLY
    # MBEDTLS_SHA512_*ALT can't be used with MBEDTLS_SHA512_USE_A64_CRYPTO_*
    scripts/config.py unset MBEDTLS_SHA512_USE_A64_CRYPTO_IF_PRESENT
    scripts/config.py unset MBEDTLS_SHA512_USE_A64_CRYPTO_ONLY

    # Enable all MBEDTLS_XXX_ALT for whole modules. Do not enable
    # MBEDTLS_XXX_YYY_ALT which are for single functions.
    scripts/config.py set-all 'MBEDTLS_([A-Z0-9]*|NIST_KW)_ALT'
    scripts/config.py unset MBEDTLS_DHM_ALT #incompatible with MBEDTLS_DEBUG_C

    # We can only compile, not link, since we don't have any implementations
    # suitable for testing with the dummy alt headers.
    make CFLAGS='-Werror -Wall -Wextra -I../tests/include/alt-dummy' lib
}

component_test_psa_crypto_config_accel_ecdsa () {
    msg "build: MBEDTLS_PSA_CRYPTO_CONFIG with accelerated ECDSA"

    # Algorithms and key types to accelerate
    loc_accel_list="ALG_ECDSA ALG_DETERMINISTIC_ECDSA \
                    $(helper_get_psa_key_type_list "ECC") \
                    $(helper_get_psa_curve_list)"

    # Configure
    # ---------

    # Start from default config (no USE_PSA) + TLS 1.3
    helper_libtestdriver1_adjust_config "default"

    # Disable the module that's accelerated
    scripts/config.py unset MBEDTLS_ECDSA_C

    # Disable things that depend on it
    scripts/config.py unset MBEDTLS_KEY_EXCHANGE_ECDHE_ECDSA_ENABLED
    scripts/config.py unset MBEDTLS_KEY_EXCHANGE_ECDH_ECDSA_ENABLED

    # Build
    # -----

    # These hashes are needed for some ECDSA signature tests.
    loc_extra_list="ALG_SHA_224 ALG_SHA_256 ALG_SHA_384 ALG_SHA_512 \
                    ALG_SHA3_224 ALG_SHA3_256 ALG_SHA3_384 ALG_SHA3_512"

    helper_libtestdriver1_make_drivers "$loc_accel_list" "$loc_extra_list"

    helper_libtestdriver1_make_main "$loc_accel_list"

    # Make sure this was not re-enabled by accident (additive config)
    not grep mbedtls_ecdsa_ library/ecdsa.o

    # Run the tests
    # -------------

    msg "test: MBEDTLS_PSA_CRYPTO_CONFIG with accelerated ECDSA"
    make test
}

component_test_psa_crypto_config_accel_ecdh () {
    msg "build: MBEDTLS_PSA_CRYPTO_CONFIG with accelerated ECDH"

    # Algorithms and key types to accelerate
    loc_accel_list="ALG_ECDH \
                    $(helper_get_psa_key_type_list "ECC") \
                    $(helper_get_psa_curve_list)"

    # Configure
    # ---------

    # Start from default config (no USE_PSA)
    helper_libtestdriver1_adjust_config "default"

    # Disable the module that's accelerated
    scripts/config.py unset MBEDTLS_ECDH_C

    # Disable things that depend on it
    scripts/config.py unset MBEDTLS_KEY_EXCHANGE_ECDH_RSA_ENABLED
    scripts/config.py unset MBEDTLS_KEY_EXCHANGE_ECDH_ECDSA_ENABLED
    scripts/config.py unset MBEDTLS_KEY_EXCHANGE_ECDHE_ECDSA_ENABLED
    scripts/config.py unset MBEDTLS_KEY_EXCHANGE_ECDHE_RSA_ENABLED
    scripts/config.py unset MBEDTLS_KEY_EXCHANGE_ECDHE_PSK_ENABLED

    # Build
    # -----

    helper_libtestdriver1_make_drivers "$loc_accel_list"

    helper_libtestdriver1_make_main "$loc_accel_list"

    # Make sure this was not re-enabled by accident (additive config)
    not grep mbedtls_ecdh_ library/ecdh.o

    # Run the tests
    # -------------

    msg "test: MBEDTLS_PSA_CRYPTO_CONFIG with accelerated ECDH"
    make test
}

component_test_psa_crypto_config_accel_ffdh () {
    msg "build: full with accelerated FFDH"

    # Algorithms and key types to accelerate
    loc_accel_list="ALG_FFDH \
                    $(helper_get_psa_key_type_list "DH") \
                    $(helper_get_psa_dh_group_list)"

    # Configure
    # ---------

    # start with full (USE_PSA and TLS 1.3)
    helper_libtestdriver1_adjust_config "full"

    # Disable the module that's accelerated
    scripts/config.py unset MBEDTLS_DHM_C

    # Disable things that depend on it
    scripts/config.py unset MBEDTLS_KEY_EXCHANGE_DHE_PSK_ENABLED
    scripts/config.py unset MBEDTLS_KEY_EXCHANGE_DHE_RSA_ENABLED

    # Build
    # -----

    helper_libtestdriver1_make_drivers "$loc_accel_list"

    helper_libtestdriver1_make_main "$loc_accel_list"

    # Make sure this was not re-enabled by accident (additive config)
    not grep mbedtls_dhm_ library/dhm.o

    # Run the tests
    # -------------

    msg "test: full with accelerated FFDH"
    make test

    msg "ssl-opt: full with accelerated FFDH alg"
    tests/ssl-opt.sh -f "ffdh"
}

component_test_psa_crypto_config_reference_ffdh () {
    msg "build: full with non-accelerated FFDH"

    # Start with full (USE_PSA and TLS 1.3)
    helper_libtestdriver1_adjust_config "full"

    # Disable things that are not supported
    scripts/config.py unset MBEDTLS_KEY_EXCHANGE_DHE_PSK_ENABLED
    scripts/config.py unset MBEDTLS_KEY_EXCHANGE_DHE_RSA_ENABLED
    make

    msg "test suites: full with non-accelerated FFDH alg"
    make test

    msg "ssl-opt: full with non-accelerated FFDH alg"
    tests/ssl-opt.sh -f "ffdh"
}

component_test_psa_crypto_config_accel_pake () {
    msg "build: full with accelerated PAKE"

    loc_accel_list="ALG_JPAKE \
                    $(helper_get_psa_key_type_list "ECC") \
                    $(helper_get_psa_curve_list)"

    # Configure
    # ---------

    helper_libtestdriver1_adjust_config "full"

    # Make built-in fallback not available
    scripts/config.py unset MBEDTLS_ECJPAKE_C
    scripts/config.py unset MBEDTLS_KEY_EXCHANGE_ECJPAKE_ENABLED

    # Build
    # -----

    helper_libtestdriver1_make_drivers "$loc_accel_list"

    helper_libtestdriver1_make_main "$loc_accel_list"

    # Make sure this was not re-enabled by accident (additive config)
    not grep mbedtls_ecjpake_init library/ecjpake.o

    # Run the tests
    # -------------

    msg "test: full with accelerated PAKE"
    make test
}

component_test_psa_crypto_config_accel_ecc_some_key_types () {
    msg "build: full with accelerated EC algs and some key types"

    # Algorithms and key types to accelerate
    # For key types, use an explicitly list to omit GENERATE (and DERIVE)
    loc_accel_list="ALG_ECDSA ALG_DETERMINISTIC_ECDSA \
                    ALG_ECDH \
                    ALG_JPAKE \
                    KEY_TYPE_ECC_PUBLIC_KEY \
                    KEY_TYPE_ECC_KEY_PAIR_BASIC \
                    KEY_TYPE_ECC_KEY_PAIR_IMPORT \
                    KEY_TYPE_ECC_KEY_PAIR_EXPORT \
                    $(helper_get_psa_curve_list)"

    # Configure
    # ---------

    # start with config full for maximum coverage (also enables USE_PSA)
    helper_libtestdriver1_adjust_config "full"

    # Disable modules that are accelerated - some will be re-enabled
    scripts/config.py unset MBEDTLS_ECDSA_C
    scripts/config.py unset MBEDTLS_ECDH_C
    scripts/config.py unset MBEDTLS_ECJPAKE_C
    scripts/config.py unset MBEDTLS_ECP_C

    # Disable all curves - those that aren't accelerated should be re-enabled
    helper_disable_builtin_curves

    # Restartable feature is not yet supported by PSA. Once it will in
    # the future, the following line could be removed (see issues
    # 6061, 6332 and following ones)
    scripts/config.py unset MBEDTLS_ECP_RESTARTABLE

    # this is not supported by the driver API yet
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_KEY_TYPE_ECC_KEY_PAIR_DERIVE

    # Build
    # -----

    # These hashes are needed for some ECDSA signature tests.
    loc_extra_list="ALG_SHA_1 ALG_SHA_224 ALG_SHA_256 ALG_SHA_384 ALG_SHA_512 \
                    ALG_SHA3_224 ALG_SHA3_256 ALG_SHA3_384 ALG_SHA3_512"
    helper_libtestdriver1_make_drivers "$loc_accel_list" "$loc_extra_list"

    helper_libtestdriver1_make_main "$loc_accel_list"

    # ECP should be re-enabled but not the others
    not grep mbedtls_ecdh_ library/ecdh.o
    not grep mbedtls_ecdsa library/ecdsa.o
    not grep mbedtls_ecjpake  library/ecjpake.o
    grep mbedtls_ecp library/ecp.o

    # Run the tests
    # -------------

    msg "test suites: full with accelerated EC algs and some key types"
    make test
}

# Run tests with only (non-)Weierstrass accelerated
# Common code used in:
# - component_test_psa_crypto_config_accel_ecc_weierstrass_curves
# - component_test_psa_crypto_config_accel_ecc_non_weierstrass_curves
common_test_psa_crypto_config_accel_ecc_some_curves () {
    weierstrass=$1
    if [ $weierstrass -eq 1 ]; then
        desc="Weierstrass"
    else
        desc="non-Weierstrass"
    fi

    msg "build: crypto_full minus PK with accelerated EC algs and $desc curves"

    # Note: Curves are handled in a special way by the libtestdriver machinery,
    # so we only want to include them in the accel list when building the main
    # libraries, hence the use of a separate variable.
    # Note: the following loop is a modified version of
    # helper_get_psa_curve_list that only keeps Weierstrass families.
    loc_weierstrass_list=""
    loc_non_weierstrass_list=""
    for item in $(sed -n 's/^#define PSA_WANT_\(ECC_[0-9A-Z_a-z]*\).*/\1/p' <"$CRYPTO_CONFIG_H"); do
        case $item in
            ECC_BRAINPOOL*|ECC_SECP*)
                loc_weierstrass_list="$loc_weierstrass_list $item"
                ;;
            *)
                loc_non_weierstrass_list="$loc_non_weierstrass_list $item"
                ;;
        esac
    done
    if [ $weierstrass -eq 1 ]; then
        loc_curve_list=$loc_weierstrass_list
    else
        loc_curve_list=$loc_non_weierstrass_list
    fi

    # Algorithms and key types to accelerate
    loc_accel_list="ALG_ECDSA ALG_DETERMINISTIC_ECDSA \
                    ALG_ECDH \
                    ALG_JPAKE \
                    $(helper_get_psa_key_type_list "ECC") \
                    $loc_curve_list"

    # Configure
    # ---------

    # Start with config crypto_full and remove PK_C:
    # that's what's supported now, see docs/driver-only-builds.md.
    helper_libtestdriver1_adjust_config "crypto_full"
    scripts/config.py unset MBEDTLS_PK_C
    scripts/config.py unset MBEDTLS_PK_PARSE_C
    scripts/config.py unset MBEDTLS_PK_WRITE_C

    # Disable modules that are accelerated - some will be re-enabled
    scripts/config.py unset MBEDTLS_ECDSA_C
    scripts/config.py unset MBEDTLS_ECDH_C
    scripts/config.py unset MBEDTLS_ECJPAKE_C
    scripts/config.py unset MBEDTLS_ECP_C

    # Disable all curves - those that aren't accelerated should be re-enabled
    helper_disable_builtin_curves

    # Restartable feature is not yet supported by PSA. Once it will in
    # the future, the following line could be removed (see issues
    # 6061, 6332 and following ones)
    scripts/config.py unset MBEDTLS_ECP_RESTARTABLE

    # this is not supported by the driver API yet
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_KEY_TYPE_ECC_KEY_PAIR_DERIVE

    # Build
    # -----

    # These hashes are needed for some ECDSA signature tests.
    loc_extra_list="ALG_SHA_1 ALG_SHA_224 ALG_SHA_256 ALG_SHA_384 ALG_SHA_512 \
                    ALG_SHA3_224 ALG_SHA3_256 ALG_SHA3_384 ALG_SHA3_512"
    helper_libtestdriver1_make_drivers "$loc_accel_list" "$loc_extra_list"

    helper_libtestdriver1_make_main "$loc_accel_list"

    # We expect ECDH to be re-enabled for the missing curves
    grep mbedtls_ecdh_ library/ecdh.o
    # We expect ECP to be re-enabled, however the parts specific to the
    # families of curves that are accelerated should be ommited.
    # - functions with mxz in the name are specific to Montgomery curves
    # - ecp_muladd is specific to Weierstrass curves
    ##nm library/ecp.o | tee ecp.syms
    if [ $weierstrass -eq 1 ]; then
        not grep mbedtls_ecp_muladd library/ecp.o
        grep mxz library/ecp.o
    else
        grep mbedtls_ecp_muladd library/ecp.o
        not grep mxz library/ecp.o
    fi
    # We expect ECDSA and ECJPAKE to be re-enabled only when
    # Weierstrass curves are not accelerated
    if [ $weierstrass -eq 1 ]; then
        not grep mbedtls_ecdsa library/ecdsa.o
        not grep mbedtls_ecjpake  library/ecjpake.o
    else
        grep mbedtls_ecdsa library/ecdsa.o
        grep mbedtls_ecjpake  library/ecjpake.o
    fi

    # Run the tests
    # -------------

    msg "test suites: crypto_full minus PK with accelerated EC algs and $desc curves"
    make test
}

component_test_psa_crypto_config_accel_ecc_weierstrass_curves () {
    common_test_psa_crypto_config_accel_ecc_some_curves 1
}

component_test_psa_crypto_config_accel_ecc_non_weierstrass_curves () {
    common_test_psa_crypto_config_accel_ecc_some_curves 0
}

# Auxiliary function to build config for all EC based algorithms (EC-JPAKE,
# ECDH, ECDSA) with and without drivers.
# The input parameter is a boolean value which indicates:
# - 0 keep built-in EC algs,
# - 1 exclude built-in EC algs (driver only).
#
# This is used by the two following components to ensure they always use the
# same config, except for the use of driver or built-in EC algorithms:
# - component_test_psa_crypto_config_accel_ecc_ecp_light_only;
# - component_test_psa_crypto_config_reference_ecc_ecp_light_only.
# This supports comparing their test coverage with analyze_outcomes.py.
config_psa_crypto_config_ecp_light_only () {
    driver_only="$1"
    # start with config full for maximum coverage (also enables USE_PSA)
    helper_libtestdriver1_adjust_config "full"
    if [ "$driver_only" -eq 1 ]; then
        # Disable modules that are accelerated
        scripts/config.py unset MBEDTLS_ECDSA_C
        scripts/config.py unset MBEDTLS_ECDH_C
        scripts/config.py unset MBEDTLS_ECJPAKE_C
        scripts/config.py unset MBEDTLS_ECP_C
    fi

    # Restartable feature is not yet supported by PSA. Once it will in
    # the future, the following line could be removed (see issues
    # 6061, 6332 and following ones)
    scripts/config.py unset MBEDTLS_ECP_RESTARTABLE
}

# Keep in sync with component_test_psa_crypto_config_reference_ecc_ecp_light_only
component_test_psa_crypto_config_accel_ecc_ecp_light_only () {
    msg "build: full with accelerated EC algs"

    # Algorithms and key types to accelerate
    loc_accel_list="ALG_ECDSA ALG_DETERMINISTIC_ECDSA \
                    ALG_ECDH \
                    ALG_JPAKE \
                    $(helper_get_psa_key_type_list "ECC") \
                    $(helper_get_psa_curve_list)"

    # Configure
    # ---------

    # Use the same config as reference, only without built-in EC algs
    config_psa_crypto_config_ecp_light_only 1

    # Do not disable builtin curves because that support is required for:
    # - MBEDTLS_PK_PARSE_EC_EXTENDED
    # - MBEDTLS_PK_PARSE_EC_COMPRESSED

    # Build
    # -----

    # These hashes are needed for some ECDSA signature tests.
    loc_extra_list="ALG_SHA_1 ALG_SHA_224 ALG_SHA_256 ALG_SHA_384 ALG_SHA_512 \
                    ALG_SHA3_224 ALG_SHA3_256 ALG_SHA3_384 ALG_SHA3_512"
    helper_libtestdriver1_make_drivers "$loc_accel_list" "$loc_extra_list"

    helper_libtestdriver1_make_main "$loc_accel_list"

    # Make sure any built-in EC alg was not re-enabled by accident (additive config)
    not grep mbedtls_ecdsa_ library/ecdsa.o
    not grep mbedtls_ecdh_ library/ecdh.o
    not grep mbedtls_ecjpake_ library/ecjpake.o
    not grep mbedtls_ecp_mul library/ecp.o

    # Run the tests
    # -------------

    msg "test suites: full with accelerated EC algs"
    make test

    msg "ssl-opt: full with accelerated EC algs"
    tests/ssl-opt.sh
}

# Keep in sync with component_test_psa_crypto_config_accel_ecc_ecp_light_only
component_test_psa_crypto_config_reference_ecc_ecp_light_only () {
    msg "build: MBEDTLS_PSA_CRYPTO_CONFIG with non-accelerated EC algs"

    config_psa_crypto_config_ecp_light_only 0

    make

    msg "test suites: full with non-accelerated EC algs"
    make test

    msg "ssl-opt: full with non-accelerated EC algs"
    tests/ssl-opt.sh
}

# This helper function is used by:
# - component_test_psa_crypto_config_accel_ecc_no_ecp_at_all()
# - component_test_psa_crypto_config_reference_ecc_no_ecp_at_all()
# to ensure that both tests use the same underlying configuration when testing
# driver's coverage with analyze_outcomes.py.
#
# This functions accepts 1 boolean parameter as follows:
# - 1: building with accelerated EC algorithms (ECDSA, ECDH, ECJPAKE), therefore
#      excluding their built-in implementation as well as ECP_C & ECP_LIGHT
# - 0: include built-in implementation of EC algorithms.
#
# PK_C and RSA_C are always disabled to ensure there is no remaining dependency
# on the ECP module.
config_psa_crypto_no_ecp_at_all () {
    driver_only="$1"
    # start with full config for maximum coverage (also enables USE_PSA)
    helper_libtestdriver1_adjust_config "full"

    if [ "$driver_only" -eq 1 ]; then
        # Disable modules that are accelerated
        scripts/config.py unset MBEDTLS_ECDSA_C
        scripts/config.py unset MBEDTLS_ECDH_C
        scripts/config.py unset MBEDTLS_ECJPAKE_C
        # Disable ECP module (entirely)
        scripts/config.py unset MBEDTLS_ECP_C
    fi

    # Disable all the features that auto-enable ECP_LIGHT (see build_info.h)
    scripts/config.py unset MBEDTLS_PK_PARSE_EC_EXTENDED
    scripts/config.py unset MBEDTLS_PK_PARSE_EC_COMPRESSED
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_KEY_TYPE_ECC_KEY_PAIR_DERIVE

    # Restartable feature is not yet supported by PSA. Once it will in
    # the future, the following line could be removed (see issues
    # 6061, 6332 and following ones)
    scripts/config.py unset MBEDTLS_ECP_RESTARTABLE
}

# Build and test a configuration where driver accelerates all EC algs while
# all support and dependencies from ECP and ECP_LIGHT are removed on the library
# side.
#
# Keep in sync with component_test_psa_crypto_config_reference_ecc_no_ecp_at_all()
component_test_psa_crypto_config_accel_ecc_no_ecp_at_all () {
    msg "build: full + accelerated EC algs - ECP"

    # Algorithms and key types to accelerate
    loc_accel_list="ALG_ECDSA ALG_DETERMINISTIC_ECDSA \
                    ALG_ECDH \
                    ALG_JPAKE \
                    $(helper_get_psa_key_type_list "ECC") \
                    $(helper_get_psa_curve_list)"

    # Configure
    # ---------

    # Set common configurations between library's and driver's builds
    config_psa_crypto_no_ecp_at_all 1
    # Disable all the builtin curves. All the required algs are accelerated.
    helper_disable_builtin_curves

    # Build
    # -----

    # Things we wanted supported in libtestdriver1, but not accelerated in the main library:
    # SHA-1 and all SHA-2/3 variants, as they are used by ECDSA deterministic.
    loc_extra_list="ALG_SHA_1 ALG_SHA_224 ALG_SHA_256 ALG_SHA_384 ALG_SHA_512 \
                    ALG_SHA3_224 ALG_SHA3_256 ALG_SHA3_384 ALG_SHA3_512"

    helper_libtestdriver1_make_drivers "$loc_accel_list" "$loc_extra_list"

    helper_libtestdriver1_make_main "$loc_accel_list"

    # Make sure any built-in EC alg was not re-enabled by accident (additive config)
    not grep mbedtls_ecdsa_ library/ecdsa.o
    not grep mbedtls_ecdh_ library/ecdh.o
    not grep mbedtls_ecjpake_ library/ecjpake.o
    # Also ensure that ECP module was not re-enabled
    not grep mbedtls_ecp_ library/ecp.o

    # Run the tests
    # -------------

    msg "test: full + accelerated EC algs - ECP"
    make test

    msg "ssl-opt: full + accelerated EC algs - ECP"
    tests/ssl-opt.sh
}

# Reference function used for driver's coverage analysis in analyze_outcomes.py
# in conjunction with component_test_psa_crypto_config_accel_ecc_no_ecp_at_all().
# Keep in sync with its accelerated counterpart.
component_test_psa_crypto_config_reference_ecc_no_ecp_at_all () {
    msg "build: full + non accelerated EC algs"

    config_psa_crypto_no_ecp_at_all 0

    make

    msg "test: full + non accelerated EC algs"
    make test

    msg "ssl-opt: full + non accelerated EC algs"
    tests/ssl-opt.sh
}

# This is a common configuration helper used directly from:
# - common_test_psa_crypto_config_accel_ecc_ffdh_no_bignum
# - common_test_psa_crypto_config_reference_ecc_ffdh_no_bignum
# and indirectly from:
# - component_test_psa_crypto_config_accel_ecc_no_bignum
#       - accelerate all EC algs, disable RSA and FFDH
# - component_test_psa_crypto_config_reference_ecc_no_bignum
#       - this is the reference component of the above
#       - it still disables RSA and FFDH, but it uses builtin EC algs
# - component_test_psa_crypto_config_accel_ecc_ffdh_no_bignum
#       - accelerate all EC and FFDH algs, disable only RSA
# - component_test_psa_crypto_config_reference_ecc_ffdh_no_bignum
#       - this is the reference component of the above
#       - it still disables RSA, but it uses builtin EC and FFDH algs
#
# This function accepts 2 parameters:
# $1: a boolean value which states if we are testing an accelerated scenario
#     or not.
# $2: a string value which states which components are tested. Allowed values
#     are "ECC" or "ECC_DH".
config_psa_crypto_config_accel_ecc_ffdh_no_bignum () {
    driver_only="$1"
    test_target="$2"
    # start with full config for maximum coverage (also enables USE_PSA)
    helper_libtestdriver1_adjust_config "full"

    if [ "$driver_only" -eq 1 ]; then
        # Disable modules that are accelerated
        scripts/config.py unset MBEDTLS_ECDSA_C
        scripts/config.py unset MBEDTLS_ECDH_C
        scripts/config.py unset MBEDTLS_ECJPAKE_C
        # Disable ECP module (entirely)
        scripts/config.py unset MBEDTLS_ECP_C
        # Also disable bignum
        scripts/config.py unset MBEDTLS_BIGNUM_C
    fi

    # Disable all the features that auto-enable ECP_LIGHT (see build_info.h)
    scripts/config.py unset MBEDTLS_PK_PARSE_EC_EXTENDED
    scripts/config.py unset MBEDTLS_PK_PARSE_EC_COMPRESSED
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_KEY_TYPE_ECC_KEY_PAIR_DERIVE

    # RSA support is intentionally disabled on this test because RSA_C depends
    # on BIGNUM_C.
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset-all "PSA_WANT_KEY_TYPE_RSA_[0-9A-Z_a-z]*"
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset-all "PSA_WANT_ALG_RSA_[0-9A-Z_a-z]*"
    scripts/config.py unset MBEDTLS_RSA_C
    scripts/config.py unset MBEDTLS_PKCS1_V15
    scripts/config.py unset MBEDTLS_PKCS1_V21
    scripts/config.py unset MBEDTLS_X509_RSASSA_PSS_SUPPORT
    # Also disable key exchanges that depend on RSA
    scripts/config.py unset MBEDTLS_KEY_EXCHANGE_RSA_PSK_ENABLED
    scripts/config.py unset MBEDTLS_KEY_EXCHANGE_RSA_ENABLED
    scripts/config.py unset MBEDTLS_KEY_EXCHANGE_DHE_RSA_ENABLED
    scripts/config.py unset MBEDTLS_KEY_EXCHANGE_ECDHE_RSA_ENABLED
    scripts/config.py unset MBEDTLS_KEY_EXCHANGE_ECDH_RSA_ENABLED

    if [ "$test_target" = "ECC" ]; then
        # When testing ECC only, we disable FFDH support, both from builtin and
        # PSA sides, and also disable the key exchanges that depend on DHM.
        scripts/config.py -f include/psa/crypto_config.h unset PSA_WANT_ALG_FFDH
        scripts/config.py -f "$CRYPTO_CONFIG_H" unset-all "PSA_WANT_KEY_TYPE_DH_[0-9A-Z_a-z]*"
        scripts/config.py -f "$CRYPTO_CONFIG_H" unset-all "PSA_WANT_DH_RFC7919_[0-9]*"
        scripts/config.py unset MBEDTLS_DHM_C
        scripts/config.py unset MBEDTLS_KEY_EXCHANGE_DHE_PSK_ENABLED
        scripts/config.py unset MBEDTLS_KEY_EXCHANGE_DHE_RSA_ENABLED
    else
        # When testing ECC and DH instead, we disable DHM and depending key
        # exchanges only in the accelerated build
        if [ "$driver_only" -eq 1 ]; then
            scripts/config.py unset MBEDTLS_DHM_C
            scripts/config.py unset MBEDTLS_KEY_EXCHANGE_DHE_PSK_ENABLED
            scripts/config.py unset MBEDTLS_KEY_EXCHANGE_DHE_RSA_ENABLED
        fi
    fi

    # Restartable feature is not yet supported by PSA. Once it will in
    # the future, the following line could be removed (see issues
    # 6061, 6332 and following ones)
    scripts/config.py unset MBEDTLS_ECP_RESTARTABLE
}

# Common helper used by:
# - component_test_psa_crypto_config_accel_ecc_no_bignum
# - component_test_psa_crypto_config_accel_ecc_ffdh_no_bignum
#
# The goal is to build and test accelerating either:
# - ECC only or
# - both ECC and FFDH
#
# It is meant to be used in conjunction with
# common_test_psa_crypto_config_reference_ecc_ffdh_no_bignum() for drivers
# coverage analysis in the "analyze_outcomes.py" script.
common_test_psa_crypto_config_accel_ecc_ffdh_no_bignum () {
    test_target="$1"

    # This is an internal helper to simplify text message handling
    if [ "$test_target" = "ECC_DH" ]; then
        accel_text="ECC/FFDH"
        removed_text="ECP - DH"
    else
        accel_text="ECC"
        removed_text="ECP"
    fi

    msg "build: full + accelerated $accel_text algs + USE_PSA - $removed_text - BIGNUM"

    # By default we accelerate all EC keys/algs
    loc_accel_list="ALG_ECDSA ALG_DETERMINISTIC_ECDSA \
                    ALG_ECDH \
                    ALG_JPAKE \
                    $(helper_get_psa_key_type_list "ECC") \
                    $(helper_get_psa_curve_list)"
    # Optionally we can also add DH to the list of accelerated items
    if [ "$test_target" = "ECC_DH" ]; then
        loc_accel_list="$loc_accel_list \
                        ALG_FFDH \
                        $(helper_get_psa_key_type_list "DH") \
                        $(helper_get_psa_dh_group_list)"
    fi

    # Configure
    # ---------

    # Set common configurations between library's and driver's builds
    config_psa_crypto_config_accel_ecc_ffdh_no_bignum 1 "$test_target"
    # Disable all the builtin curves. All the required algs are accelerated.
    helper_disable_builtin_curves

    # Build
    # -----

    # Things we wanted supported in libtestdriver1, but not accelerated in the main library:
    # SHA-1 and all SHA-2/3 variants, as they are used by ECDSA deterministic.
    loc_extra_list="ALG_SHA_1 ALG_SHA_224 ALG_SHA_256 ALG_SHA_384 ALG_SHA_512 \
                    ALG_SHA3_224 ALG_SHA3_256 ALG_SHA3_384 ALG_SHA3_512"

    helper_libtestdriver1_make_drivers "$loc_accel_list" "$loc_extra_list"

    helper_libtestdriver1_make_main "$loc_accel_list"

    # Make sure any built-in EC alg was not re-enabled by accident (additive config)
    not grep mbedtls_ecdsa_ library/ecdsa.o
    not grep mbedtls_ecdh_ library/ecdh.o
    not grep mbedtls_ecjpake_ library/ecjpake.o
    # Also ensure that ECP, RSA, [DHM] or BIGNUM modules were not re-enabled
    not grep mbedtls_ecp_ library/ecp.o
    not grep mbedtls_rsa_ library/rsa.o
    not grep mbedtls_mpi_ library/bignum.o
    not grep mbedtls_dhm_ library/dhm.o

    # Run the tests
    # -------------

    msg "test suites: full + accelerated $accel_text algs + USE_PSA - $removed_text - DHM - BIGNUM"

    make test

    msg "ssl-opt: full + accelerated $accel_text algs + USE_PSA - $removed_text - BIGNUM"
    tests/ssl-opt.sh
}

# Common helper used by:
# - component_test_psa_crypto_config_reference_ecc_no_bignum
# - component_test_psa_crypto_config_reference_ecc_ffdh_no_bignum
#
# The goal is to build and test a reference scenario (i.e. with builtin
# components) compared to the ones used in
# common_test_psa_crypto_config_accel_ecc_ffdh_no_bignum() above.
#
# It is meant to be used in conjunction with
# common_test_psa_crypto_config_accel_ecc_ffdh_no_bignum() for drivers'
# coverage analysis in "analyze_outcomes.py" script.
common_test_psa_crypto_config_reference_ecc_ffdh_no_bignum () {
    test_target="$1"

    # This is an internal helper to simplify text message handling
    if [ "$test_target" = "ECC_DH" ]; then
        accel_text="ECC/FFDH"
    else
        accel_text="ECC"
    fi

    msg "build: full + non accelerated $accel_text algs + USE_PSA"

    config_psa_crypto_config_accel_ecc_ffdh_no_bignum 0 "$test_target"

    make

    msg "test suites: full + non accelerated EC algs + USE_PSA"
    make test

    msg "ssl-opt: full + non accelerated $accel_text algs + USE_PSA"
    tests/ssl-opt.sh
}

component_test_psa_crypto_config_accel_ecc_no_bignum () {
    common_test_psa_crypto_config_accel_ecc_ffdh_no_bignum "ECC"
}

component_test_psa_crypto_config_reference_ecc_no_bignum () {
    common_test_psa_crypto_config_reference_ecc_ffdh_no_bignum "ECC"
}

component_test_psa_crypto_config_accel_ecc_ffdh_no_bignum () {
    common_test_psa_crypto_config_accel_ecc_ffdh_no_bignum "ECC_DH"
}

component_test_psa_crypto_config_reference_ecc_ffdh_no_bignum () {
    common_test_psa_crypto_config_reference_ecc_ffdh_no_bignum "ECC_DH"
}

# Helper for setting common configurations between:
# - component_test_tfm_config_p256m_driver_accel_ec()
# - component_test_tfm_config()
common_tfm_config () {
    # Enable TF-M config
    cp configs/config-tfm.h "$CONFIG_H"
    echo "#undef MBEDTLS_PSA_CRYPTO_CONFIG_FILE" >> "$CONFIG_H"
    cp configs/ext/crypto_config_profile_medium.h "$CRYPTO_CONFIG_H"

    # Other config adjustment to make the tests pass.
    # This should probably be adopted upstream.
    #
    # - USE_PSA_CRYPTO for PK_HAVE_ECC_KEYS
    echo "#define MBEDTLS_USE_PSA_CRYPTO" >> "$CONFIG_H"

    # Config adjustment for better test coverage in our environment.
    # This is not needed just to build and pass tests.
    #
    # Enable filesystem I/O for the benefit of PK parse/write tests.
    echo "#define MBEDTLS_FS_IO" >> "$CONFIG_H"
}

# Keep this in sync with component_test_tfm_config() as they are both meant
# to be used in analyze_outcomes.py for driver's coverage analysis.
component_test_tfm_config_p256m_driver_accel_ec () {
    msg "build: TF-M config + p256m driver + accel ECDH(E)/ECDSA"

    common_tfm_config

    # Build crypto library
    make CC=$ASAN_CC CFLAGS="$ASAN_CFLAGS -I../tests/include/spe" LDFLAGS="$ASAN_CFLAGS"

    # Make sure any built-in EC alg was not re-enabled by accident (additive config)
    not grep mbedtls_ecdsa_ library/ecdsa.o
    not grep mbedtls_ecdh_ library/ecdh.o
    not grep mbedtls_ecjpake_ library/ecjpake.o
    # Also ensure that ECP, RSA, DHM or BIGNUM modules were not re-enabled
    not grep mbedtls_ecp_ library/ecp.o
    not grep mbedtls_rsa_ library/rsa.o
    not grep mbedtls_dhm_ library/dhm.o
    not grep mbedtls_mpi_ library/bignum.o
    # Check that p256m was built
    grep -q p256_ecdsa_ library/libmbedcrypto.a

    # In "config-tfm.h" we disabled CIPHER_C tweaking TF-M's configuration
    # files, so we want to ensure that it has not be re-enabled accidentally.
    not grep mbedtls_cipher library/cipher.o

    # Run the tests
    msg "test: TF-M config + p256m driver + accel ECDH(E)/ECDSA"
    make test
}

# Keep this in sync with component_test_tfm_config_p256m_driver_accel_ec() as
# they are both meant to be used in analyze_outcomes.py for driver's coverage
# analysis.
component_test_tfm_config () {
    common_tfm_config

    # Disable P256M driver, which is on by default, so that analyze_outcomes
    # can compare this test with test_tfm_config_p256m_driver_accel_ec
    echo "#undef MBEDTLS_PSA_P256M_DRIVER_ENABLED" >> "$CONFIG_H"

    msg "build: TF-M config"
    make CFLAGS='-Werror -Wall -Wextra -I../tests/include/spe' tests

    # Check that p256m was not built
    not grep p256_ecdsa_ library/libmbedcrypto.a

    # In "config-tfm.h" we disabled CIPHER_C tweaking TF-M's configuration
    # files, so we want to ensure that it has not be re-enabled accidentally.
    not grep mbedtls_cipher library/cipher.o

    msg "test: TF-M config"
    make test
}

# This is an helper used by:
# - component_test_psa_ecc_key_pair_no_derive
# - component_test_psa_ecc_key_pair_no_generate
# The goal is to test with all PSA_WANT_KEY_TYPE_xxx_KEY_PAIR_yyy symbols
# enabled, but one. Input arguments are as follows:
# - $1 is the key type under test, i.e. ECC/RSA/DH
# - $2 is the key option to be unset (i.e. generate, derive, etc)
build_and_test_psa_want_key_pair_partial () {
    key_type=$1
    unset_option=$2
    disabled_psa_want="PSA_WANT_KEY_TYPE_${key_type}_KEY_PAIR_${unset_option}"

    msg "build: full - MBEDTLS_USE_PSA_CRYPTO - ${disabled_psa_want}"
    scripts/config.py full
    scripts/config.py unset MBEDTLS_USE_PSA_CRYPTO
    scripts/config.py unset MBEDTLS_SSL_PROTO_TLS1_3

    # All the PSA_WANT_KEY_TYPE_xxx_KEY_PAIR_yyy are enabled by default in
    # crypto_config.h so we just disable the one we don't want.
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset "$disabled_psa_want"

    make CC=$ASAN_CC CFLAGS="$ASAN_CFLAGS" LDFLAGS="$ASAN_CFLAGS"

    msg "test: full - MBEDTLS_USE_PSA_CRYPTO - ${disabled_psa_want}"
    make test
}

component_test_psa_ecc_key_pair_no_derive () {
    build_and_test_psa_want_key_pair_partial "ECC" "DERIVE"
}

component_test_psa_ecc_key_pair_no_generate () {
    build_and_test_psa_want_key_pair_partial "ECC" "GENERATE"
}

config_psa_crypto_accel_rsa () {
    driver_only=$1

    # Start from crypto_full config (no X.509, no TLS)
    helper_libtestdriver1_adjust_config "crypto_full"

    if [ "$driver_only" -eq 1 ]; then
        # Remove RSA support and its dependencies
        scripts/config.py unset MBEDTLS_RSA_C
        scripts/config.py unset MBEDTLS_PKCS1_V15
        scripts/config.py unset MBEDTLS_PKCS1_V21

        # We need PEM parsing in the test library as well to support the import
        # of PEM encoded RSA keys.
        scripts/config.py -f "$CONFIG_TEST_DRIVER_H" set MBEDTLS_PEM_PARSE_C
        scripts/config.py -f "$CONFIG_TEST_DRIVER_H" set MBEDTLS_BASE64_C
    fi
}

component_test_psa_crypto_config_accel_rsa_crypto () {
    msg "build: crypto_full with accelerated RSA"

    loc_accel_list="ALG_RSA_OAEP ALG_RSA_PSS \
                    ALG_RSA_PKCS1V15_CRYPT ALG_RSA_PKCS1V15_SIGN \
                    KEY_TYPE_RSA_PUBLIC_KEY \
                    KEY_TYPE_RSA_KEY_PAIR_BASIC \
                    KEY_TYPE_RSA_KEY_PAIR_GENERATE \
                    KEY_TYPE_RSA_KEY_PAIR_IMPORT \
                    KEY_TYPE_RSA_KEY_PAIR_EXPORT"

    # Configure
    # ---------

    config_psa_crypto_accel_rsa 1

    # Build
    # -----

    # These hashes are needed for unit tests.
    loc_extra_list="ALG_SHA_1 ALG_SHA_224 ALG_SHA_256 ALG_SHA_384 ALG_SHA_512 \
                    ALG_SHA3_224 ALG_SHA3_256 ALG_SHA3_384 ALG_SHA3_512 ALG_MD5"
    helper_libtestdriver1_make_drivers "$loc_accel_list" "$loc_extra_list"

    helper_libtestdriver1_make_main "$loc_accel_list"

    # Make sure this was not re-enabled by accident (additive config)
    not grep mbedtls_rsa library/rsa.o

    # Run the tests
    # -------------

    msg "test: crypto_full with accelerated RSA"
    make test
}

component_test_psa_crypto_config_reference_rsa_crypto () {
    msg "build: crypto_full with non-accelerated RSA"

    # Configure
    # ---------
    config_psa_crypto_accel_rsa 0

    # Build
    # -----
    make

    # Run the tests
    # -------------
    msg "test: crypto_full with non-accelerated RSA"
    make test
}

# This is a temporary test to verify that full RSA support is present even when
# only one single new symbols (PSA_WANT_KEY_TYPE_RSA_KEY_PAIR_BASIC) is defined.
component_test_new_psa_want_key_pair_symbol () {
    msg "Build: crypto config - MBEDTLS_RSA_C + PSA_WANT_KEY_TYPE_RSA_KEY_PAIR_BASIC"

    # Create a temporary output file unless there is already one set
    if [ "$MBEDTLS_TEST_OUTCOME_FILE" ]; then
        REMOVE_OUTCOME_ON_EXIT="no"
    else
        REMOVE_OUTCOME_ON_EXIT="yes"
        MBEDTLS_TEST_OUTCOME_FILE="$PWD/out.csv"
        export MBEDTLS_TEST_OUTCOME_FILE
    fi

    # Start from crypto configuration
    scripts/config.py crypto

    # Remove RSA support and its dependencies
    scripts/config.py unset MBEDTLS_PKCS1_V15
    scripts/config.py unset MBEDTLS_PKCS1_V21
    scripts/config.py unset MBEDTLS_KEY_EXCHANGE_DHE_RSA_ENABLED
    scripts/config.py unset MBEDTLS_KEY_EXCHANGE_ECDH_RSA_ENABLED
    scripts/config.py unset MBEDTLS_KEY_EXCHANGE_ECDHE_RSA_ENABLED
    scripts/config.py unset MBEDTLS_KEY_EXCHANGE_RSA_PSK_ENABLED
    scripts/config.py unset MBEDTLS_KEY_EXCHANGE_RSA_ENABLED
    scripts/config.py unset MBEDTLS_RSA_C
    scripts/config.py unset MBEDTLS_X509_RSASSA_PSS_SUPPORT

    # Enable PSA support
    scripts/config.py set MBEDTLS_PSA_CRYPTO_CONFIG

    # Keep only PSA_WANT_KEY_TYPE_RSA_KEY_PAIR_BASIC enabled in order to ensure
    # that proper translations is done in crypto_legacy.h.
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_KEY_TYPE_RSA_KEY_PAIR_IMPORT
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_KEY_TYPE_RSA_KEY_PAIR_EXPORT
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_KEY_TYPE_RSA_KEY_PAIR_GENERATE

    make

    msg "Test: crypto config - MBEDTLS_RSA_C + PSA_WANT_KEY_TYPE_RSA_KEY_PAIR_BASIC"
    make test

    # Parse only 1 relevant line from the outcome file, i.e. a test which is
    # performing RSA signature.
    msg "Verify that 'RSA PKCS1 Sign #1 (SHA512, 1536 bits RSA)' is PASS"
    cat $MBEDTLS_TEST_OUTCOME_FILE | grep 'RSA PKCS1 Sign #1 (SHA512, 1536 bits RSA)' | grep -q "PASS"

    if [ "$REMOVE_OUTCOME_ON_EXIT" == "yes" ]; then
        rm $MBEDTLS_TEST_OUTCOME_FILE
    fi
}

component_test_psa_crypto_config_accel_hash () {
    msg "test: MBEDTLS_PSA_CRYPTO_CONFIG with accelerated hash"

    loc_accel_list="ALG_MD5 ALG_RIPEMD160 ALG_SHA_1 \
                    ALG_SHA_224 ALG_SHA_256 ALG_SHA_384 ALG_SHA_512 \
                    ALG_SHA3_224 ALG_SHA3_256 ALG_SHA3_384 ALG_SHA3_512"

    # Configure
    # ---------

    # Start from default config (no USE_PSA)
    helper_libtestdriver1_adjust_config "default"

    # Disable the things that are being accelerated
    scripts/config.py unset MBEDTLS_MD5_C
    scripts/config.py unset MBEDTLS_RIPEMD160_C
    scripts/config.py unset MBEDTLS_SHA1_C
    scripts/config.py unset MBEDTLS_SHA224_C
    scripts/config.py unset MBEDTLS_SHA256_C
    scripts/config.py unset MBEDTLS_SHA384_C
    scripts/config.py unset MBEDTLS_SHA512_C
    scripts/config.py unset MBEDTLS_SHA3_C

    # Build
    # -----

    helper_libtestdriver1_make_drivers "$loc_accel_list"

    helper_libtestdriver1_make_main "$loc_accel_list"

    # There's a risk of something getting re-enabled via config_psa.h;
    # make sure it did not happen. Note: it's OK for MD_C to be enabled.
    not grep mbedtls_md5 library/md5.o
    not grep mbedtls_sha1 library/sha1.o
    not grep mbedtls_sha256 library/sha256.o
    not grep mbedtls_sha512 library/sha512.o
    not grep mbedtls_ripemd160 library/ripemd160.o

    # Run the tests
    # -------------

    msg "test: MBEDTLS_PSA_CRYPTO_CONFIG with accelerated hash"
    make test
}

component_test_psa_crypto_config_accel_hash_keep_builtins () {
    msg "test: MBEDTLS_PSA_CRYPTO_CONFIG with accelerated+builtin hash"
    # This component ensures that all the test cases for
    # md_psa_dynamic_dispatch with legacy+driver in test_suite_md are run.

    loc_accel_list="ALG_MD5 ALG_RIPEMD160 ALG_SHA_1 \
                    ALG_SHA_224 ALG_SHA_256 ALG_SHA_384 ALG_SHA_512 \
                    ALG_SHA3_224 ALG_SHA3_256 ALG_SHA3_384 ALG_SHA3_512"

    # Start from default config (no USE_PSA)
    helper_libtestdriver1_adjust_config "default"

    helper_libtestdriver1_make_drivers "$loc_accel_list"

    helper_libtestdriver1_make_main "$loc_accel_list"

    msg "test: MBEDTLS_PSA_CRYPTO_CONFIG with accelerated+builtin hash"
    make test
}

# This should be renamed to test and updated once the accelerator ECDH code is in place and ready to test.
component_build_psa_accel_alg_ecdh () {
    msg "build: full - MBEDTLS_USE_PSA_CRYPTO + PSA_WANT_ALG_ECDH without MBEDTLS_ECDH_C"
    scripts/config.py full
    scripts/config.py unset MBEDTLS_USE_PSA_CRYPTO
    scripts/config.py unset MBEDTLS_SSL_PROTO_TLS1_3
    scripts/config.py unset MBEDTLS_ECDH_C
    scripts/config.py unset MBEDTLS_KEY_EXCHANGE_ECDH_RSA_ENABLED
    scripts/config.py unset MBEDTLS_KEY_EXCHANGE_ECDH_ECDSA_ENABLED
    scripts/config.py unset MBEDTLS_KEY_EXCHANGE_ECDHE_ECDSA_ENABLED
    scripts/config.py unset MBEDTLS_KEY_EXCHANGE_ECDHE_RSA_ENABLED
    scripts/config.py unset MBEDTLS_KEY_EXCHANGE_ECDHE_PSK_ENABLED
    # Need to define the correct symbol and include the test driver header path in order to build with the test driver
    make CC=$ASAN_CC CFLAGS="$ASAN_CFLAGS -DPSA_CRYPTO_DRIVER_TEST -DMBEDTLS_PSA_ACCEL_ALG_ECDH -I../tests/include" LDFLAGS="$ASAN_CFLAGS"
}

# This should be renamed to test and updated once the accelerator HMAC code is in place and ready to test.
component_build_psa_accel_alg_hmac () {
    msg "build: full - MBEDTLS_USE_PSA_CRYPTO + PSA_WANT_ALG_HMAC"
    scripts/config.py full
    scripts/config.py unset MBEDTLS_USE_PSA_CRYPTO
    scripts/config.py unset MBEDTLS_SSL_PROTO_TLS1_3
    # Need to define the correct symbol and include the test driver header path in order to build with the test driver
    make CC=$ASAN_CC CFLAGS="$ASAN_CFLAGS -DPSA_CRYPTO_DRIVER_TEST -DMBEDTLS_PSA_ACCEL_ALG_HMAC -I../tests/include" LDFLAGS="$ASAN_CFLAGS"
}

# This should be renamed to test and updated once the accelerator HKDF code is in place and ready to test.
component_build_psa_accel_alg_hkdf () {
    msg "build: full - MBEDTLS_USE_PSA_CRYPTO + PSA_WANT_ALG_HKDF without MBEDTLS_HKDF_C"
    scripts/config.py full
    scripts/config.py unset MBEDTLS_USE_PSA_CRYPTO
    scripts/config.py unset MBEDTLS_HKDF_C
    # Make sure to unset TLS1_3 since it requires HKDF_C and will not build properly without it.
    scripts/config.py unset MBEDTLS_SSL_PROTO_TLS1_3
    # Need to define the correct symbol and include the test driver header path in order to build with the test driver
    make CC=$ASAN_CC CFLAGS="$ASAN_CFLAGS -DPSA_CRYPTO_DRIVER_TEST -DMBEDTLS_PSA_ACCEL_ALG_HKDF -I../tests/include" LDFLAGS="$ASAN_CFLAGS"
}

# This should be renamed to test and updated once the accelerator MD5 code is in place and ready to test.
component_build_psa_accel_alg_md5 () {
    msg "build: full - MBEDTLS_USE_PSA_CRYPTO + PSA_WANT_ALG_MD5 - other hashes"
    scripts/config.py full
    scripts/config.py unset MBEDTLS_USE_PSA_CRYPTO
    scripts/config.py unset MBEDTLS_SSL_PROTO_TLS1_3
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_RIPEMD160
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_SHA_1
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_SHA_224
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_SHA_256
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_SHA_384
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_SHA_512
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_TLS12_ECJPAKE_TO_PMS
    scripts/config.py unset MBEDTLS_LMS_C
    scripts/config.py unset MBEDTLS_LMS_PRIVATE
    # Need to define the correct symbol and include the test driver header path in order to build with the test driver
    make CC=$ASAN_CC CFLAGS="$ASAN_CFLAGS -DPSA_CRYPTO_DRIVER_TEST -DMBEDTLS_PSA_ACCEL_ALG_MD5 -I../tests/include" LDFLAGS="$ASAN_CFLAGS"
}

# This should be renamed to test and updated once the accelerator RIPEMD160 code is in place and ready to test.
component_build_psa_accel_alg_ripemd160 () {
    msg "build: full - MBEDTLS_USE_PSA_CRYPTO + PSA_WANT_ALG_RIPEMD160 - other hashes"
    scripts/config.py full
    scripts/config.py unset MBEDTLS_USE_PSA_CRYPTO
    scripts/config.py unset MBEDTLS_SSL_PROTO_TLS1_3
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_MD5
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_SHA_1
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_SHA_224
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_SHA_256
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_SHA_384
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_SHA_512
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_TLS12_ECJPAKE_TO_PMS
    scripts/config.py unset MBEDTLS_LMS_C
    scripts/config.py unset MBEDTLS_LMS_PRIVATE
    # Need to define the correct symbol and include the test driver header path in order to build with the test driver
    make CC=$ASAN_CC CFLAGS="$ASAN_CFLAGS -DPSA_CRYPTO_DRIVER_TEST -DMBEDTLS_PSA_ACCEL_ALG_RIPEMD160 -I../tests/include" LDFLAGS="$ASAN_CFLAGS"
}

# This should be renamed to test and updated once the accelerator SHA1 code is in place and ready to test.
component_build_psa_accel_alg_sha1 () {
    msg "build: full - MBEDTLS_USE_PSA_CRYPTO + PSA_WANT_ALG_SHA_1 - other hashes"
    scripts/config.py full
    scripts/config.py unset MBEDTLS_USE_PSA_CRYPTO
    scripts/config.py unset MBEDTLS_SSL_PROTO_TLS1_3
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_MD5
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_RIPEMD160
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_SHA_224
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_SHA_256
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_SHA_384
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_SHA_512
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_TLS12_ECJPAKE_TO_PMS
    scripts/config.py unset MBEDTLS_LMS_C
    scripts/config.py unset MBEDTLS_LMS_PRIVATE
    # Need to define the correct symbol and include the test driver header path in order to build with the test driver
    make CC=$ASAN_CC CFLAGS="$ASAN_CFLAGS -DPSA_CRYPTO_DRIVER_TEST -DMBEDTLS_PSA_ACCEL_ALG_SHA_1 -I../tests/include" LDFLAGS="$ASAN_CFLAGS"
}

# This should be renamed to test and updated once the accelerator SHA224 code is in place and ready to test.
component_build_psa_accel_alg_sha224 () {
    msg "build: full - MBEDTLS_USE_PSA_CRYPTO + PSA_WANT_ALG_SHA_224 - other hashes"
    scripts/config.py full
    scripts/config.py unset MBEDTLS_USE_PSA_CRYPTO
    scripts/config.py unset MBEDTLS_SSL_PROTO_TLS1_3
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_MD5
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_RIPEMD160
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_SHA_1
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_SHA_384
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_SHA_512
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_TLS12_ECJPAKE_TO_PMS
    # Need to define the correct symbol and include the test driver header path in order to build with the test driver
    make CC=$ASAN_CC CFLAGS="$ASAN_CFLAGS -DPSA_CRYPTO_DRIVER_TEST -DMBEDTLS_PSA_ACCEL_ALG_SHA_224 -I../tests/include" LDFLAGS="$ASAN_CFLAGS"
}

# This should be renamed to test and updated once the accelerator SHA256 code is in place and ready to test.
component_build_psa_accel_alg_sha256 () {
    msg "build: full - MBEDTLS_USE_PSA_CRYPTO + PSA_WANT_ALG_SHA_256 - other hashes"
    scripts/config.py full
    scripts/config.py unset MBEDTLS_USE_PSA_CRYPTO
    scripts/config.py unset MBEDTLS_SSL_PROTO_TLS1_3
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_MD5
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_RIPEMD160
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_SHA_1
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_SHA_224
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_SHA_384
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_SHA_512
    # Need to define the correct symbol and include the test driver header path in order to build with the test driver
    make CC=$ASAN_CC CFLAGS="$ASAN_CFLAGS -DPSA_CRYPTO_DRIVER_TEST -DMBEDTLS_PSA_ACCEL_ALG_SHA_256 -I../tests/include" LDFLAGS="$ASAN_CFLAGS"
}

# This should be renamed to test and updated once the accelerator SHA384 code is in place and ready to test.
component_build_psa_accel_alg_sha384 () {
    msg "build: full - MBEDTLS_USE_PSA_CRYPTO + PSA_WANT_ALG_SHA_384 - other hashes"
    scripts/config.py full
    scripts/config.py unset MBEDTLS_USE_PSA_CRYPTO
    scripts/config.py unset MBEDTLS_SSL_PROTO_TLS1_3
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_MD5
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_RIPEMD160
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_SHA_1
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_SHA_224
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_SHA_256
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_TLS12_ECJPAKE_TO_PMS
    scripts/config.py unset MBEDTLS_LMS_C
    scripts/config.py unset MBEDTLS_LMS_PRIVATE
    # Need to define the correct symbol and include the test driver header path in order to build with the test driver
    make CC=$ASAN_CC CFLAGS="$ASAN_CFLAGS -DPSA_CRYPTO_DRIVER_TEST -DMBEDTLS_PSA_ACCEL_ALG_SHA_384 -I../tests/include" LDFLAGS="$ASAN_CFLAGS"
}

# This should be renamed to test and updated once the accelerator SHA512 code is in place and ready to test.
component_build_psa_accel_alg_sha512 () {
    msg "build: full - MBEDTLS_USE_PSA_CRYPTO + PSA_WANT_ALG_SHA_512 - other hashes"
    scripts/config.py full
    scripts/config.py unset MBEDTLS_USE_PSA_CRYPTO
    scripts/config.py unset MBEDTLS_SSL_PROTO_TLS1_3
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_MD5
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_RIPEMD160
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_SHA_1
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_SHA_224
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_SHA_256
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_SHA_384
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_TLS12_ECJPAKE_TO_PMS
    scripts/config.py unset MBEDTLS_LMS_C
    scripts/config.py unset MBEDTLS_LMS_PRIVATE
    # Need to define the correct symbol and include the test driver header path in order to build with the test driver
    make CC=$ASAN_CC CFLAGS="$ASAN_CFLAGS -DPSA_CRYPTO_DRIVER_TEST -DMBEDTLS_PSA_ACCEL_ALG_SHA_512 -I../tests/include" LDFLAGS="$ASAN_CFLAGS"
}

# This should be renamed to test and updated once the accelerator RSA code is in place and ready to test.
component_build_psa_accel_alg_rsa_pkcs1v15_crypt () {
    msg "build: full - MBEDTLS_USE_PSA_CRYPTO + PSA_WANT_ALG_RSA_PKCS1V15_CRYPT + PSA_WANT_KEY_TYPE_RSA_PUBLIC_KEY"
    scripts/config.py full
    scripts/config.py unset MBEDTLS_USE_PSA_CRYPTO
    scripts/config.py unset MBEDTLS_SSL_PROTO_TLS1_3
    scripts/config.py -f "$CRYPTO_CONFIG_H" set PSA_WANT_ALG_RSA_PKCS1V15_CRYPT 1
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_RSA_PKCS1V15_SIGN
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_RSA_OAEP
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_RSA_PSS
    # Need to define the correct symbol and include the test driver header path in order to build with the test driver
    make CC=$ASAN_CC CFLAGS="$ASAN_CFLAGS -DPSA_CRYPTO_DRIVER_TEST -DMBEDTLS_PSA_ACCEL_ALG_RSA_PKCS1V15_CRYPT -I../tests/include" LDFLAGS="$ASAN_CFLAGS"
}

# This should be renamed to test and updated once the accelerator RSA code is in place and ready to test.
component_build_psa_accel_alg_rsa_pkcs1v15_sign () {
    msg "build: full - MBEDTLS_USE_PSA_CRYPTO + PSA_WANT_ALG_RSA_PKCS1V15_SIGN + PSA_WANT_KEY_TYPE_RSA_PUBLIC_KEY"
    scripts/config.py full
    scripts/config.py unset MBEDTLS_USE_PSA_CRYPTO
    scripts/config.py unset MBEDTLS_SSL_PROTO_TLS1_3
    scripts/config.py -f "$CRYPTO_CONFIG_H" set PSA_WANT_ALG_RSA_PKCS1V15_SIGN 1
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_RSA_PKCS1V15_CRYPT
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_RSA_OAEP
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_RSA_PSS
    # Need to define the correct symbol and include the test driver header path in order to build with the test driver
    make CC=$ASAN_CC CFLAGS="$ASAN_CFLAGS -DPSA_CRYPTO_DRIVER_TEST -DMBEDTLS_PSA_ACCEL_ALG_RSA_PKCS1V15_SIGN -I../tests/include" LDFLAGS="$ASAN_CFLAGS"
}

# This should be renamed to test and updated once the accelerator RSA code is in place and ready to test.
component_build_psa_accel_alg_rsa_oaep () {
    msg "build: full - MBEDTLS_USE_PSA_CRYPTO + PSA_WANT_ALG_RSA_OAEP + PSA_WANT_KEY_TYPE_RSA_PUBLIC_KEY"
    scripts/config.py full
    scripts/config.py unset MBEDTLS_USE_PSA_CRYPTO
    scripts/config.py unset MBEDTLS_SSL_PROTO_TLS1_3
    scripts/config.py -f "$CRYPTO_CONFIG_H" set PSA_WANT_ALG_RSA_OAEP 1
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_RSA_PKCS1V15_CRYPT
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_RSA_PKCS1V15_SIGN
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_RSA_PSS
    # Need to define the correct symbol and include the test driver header path in order to build with the test driver
    make CC=$ASAN_CC CFLAGS="$ASAN_CFLAGS -DPSA_CRYPTO_DRIVER_TEST -DMBEDTLS_PSA_ACCEL_ALG_RSA_OAEP -I../tests/include" LDFLAGS="$ASAN_CFLAGS"
}

# This should be renamed to test and updated once the accelerator RSA code is in place and ready to test.
component_build_psa_accel_alg_rsa_pss () {
    msg "build: full - MBEDTLS_USE_PSA_CRYPTO + PSA_WANT_ALG_RSA_PSS + PSA_WANT_KEY_TYPE_RSA_PUBLIC_KEY"
    scripts/config.py full
    scripts/config.py unset MBEDTLS_USE_PSA_CRYPTO
    scripts/config.py unset MBEDTLS_SSL_PROTO_TLS1_3
    scripts/config.py -f "$CRYPTO_CONFIG_H" set PSA_WANT_ALG_RSA_PSS 1
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_RSA_PKCS1V15_CRYPT
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_RSA_PKCS1V15_SIGN
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_RSA_OAEP
    # Need to define the correct symbol and include the test driver header path in order to build with the test driver
    make CC=$ASAN_CC CFLAGS="$ASAN_CFLAGS -DPSA_CRYPTO_DRIVER_TEST -DMBEDTLS_PSA_ACCEL_ALG_RSA_PSS -I../tests/include" LDFLAGS="$ASAN_CFLAGS"
}

# This should be renamed to test and updated once the accelerator RSA code is in place and ready to test.
component_build_psa_accel_key_type_rsa_key_pair () {
    msg "build: full - MBEDTLS_USE_PSA_CRYPTO + PSA_WANT_KEY_TYPE_RSA_KEY_PAIR_xxx + PSA_WANT_ALG_RSA_PSS"
    scripts/config.py full
    scripts/config.py unset MBEDTLS_USE_PSA_CRYPTO
    scripts/config.py unset MBEDTLS_SSL_PROTO_TLS1_3
    scripts/config.py -f "$CRYPTO_CONFIG_H" set PSA_WANT_ALG_RSA_PSS 1
    scripts/config.py -f "$CRYPTO_CONFIG_H" set PSA_WANT_KEY_TYPE_RSA_KEY_PAIR_BASIC 1
    scripts/config.py -f "$CRYPTO_CONFIG_H" set PSA_WANT_KEY_TYPE_RSA_KEY_PAIR_IMPORT 1
    scripts/config.py -f "$CRYPTO_CONFIG_H" set PSA_WANT_KEY_TYPE_RSA_KEY_PAIR_EXPORT 1
    scripts/config.py -f "$CRYPTO_CONFIG_H" set PSA_WANT_KEY_TYPE_RSA_KEY_PAIR_GENERATE 1
    # Need to define the correct symbol and include the test driver header path in order to build with the test driver
    make CC=$ASAN_CC CFLAGS="$ASAN_CFLAGS -DPSA_CRYPTO_DRIVER_TEST -DMBEDTLS_PSA_ACCEL_KEY_TYPE_RSA_KEY_PAIR -I../tests/include" LDFLAGS="$ASAN_CFLAGS"
}

# This should be renamed to test and updated once the accelerator RSA code is in place and ready to test.
component_build_psa_accel_key_type_rsa_public_key () {
    msg "build: full - MBEDTLS_USE_PSA_CRYPTO + PSA_WANT_KEY_TYPE_RSA_PUBLIC_KEY + PSA_WANT_ALG_RSA_PSS"
    scripts/config.py full
    scripts/config.py unset MBEDTLS_USE_PSA_CRYPTO
    scripts/config.py unset MBEDTLS_SSL_PROTO_TLS1_3
    scripts/config.py -f "$CRYPTO_CONFIG_H" set PSA_WANT_ALG_RSA_PSS 1
    scripts/config.py -f "$CRYPTO_CONFIG_H" set PSA_WANT_KEY_TYPE_RSA_PUBLIC_KEY 1
    # Need to define the correct symbol and include the test driver header path in order to build with the test driver
    make CC=$ASAN_CC CFLAGS="$ASAN_CFLAGS -DPSA_CRYPTO_DRIVER_TEST -DMBEDTLS_PSA_ACCEL_KEY_TYPE_RSA_PUBLIC_KEY -I../tests/include" LDFLAGS="$ASAN_CFLAGS"
}

# Auxiliary function to build config for hashes with and without drivers
config_psa_crypto_hash_use_psa () {
    driver_only="$1"
    # start with config full for maximum coverage (also enables USE_PSA)
    helper_libtestdriver1_adjust_config "full"
    if [ "$driver_only" -eq 1 ]; then
        # disable the built-in implementation of hashes
        scripts/config.py unset MBEDTLS_MD5_C
        scripts/config.py unset MBEDTLS_RIPEMD160_C
        scripts/config.py unset MBEDTLS_SHA1_C
        scripts/config.py unset MBEDTLS_SHA224_C
        scripts/config.py unset MBEDTLS_SHA256_C # see external RNG below
        scripts/config.py unset MBEDTLS_SHA256_USE_ARMV8_A_CRYPTO_IF_PRESENT
        scripts/config.py unset MBEDTLS_SHA384_C
        scripts/config.py unset MBEDTLS_SHA512_C
        scripts/config.py unset MBEDTLS_SHA512_USE_A64_CRYPTO_IF_PRESENT
        scripts/config.py unset MBEDTLS_SHA3_C
    fi
}

# Note that component_test_psa_crypto_config_reference_hash_use_psa
# is related to this component and both components need to be kept in sync.
# For details please see comments for component_test_psa_crypto_config_reference_hash_use_psa.
component_test_psa_crypto_config_accel_hash_use_psa () {
    msg "test: full with accelerated hashes"

    loc_accel_list="ALG_MD5 ALG_RIPEMD160 ALG_SHA_1 \
                    ALG_SHA_224 ALG_SHA_256 ALG_SHA_384 ALG_SHA_512 \
                    ALG_SHA3_224 ALG_SHA3_256 ALG_SHA3_384 ALG_SHA3_512"

    # Configure
    # ---------

    config_psa_crypto_hash_use_psa 1

    # Build
    # -----

    helper_libtestdriver1_make_drivers "$loc_accel_list"

    helper_libtestdriver1_make_main "$loc_accel_list"

    # There's a risk of something getting re-enabled via config_psa.h;
    # make sure it did not happen. Note: it's OK for MD_C to be enabled.
    not grep mbedtls_md5 library/md5.o
    not grep mbedtls_sha1 library/sha1.o
    not grep mbedtls_sha256 library/sha256.o
    not grep mbedtls_sha512 library/sha512.o
    not grep mbedtls_ripemd160 library/ripemd160.o

    # Run the tests
    # -------------

    msg "test: full with accelerated hashes"
    make test

    # This is mostly useful so that we can later compare outcome files with
    # the reference config in analyze_outcomes.py, to check that the
    # dependency declarations in ssl-opt.sh and in TLS code are correct.
    msg "test: ssl-opt.sh, full with accelerated hashes"
    tests/ssl-opt.sh

    # This is to make sure all ciphersuites are exercised, but we don't need
    # interop testing (besides, we already got some from ssl-opt.sh).
    msg "test: compat.sh, full with accelerated hashes"
    tests/compat.sh -p mbedTLS -V YES
}

# This component provides reference configuration for test_psa_crypto_config_accel_hash_use_psa
# without accelerated hash. The outcome from both components are used by the analyze_outcomes.py
# script to find regression in test coverage when accelerated hash is used (tests and ssl-opt).
# Both components need to be kept in sync.
component_test_psa_crypto_config_reference_hash_use_psa () {
    msg "test: full without accelerated hashes"

    config_psa_crypto_hash_use_psa 0

    make

    msg "test: full without accelerated hashes"
    make test

    msg "test: ssl-opt.sh, full without accelerated hashes"
    tests/ssl-opt.sh
}

# Auxiliary function to build config for hashes with and without drivers
config_psa_crypto_hmac_use_psa () {
    driver_only="$1"
    # start with config full for maximum coverage (also enables USE_PSA)
    helper_libtestdriver1_adjust_config "full"

    if [ "$driver_only" -eq 1 ]; then
        # Disable MD_C in order to disable the builtin support for HMAC. MD_LIGHT
        # is still enabled though (for ENTROPY_C among others).
        scripts/config.py unset MBEDTLS_MD_C
        # Disable also the builtin hashes since they are supported by the driver
        # and MD module is able to perform PSA dispathing.
        scripts/config.py unset-all MBEDTLS_SHA
        scripts/config.py unset MBEDTLS_MD5_C
        scripts/config.py unset MBEDTLS_RIPEMD160_C
    fi

    # Direct dependencies of MD_C. We disable them also in the reference
    # component to work with the same set of features.
    scripts/config.py unset MBEDTLS_PKCS7_C
    scripts/config.py unset MBEDTLS_PKCS5_C
    scripts/config.py unset MBEDTLS_HMAC_DRBG_C
    scripts/config.py unset MBEDTLS_HKDF_C
    # Dependencies of HMAC_DRBG
    scripts/config.py unset MBEDTLS_ECDSA_DETERMINISTIC
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_DETERMINISTIC_ECDSA
}

component_test_psa_crypto_config_accel_hmac () {
    msg "test: full with accelerated hmac"

    loc_accel_list="ALG_HMAC KEY_TYPE_HMAC \
                    ALG_MD5 ALG_RIPEMD160 ALG_SHA_1 \
                    ALG_SHA_224 ALG_SHA_256 ALG_SHA_384 ALG_SHA_512 \
                    ALG_SHA3_224 ALG_SHA3_256 ALG_SHA3_384 ALG_SHA3_512"

    # Configure
    # ---------

    config_psa_crypto_hmac_use_psa 1

    # Build
    # -----

    helper_libtestdriver1_make_drivers "$loc_accel_list"

    helper_libtestdriver1_make_main "$loc_accel_list"

    # Ensure that built-in support for HMAC is disabled.
    not grep mbedtls_md_hmac library/md.o

    # Run the tests
    # -------------

    msg "test: full with accelerated hmac"
    make test
}

component_test_psa_crypto_config_reference_hmac () {
    msg "test: full without accelerated hmac"

    config_psa_crypto_hmac_use_psa 0

    make

    msg "test: full without accelerated hmac"
    make test
}

component_test_psa_crypto_config_accel_des () {
    msg "test: MBEDTLS_PSA_CRYPTO_CONFIG with accelerated DES"

    # Albeit this components aims at accelerating DES which should only support
    # CBC and ECB modes, we need to accelerate more than that otherwise DES_C
    # would automatically be re-enabled by "config_adjust_legacy_from_psa.c"
    loc_accel_list="ALG_ECB_NO_PADDING ALG_CBC_NO_PADDING ALG_CBC_PKCS7 \
                    ALG_CTR ALG_CFB ALG_OFB ALG_XTS ALG_CMAC \
                    KEY_TYPE_DES"

    # Note: we cannot accelerate all ciphers' key types otherwise we would also
    # have to either disable CCM/GCM or accelerate them, but that's out of scope
    # of this component. This limitation will be addressed by #8598.

    # Configure
    # ---------

    # Start from the full config
    helper_libtestdriver1_adjust_config "full"

    # Disable the things that are being accelerated
    scripts/config.py unset MBEDTLS_CIPHER_MODE_CBC
    scripts/config.py unset MBEDTLS_CIPHER_PADDING_PKCS7
    scripts/config.py unset MBEDTLS_CIPHER_MODE_CTR
    scripts/config.py unset MBEDTLS_CIPHER_MODE_CFB
    scripts/config.py unset MBEDTLS_CIPHER_MODE_OFB
    scripts/config.py unset MBEDTLS_CIPHER_MODE_XTS
    scripts/config.py unset MBEDTLS_DES_C
    scripts/config.py unset MBEDTLS_CMAC_C

    # Build
    # -----

    helper_libtestdriver1_make_drivers "$loc_accel_list"

    helper_libtestdriver1_make_main "$loc_accel_list"

    # Make sure this was not re-enabled by accident (additive config)
    not grep mbedtls_des* library/des.o

    # Run the tests
    # -------------

    msg "test: MBEDTLS_PSA_CRYPTO_CONFIG with accelerated DES"
    make test
}

component_test_psa_crypto_config_accel_aead () {
    msg "test: MBEDTLS_PSA_CRYPTO_CONFIG with accelerated AEAD"

    loc_accel_list="ALG_GCM ALG_CCM ALG_CHACHA20_POLY1305 \
                    KEY_TYPE_AES KEY_TYPE_CHACHA20 KEY_TYPE_ARIA KEY_TYPE_CAMELLIA"

    # Configure
    # ---------

    # Start from full config
    helper_libtestdriver1_adjust_config "full"

    # Disable things that are being accelerated
    scripts/config.py unset MBEDTLS_GCM_C
    scripts/config.py unset MBEDTLS_CCM_C
    scripts/config.py unset MBEDTLS_CHACHAPOLY_C

    # Disable CCM_STAR_NO_TAG because this re-enables CCM_C.
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_CCM_STAR_NO_TAG

    # Build
    # -----

    helper_libtestdriver1_make_drivers "$loc_accel_list"

    helper_libtestdriver1_make_main "$loc_accel_list"

    # Make sure this was not re-enabled by accident (additive config)
    not grep mbedtls_ccm library/ccm.o
    not grep mbedtls_gcm library/gcm.o
    not grep mbedtls_chachapoly library/chachapoly.o

    # Run the tests
    # -------------

    msg "test: MBEDTLS_PSA_CRYPTO_CONFIG with accelerated AEAD"
    make test
}

# This is a common configuration function used in:
# - component_test_psa_crypto_config_accel_cipher_aead_cmac
# - component_test_psa_crypto_config_reference_cipher_aead_cmac
common_psa_crypto_config_accel_cipher_aead_cmac () {
    # Start from the full config
    helper_libtestdriver1_adjust_config "full"

    scripts/config.py unset MBEDTLS_NIST_KW_C
}

# The 2 following test components, i.e.
# - component_test_psa_crypto_config_accel_cipher_aead_cmac
# - component_test_psa_crypto_config_reference_cipher_aead_cmac
# are meant to be used together in analyze_outcomes.py script in order to test
# driver's coverage for ciphers and AEADs.
component_test_psa_crypto_config_accel_cipher_aead_cmac () {
    msg "build: full config with accelerated cipher inc. AEAD and CMAC"

    loc_accel_list="ALG_ECB_NO_PADDING ALG_CBC_NO_PADDING ALG_CBC_PKCS7 ALG_CTR ALG_CFB \
                    ALG_OFB ALG_XTS ALG_STREAM_CIPHER ALG_CCM_STAR_NO_TAG \
                    ALG_GCM ALG_CCM ALG_CHACHA20_POLY1305 ALG_CMAC \
                    KEY_TYPE_DES KEY_TYPE_AES KEY_TYPE_ARIA KEY_TYPE_CHACHA20 KEY_TYPE_CAMELLIA"

    # Configure
    # ---------

    common_psa_crypto_config_accel_cipher_aead_cmac

    # Disable the things that are being accelerated
    scripts/config.py unset MBEDTLS_CIPHER_MODE_CBC
    scripts/config.py unset MBEDTLS_CIPHER_PADDING_PKCS7
    scripts/config.py unset MBEDTLS_CIPHER_MODE_CTR
    scripts/config.py unset MBEDTLS_CIPHER_MODE_CFB
    scripts/config.py unset MBEDTLS_CIPHER_MODE_OFB
    scripts/config.py unset MBEDTLS_CIPHER_MODE_XTS
    scripts/config.py unset MBEDTLS_GCM_C
    scripts/config.py unset MBEDTLS_CCM_C
    scripts/config.py unset MBEDTLS_CHACHAPOLY_C
    scripts/config.py unset MBEDTLS_CMAC_C
    scripts/config.py unset MBEDTLS_DES_C
    scripts/config.py unset MBEDTLS_AES_C
    scripts/config.py unset MBEDTLS_ARIA_C
    scripts/config.py unset MBEDTLS_CHACHA20_C
    scripts/config.py unset MBEDTLS_CAMELLIA_C

    # Disable CIPHER_C entirely as all ciphers/AEADs are accelerated and PSA
    # does not depend on it.
    scripts/config.py unset MBEDTLS_CIPHER_C

    # Build
    # -----

    helper_libtestdriver1_make_drivers "$loc_accel_list"

    helper_libtestdriver1_make_main "$loc_accel_list"

    # Make sure this was not re-enabled by accident (additive config)
    not grep mbedtls_cipher library/cipher.o
    not grep mbedtls_des library/des.o
    not grep mbedtls_aes library/aes.o
    not grep mbedtls_aria library/aria.o
    not grep mbedtls_camellia library/camellia.o
    not grep mbedtls_ccm library/ccm.o
    not grep mbedtls_gcm library/gcm.o
    not grep mbedtls_chachapoly library/chachapoly.o
    not grep mbedtls_cmac library/cmac.o

    # Run the tests
    # -------------

    msg "test: full config with accelerated cipher inc. AEAD and CMAC"
    make test

    msg "ssl-opt: full config with accelerated cipher inc. AEAD and CMAC"
    tests/ssl-opt.sh

    msg "compat.sh: full config with accelerated cipher inc. AEAD and CMAC"
    tests/compat.sh -V NO -p mbedTLS
}

component_test_psa_crypto_config_reference_cipher_aead_cmac () {
    msg "build: full config with non-accelerated cipher inc. AEAD and CMAC"
    common_psa_crypto_config_accel_cipher_aead_cmac

    make

    msg "test: full config with non-accelerated cipher inc. AEAD and CMAC"
    make test

    msg "ssl-opt: full config with non-accelerated cipher inc. AEAD and CMAC"
    tests/ssl-opt.sh

    msg "compat.sh: full config with non-accelerated cipher inc. AEAD and CMAC"
    tests/compat.sh -V NO -p mbedTLS
}

common_block_cipher_dispatch () {
    TEST_WITH_DRIVER="$1"

    # Start from the full config
    helper_libtestdriver1_adjust_config "full"

    if [ "$TEST_WITH_DRIVER" -eq 1 ]; then
        # Disable key types that are accelerated (there is no legacy equivalent
        # symbol for ECB)
        scripts/config.py unset MBEDTLS_AES_C
        scripts/config.py unset MBEDTLS_ARIA_C
        scripts/config.py unset MBEDTLS_CAMELLIA_C
    fi

    # Disable cipher's modes that, when not accelerated, cause
    # legacy key types to be re-enabled in "config_adjust_legacy_from_psa.h".
    # Keep this also in the reference component in order to skip the same tests
    # that were skipped in the accelerated one.
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_CTR
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_CFB
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_OFB
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_CBC_NO_PADDING
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_CBC_PKCS7
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_CMAC
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_CCM_STAR_NO_TAG
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_PBKDF2_AES_CMAC_PRF_128

    # Disable direct dependency on AES_C
    scripts/config.py unset MBEDTLS_NIST_KW_C

    # Prevent the cipher module from using deprecated PSA path. The reason is
    # that otherwise there will be tests relying on "aes_info" (defined in
    # "cipher_wrap.c") whose functions are not available when AES_C is
    # not defined. ARIA and Camellia are not a problem in this case because
    # the PSA path is not tested for these key types.
    scripts/config.py set MBEDTLS_DEPRECATED_REMOVED
}

component_test_full_block_cipher_psa_dispatch_static_keystore () {
    msg "build: full + PSA dispatch in block_cipher with static keystore"
    # Check that the static key store works well when CTR_DRBG uses a
    # PSA key for AES.
    scripts/config.py unset MBEDTLS_PSA_KEY_STORE_DYNAMIC

    loc_accel_list="ALG_ECB_NO_PADDING \
                    KEY_TYPE_AES KEY_TYPE_ARIA KEY_TYPE_CAMELLIA"

    # Configure
    # ---------

    common_block_cipher_dispatch 1

    # Build
    # -----

    helper_libtestdriver1_make_drivers "$loc_accel_list"

    helper_libtestdriver1_make_main "$loc_accel_list"

    # Make sure disabled components were not re-enabled by accident (additive
    # config)
    not grep mbedtls_aes_ library/aes.o
    not grep mbedtls_aria_ library/aria.o
    not grep mbedtls_camellia_ library/camellia.o

    # Run the tests
    # -------------

    msg "test: full + PSA dispatch in block_cipher with static keystore"
    make test
}

component_test_full_block_cipher_psa_dispatch () {
    msg "build: full + PSA dispatch in block_cipher"

    loc_accel_list="ALG_ECB_NO_PADDING \
                    KEY_TYPE_AES KEY_TYPE_ARIA KEY_TYPE_CAMELLIA"

    # Configure
    # ---------

    common_block_cipher_dispatch 1

    # Build
    # -----

    helper_libtestdriver1_make_drivers "$loc_accel_list"

    helper_libtestdriver1_make_main "$loc_accel_list"

    # Make sure disabled components were not re-enabled by accident (additive
    # config)
    not grep mbedtls_aes_ library/aes.o
    not grep mbedtls_aria_ library/aria.o
    not grep mbedtls_camellia_ library/camellia.o

    # Run the tests
    # -------------

    msg "test: full + PSA dispatch in block_cipher"
    make test
}

# This is the reference component of component_test_full_block_cipher_psa_dispatch
component_test_full_block_cipher_legacy_dispatch () {
    msg "build: full + legacy dispatch in block_cipher"

    common_block_cipher_dispatch 0

    make

    msg "test: full + legacy dispatch in block_cipher"
    make test
}

component_test_aead_chachapoly_disabled () {
    msg "build: full minus CHACHAPOLY"
    scripts/config.py full
    scripts/config.py unset MBEDTLS_CHACHAPOLY_C
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_CHACHA20_POLY1305
    make CC=$ASAN_CC CFLAGS="$ASAN_CFLAGS" LDFLAGS="$ASAN_CFLAGS"

    msg "test: full minus CHACHAPOLY"
    make test
}

component_test_aead_only_ccm () {
    msg "build: full minus CHACHAPOLY and GCM"
    scripts/config.py full
    scripts/config.py unset MBEDTLS_CHACHAPOLY_C
    scripts/config.py unset MBEDTLS_GCM_C
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_CHACHA20_POLY1305
    scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_GCM
    make CC=$ASAN_CC CFLAGS="$ASAN_CFLAGS" LDFLAGS="$ASAN_CFLAGS"

    msg "test: full minus CHACHAPOLY and GCM"
    make test
}

component_test_ccm_aes_sha256 () {
    msg "build: CCM + AES + SHA256 configuration"

    cp "$CONFIG_TEST_DRIVER_H" "$CONFIG_H"
    cp configs/crypto-config-ccm-aes-sha256.h "$CRYPTO_CONFIG_H"

    make

    msg "test: CCM + AES + SHA256 configuration"
    make test
}

# Test that the given .o file builds with all (valid) combinations of the given options.
#
# Syntax: build_test_config_combos FILE VALIDATOR_FUNCTION OPT1 OPT2 ...
#
# The validator function is the name of a function to validate the combination of options.
# It may be "" if all combinations are valid.
# It receives a string containing a combination of options, as passed to the compiler,
# e.g. "-DOPT1 -DOPT2 ...". It must return 0 iff the combination is valid, non-zero if invalid.
build_test_config_combos () {
    file=$1
    shift
    validate_options=$1
    shift
    options=("$@")

    # clear all of the options so that they can be overridden on the clang commandline
    for opt in "${options[@]}"; do
        ./scripts/config.py unset ${opt}
    done

    # enter the directory containing the target file & strip the dir from the filename
    cd $(dirname ${file})
    file=$(basename ${file})

    # The most common issue is unused variables/functions, so ensure -Wunused is set.
    warning_flags="-Werror -Wall -Wextra -Wwrite-strings -Wpointer-arith -Wimplicit-fallthrough -Wshadow -Wvla -Wformat=2 -Wno-format-nonliteral -Wshadow -Wasm-operand-widths -Wunused"

    # Extract the command generated by the Makefile to build the target file.
    # This ensures that we have any include paths, macro definitions, etc
    # that may be applied by make.
    # Add -fsyntax-only as we only want a syntax check and don't need to generate a file.
    compile_cmd="clang \$(LOCAL_CFLAGS) ${warning_flags} -fsyntax-only -c"

    makefile=$(TMPDIR=. mktemp)
    deps=""

    len=${#options[@]}
    source_file=${file%.o}.c

    targets=0
    echo 'include Makefile' >${makefile}

    for ((i = 0; i < $((2**${len})); i++)); do
        # generate each of 2^n combinations of options
        # each bit of $i is used to determine if options[i] will be set or not
        target="t"
        clang_args=""
        for ((j = 0; j < ${len}; j++)); do
            if (((i >> j) & 1)); then
                opt=-D${options[$j]}
                clang_args="${clang_args} ${opt}"
                target="${target}${opt}"
            fi
        done

        # if combination is not known to be invalid, add it to the makefile
        if [[ -z $validate_options ]] || $validate_options "${clang_args}"; then
            cmd="${compile_cmd} ${clang_args}"
            echo "${target}: ${source_file}; $cmd ${source_file}" >> ${makefile}

            deps="${deps} ${target}"
            ((++targets))
        fi
    done

    echo "build_test_config_combos: ${deps}" >> ${makefile}

    # execute all of the commands via Make (probably in parallel)
    make -s -f ${makefile} build_test_config_combos
    echo "$targets targets checked"

    # clean up the temporary makefile
    rm ${makefile}
}

validate_aes_config_variations () {
    if [[ "$1" == *"MBEDTLS_AES_USE_HARDWARE_ONLY"* ]]; then
        if [[ "$1" == *"MBEDTLS_PADLOCK_C"* ]]; then
            return 1
        fi
        if [[ !(("$HOSTTYPE" == "aarch64" && "$1" != *"MBEDTLS_AESCE_C"*) || \
                ("$HOSTTYPE" == "x86_64"  && "$1" != *"MBEDTLS_AESNI_C"*)) ]]; then
            return 1
        fi
    fi
    return 0
}

component_build_aes_variations () {
    # 18s - around 90ms per clang invocation on M1 Pro
    #
    # aes.o has many #if defined(...) guards that intersect in complex ways.
    # Test that all the combinations build cleanly.

    MBEDTLS_ROOT_DIR="$PWD"
    msg "build: aes.o for all combinations of relevant config options"

    build_test_config_combos library/aes.o validate_aes_config_variations \
        "MBEDTLS_AES_SETKEY_ENC_ALT" "MBEDTLS_AES_DECRYPT_ALT" \
        "MBEDTLS_AES_ROM_TABLES" "MBEDTLS_AES_ENCRYPT_ALT" "MBEDTLS_AES_SETKEY_DEC_ALT" \
        "MBEDTLS_AES_FEWER_TABLES" "MBEDTLS_PADLOCK_C" "MBEDTLS_AES_USE_HARDWARE_ONLY" \
        "MBEDTLS_AESNI_C" "MBEDTLS_AESCE_C" "MBEDTLS_AES_ONLY_128_BIT_KEY_LENGTH"

    cd "$MBEDTLS_ROOT_DIR"
    msg "build: aes.o for all combinations of relevant config options + BLOCK_CIPHER_NO_DECRYPT"

    # MBEDTLS_BLOCK_CIPHER_NO_DECRYPT is incompatible with ECB in PSA, CBC/XTS/NIST_KW/DES,
    # manually set or unset those configurations to check
    # MBEDTLS_BLOCK_CIPHER_NO_DECRYPT with various combinations in aes.o.
    scripts/config.py set MBEDTLS_BLOCK_CIPHER_NO_DECRYPT
    scripts/config.py unset MBEDTLS_CIPHER_MODE_CBC
    scripts/config.py unset MBEDTLS_CIPHER_MODE_XTS
    scripts/config.py unset MBEDTLS_DES_C
    scripts/config.py unset MBEDTLS_NIST_KW_C
    build_test_config_combos library/aes.o validate_aes_config_variations \
        "MBEDTLS_AES_SETKEY_ENC_ALT" "MBEDTLS_AES_DECRYPT_ALT" \
        "MBEDTLS_AES_ROM_TABLES" "MBEDTLS_AES_ENCRYPT_ALT" "MBEDTLS_AES_SETKEY_DEC_ALT" \
        "MBEDTLS_AES_FEWER_TABLES" "MBEDTLS_PADLOCK_C" "MBEDTLS_AES_USE_HARDWARE_ONLY" \
        "MBEDTLS_AESNI_C" "MBEDTLS_AESCE_C" "MBEDTLS_AES_ONLY_128_BIT_KEY_LENGTH"
}

component_test_sha3_variations () {
    msg "sha3 loop unroll variations"

    # define minimal config sufficient to test SHA3
    cat > include/mbedtls/mbedtls_config.h << END
        #define MBEDTLS_SELF_TEST
        #define MBEDTLS_SHA3_C
END

    msg "all loops unrolled"
    make clean
    make -C tests test_suite_shax CFLAGS="-DMBEDTLS_SHA3_THETA_UNROLL=1 -DMBEDTLS_SHA3_PI_UNROLL=1 -DMBEDTLS_SHA3_CHI_UNROLL=1 -DMBEDTLS_SHA3_RHO_UNROLL=1"
    ./tests/test_suite_shax

    msg "all loops rolled up"
    make clean
    make -C tests test_suite_shax CFLAGS="-DMBEDTLS_SHA3_THETA_UNROLL=0 -DMBEDTLS_SHA3_PI_UNROLL=0 -DMBEDTLS_SHA3_CHI_UNROLL=0 -DMBEDTLS_SHA3_RHO_UNROLL=0"
    ./tests/test_suite_shax
}

# For timebeing, no aarch64 gcc available in CI and no arm64 CI node.
component_build_aes_aesce_armcc () {
    msg "Build: AESCE test on arm64 platform without plain C."
    scripts/config.py baremetal

    # armc[56] don't support SHA-512 intrinsics
    scripts/config.py unset MBEDTLS_SHA512_USE_A64_CRYPTO_IF_PRESENT

    # Stop armclang warning about feature detection for A64_CRYPTO.
    # With this enabled, the library does build correctly under armclang,
    # but in baremetal builds (as tested here), feature detection is
    # unavailable, and the user is notified via a #warning. So enabling
    # this feature would prevent us from building with -Werror on
    # armclang. Tracked in #7198.
    scripts/config.py unset MBEDTLS_SHA256_USE_ARMV8_A_CRYPTO_IF_PRESENT
    scripts/config.py set MBEDTLS_HAVE_ASM

    msg "AESCE, build with default configuration."
    scripts/config.py set MBEDTLS_AESCE_C
    scripts/config.py unset MBEDTLS_AES_USE_HARDWARE_ONLY
    armc6_build_test "-O1 --target=aarch64-arm-none-eabi -march=armv8-a+crypto"

    msg "AESCE, build AESCE only"
    scripts/config.py set MBEDTLS_AESCE_C
    scripts/config.py set MBEDTLS_AES_USE_HARDWARE_ONLY
    armc6_build_test "-O1 --target=aarch64-arm-none-eabi -march=armv8-a+crypto"
}

support_build_aes_aesce_armcc () {
    support_build_armcc
}

component_test_aes_only_128_bit_keys () {
    msg "build: default config + AES_ONLY_128_BIT_KEY_LENGTH"
    scripts/config.py set MBEDTLS_AES_ONLY_128_BIT_KEY_LENGTH
    scripts/config.py unset MBEDTLS_PADLOCK_C

    make CFLAGS='-O2 -Werror -Wall -Wextra'

    msg "test: default config + AES_ONLY_128_BIT_KEY_LENGTH"
    make test
}

component_test_no_ctr_drbg_aes_only_128_bit_keys () {
    msg "build: default config + AES_ONLY_128_BIT_KEY_LENGTH - CTR_DRBG_C"
    scripts/config.py set MBEDTLS_AES_ONLY_128_BIT_KEY_LENGTH
    scripts/config.py unset MBEDTLS_CTR_DRBG_C
    scripts/config.py unset MBEDTLS_PADLOCK_C

    make CC=clang CFLAGS='-Werror -Wall -Wextra'

    msg "test: default config + AES_ONLY_128_BIT_KEY_LENGTH - CTR_DRBG_C"
    make test
}

component_test_aes_only_128_bit_keys_have_builtins () {
    msg "build: default config + AES_ONLY_128_BIT_KEY_LENGTH - AESNI_C - AESCE_C"
    scripts/config.py set MBEDTLS_AES_ONLY_128_BIT_KEY_LENGTH
    scripts/config.py unset MBEDTLS_PADLOCK_C
    scripts/config.py unset MBEDTLS_AESNI_C
    scripts/config.py unset MBEDTLS_AESCE_C

    make CFLAGS='-O2 -Werror -Wall -Wextra'

    msg "test: default config + AES_ONLY_128_BIT_KEY_LENGTH - AESNI_C - AESCE_C"
    make test

    msg "selftest: default config + AES_ONLY_128_BIT_KEY_LENGTH - AESNI_C - AESCE_C"
    programs/test/selftest
}

component_test_gcm_largetable () {
    msg "build: default config + GCM_LARGE_TABLE - AESNI_C - AESCE_C"
    scripts/config.py set MBEDTLS_GCM_LARGE_TABLE
    scripts/config.py unset MBEDTLS_PADLOCK_C
    scripts/config.py unset MBEDTLS_AESNI_C
    scripts/config.py unset MBEDTLS_AESCE_C

    make CFLAGS='-O2 -Werror -Wall -Wextra'

    msg "test: default config - GCM_LARGE_TABLE - AESNI_C - AESCE_C"
    make test
}

component_test_aes_fewer_tables () {
    msg "build: default config with AES_FEWER_TABLES enabled"
    scripts/config.py set MBEDTLS_AES_FEWER_TABLES
    make CFLAGS='-O2 -Werror -Wall -Wextra'

    msg "test: AES_FEWER_TABLES"
    make test
}

component_test_aes_rom_tables () {
    msg "build: default config with AES_ROM_TABLES enabled"
    scripts/config.py set MBEDTLS_AES_ROM_TABLES
    make CFLAGS='-O2 -Werror -Wall -Wextra'

    msg "test: AES_ROM_TABLES"
    make test
}

component_test_aes_fewer_tables_and_rom_tables () {
    msg "build: default config with AES_ROM_TABLES and AES_FEWER_TABLES enabled"
    scripts/config.py set MBEDTLS_AES_FEWER_TABLES
    scripts/config.py set MBEDTLS_AES_ROM_TABLES
    make CFLAGS='-O2 -Werror -Wall -Wextra'

    msg "test: AES_FEWER_TABLES + AES_ROM_TABLES"
    make test
}

# helper for common_block_cipher_no_decrypt() which:
# - enable/disable the list of config options passed from -s/-u respectively.
# - build
# - test for tests_suite_xxx
# - selftest
#
# Usage: helper_block_cipher_no_decrypt_build_test
#        [-s set_opts] [-u unset_opts] [-c cflags] [-l ldflags] [option [...]]
# Options:  -s set_opts     the list of config options to enable
#           -u unset_opts   the list of config options to disable
#           -c cflags       the list of options passed to CFLAGS
#           -l ldflags      the list of options passed to LDFLAGS
helper_block_cipher_no_decrypt_build_test () {
    while [ $# -gt 0 ]; do
        case "$1" in
            -s)
                shift; local set_opts="$1";;
            -u)
                shift; local unset_opts="$1";;
            -c)
                shift; local cflags="-Werror -Wall -Wextra $1";;
            -l)
                shift; local ldflags="$1";;
        esac
        shift
    done
    set_opts="${set_opts:-}"
    unset_opts="${unset_opts:-}"
    cflags="${cflags:-}"
    ldflags="${ldflags:-}"

    [ -n "$set_opts" ] && echo "Enabling: $set_opts" && scripts/config.py set-all $set_opts
    [ -n "$unset_opts" ] && echo "Disabling: $unset_opts" && scripts/config.py unset-all $unset_opts

    msg "build: default config + BLOCK_CIPHER_NO_DECRYPT${set_opts:+ + $set_opts}${unset_opts:+ - $unset_opts} with $cflags${ldflags:+, $ldflags}"
    make clean
    make CFLAGS="-O2 $cflags" LDFLAGS="$ldflags"

    # Make sure we don't have mbedtls_xxx_setkey_dec in AES/ARIA/CAMELLIA
    not grep mbedtls_aes_setkey_dec library/aes.o
    not grep mbedtls_aria_setkey_dec library/aria.o
    not grep mbedtls_camellia_setkey_dec library/camellia.o
    # Make sure we don't have mbedtls_internal_aes_decrypt in AES
    not grep mbedtls_internal_aes_decrypt library/aes.o
    # Make sure we don't have mbedtls_aesni_inverse_key in AESNI
    not grep mbedtls_aesni_inverse_key library/aesni.o

    msg "test: default config + BLOCK_CIPHER_NO_DECRYPT${set_opts:+ + $set_opts}${unset_opts:+ - $unset_opts} with $cflags${ldflags:+, $ldflags}"
    make test

    msg "selftest: default config + BLOCK_CIPHER_NO_DECRYPT${set_opts:+ + $set_opts}${unset_opts:+ - $unset_opts} with $cflags${ldflags:+, $ldflags}"
    programs/test/selftest
}

# This is a common configuration function used in:
# - component_test_block_cipher_no_decrypt_aesni_legacy()
# - component_test_block_cipher_no_decrypt_aesni_use_psa()
# in order to test BLOCK_CIPHER_NO_DECRYPT with AESNI intrinsics,
# AESNI assembly and AES C implementation on x86_64 and with AESNI intrinsics
# on x86.
common_block_cipher_no_decrypt () {
    # test AESNI intrinsics
    helper_block_cipher_no_decrypt_build_test \
        -s "MBEDTLS_AESNI_C" \
        -c "-mpclmul -msse2 -maes"

    # test AESNI assembly
    helper_block_cipher_no_decrypt_build_test \
        -s "MBEDTLS_AESNI_C" \
        -c "-mno-pclmul -mno-sse2 -mno-aes"

    # test AES C implementation
    helper_block_cipher_no_decrypt_build_test \
        -u "MBEDTLS_AESNI_C"

    # test AESNI intrinsics for i386 target
    helper_block_cipher_no_decrypt_build_test \
        -s "MBEDTLS_AESNI_C" \
        -c "-m32 -mpclmul -msse2 -maes" \
        -l "-m32"
}

# This is a configuration function used in component_test_block_cipher_no_decrypt_xxx:
# usage: 0: no PSA crypto configuration
#        1: use PSA crypto configuration
config_block_cipher_no_decrypt () {
    use_psa=$1

    scripts/config.py set MBEDTLS_BLOCK_CIPHER_NO_DECRYPT
    scripts/config.py unset MBEDTLS_CIPHER_MODE_CBC
    scripts/config.py unset MBEDTLS_CIPHER_MODE_XTS
    scripts/config.py unset MBEDTLS_DES_C
    scripts/config.py unset MBEDTLS_NIST_KW_C

    if [ "$use_psa" -eq 1 ]; then
        # Enable support for cryptographic mechanisms through the PSA API.
        # Note: XTS, KW are not yet supported via the PSA API in Mbed TLS.
        scripts/config.py set MBEDTLS_PSA_CRYPTO_CONFIG
        scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_CBC_NO_PADDING
        scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_CBC_PKCS7
        scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_ALG_ECB_NO_PADDING
        scripts/config.py -f "$CRYPTO_CONFIG_H" unset PSA_WANT_KEY_TYPE_DES
    fi
}

component_test_block_cipher_no_decrypt_aesni () {
    # This consistently causes an llvm crash on clang 3.8, so use gcc
    export CC=gcc
    config_block_cipher_no_decrypt 0
    common_block_cipher_no_decrypt
}

component_test_block_cipher_no_decrypt_aesni_use_psa () {
    # This consistently causes an llvm crash on clang 3.8, so use gcc
    export CC=gcc
    config_block_cipher_no_decrypt 1
    common_block_cipher_no_decrypt
}

support_test_block_cipher_no_decrypt_aesce_armcc () {
    support_build_armcc
}

component_test_block_cipher_no_decrypt_aesce_armcc () {
    scripts/config.py baremetal

    # armc[56] don't support SHA-512 intrinsics
    scripts/config.py unset MBEDTLS_SHA512_USE_A64_CRYPTO_IF_PRESENT

    # Stop armclang warning about feature detection for A64_CRYPTO.
    # With this enabled, the library does build correctly under armclang,
    # but in baremetal builds (as tested here), feature detection is
    # unavailable, and the user is notified via a #warning. So enabling
    # this feature would prevent us from building with -Werror on
    # armclang. Tracked in #7198.
    scripts/config.py unset MBEDTLS_SHA256_USE_A64_CRYPTO_IF_PRESENT
    scripts/config.py set MBEDTLS_HAVE_ASM

    config_block_cipher_no_decrypt 1

    # test AESCE baremetal build
    scripts/config.py set MBEDTLS_AESCE_C
    msg "build: default config + BLOCK_CIPHER_NO_DECRYPT with AESCE"
    armc6_build_test "-O1 --target=aarch64-arm-none-eabi -march=armv8-a+crypto -Werror -Wall -Wextra"

    # Make sure we don't have mbedtls_xxx_setkey_dec in AES/ARIA/CAMELLIA
    not grep mbedtls_aes_setkey_dec library/aes.o
    not grep mbedtls_aria_setkey_dec library/aria.o
    not grep mbedtls_camellia_setkey_dec library/camellia.o
    # Make sure we don't have mbedtls_internal_aes_decrypt in AES
    not grep mbedtls_internal_aes_decrypt library/aes.o
    # Make sure we don't have mbedtls_aesce_inverse_key and aesce_decrypt_block in AESCE
    not grep mbedtls_aesce_inverse_key library/aesce.o
    not grep aesce_decrypt_block library/aesce.o
}

component_test_ctr_drbg_aes_256_sha_256 () {
    msg "build: full + MBEDTLS_ENTROPY_FORCE_SHA256 (ASan build)"
    scripts/config.py full
    scripts/config.py unset MBEDTLS_MEMORY_BUFFER_ALLOC_C
    scripts/config.py set MBEDTLS_ENTROPY_FORCE_SHA256
    CC=$ASAN_CC cmake -D CMAKE_BUILD_TYPE:String=Asan .
    make

    msg "test: full + MBEDTLS_ENTROPY_FORCE_SHA256 (ASan build)"
    make test
}

component_test_ctr_drbg_aes_128_sha_512 () {
    msg "build: full + MBEDTLS_CTR_DRBG_USE_128_BIT_KEY (ASan build)"
    scripts/config.py full
    scripts/config.py unset MBEDTLS_MEMORY_BUFFER_ALLOC_C
    scripts/config.py set MBEDTLS_CTR_DRBG_USE_128_BIT_KEY
    CC=$ASAN_CC cmake -D CMAKE_BUILD_TYPE:String=Asan .
    make

    msg "test: full + MBEDTLS_CTR_DRBG_USE_128_BIT_KEY (ASan build)"
    make test
}

component_test_ctr_drbg_aes_128_sha_256 () {
    msg "build: full + MBEDTLS_CTR_DRBG_USE_128_BIT_KEY + MBEDTLS_ENTROPY_FORCE_SHA256 (ASan build)"
    scripts/config.py full
    scripts/config.py unset MBEDTLS_MEMORY_BUFFER_ALLOC_C
    scripts/config.py set MBEDTLS_CTR_DRBG_USE_128_BIT_KEY
    scripts/config.py set MBEDTLS_ENTROPY_FORCE_SHA256
    CC=$ASAN_CC cmake -D CMAKE_BUILD_TYPE:String=Asan .
    make

    msg "test: full + MBEDTLS_CTR_DRBG_USE_128_BIT_KEY + MBEDTLS_ENTROPY_FORCE_SHA256 (ASan build)"
    make test
}

component_test_se_default () {
    msg "build: default config + MBEDTLS_PSA_CRYPTO_SE_C"
    scripts/config.py set MBEDTLS_PSA_CRYPTO_SE_C
    make CC=clang CFLAGS="$ASAN_CFLAGS -Os" LDFLAGS="$ASAN_CFLAGS"

    msg "test: default config + MBEDTLS_PSA_CRYPTO_SE_C"
    make test
}

component_test_full_static_keystore () {
    msg "build: full config - MBEDTLS_PSA_KEY_STORE_DYNAMIC"
    scripts/config.py full
    scripts/config.py unset MBEDTLS_PSA_KEY_STORE_DYNAMIC
    make CC=clang CFLAGS="$ASAN_CFLAGS -Os" LDFLAGS="$ASAN_CFLAGS"

    msg "test: full config - MBEDTLS_PSA_KEY_STORE_DYNAMIC"
    make test
}

component_test_psa_crypto_drivers () {
    msg "build: full + test drivers dispatching to builtins"
    scripts/config.py full
    scripts/config.py unset MBEDTLS_PSA_CRYPTO_CONFIG
    loc_cflags="$ASAN_CFLAGS -DPSA_CRYPTO_DRIVER_TEST_ALL"
    loc_cflags="${loc_cflags} '-DMBEDTLS_USER_CONFIG_FILE=\"../tests/configs/user-config-for-test.h\"'"
    loc_cflags="${loc_cflags} -I../tests/include -O2"

    make CC=$ASAN_CC CFLAGS="${loc_cflags}" LDFLAGS="$ASAN_CFLAGS"

    msg "test: full + test drivers dispatching to builtins"
    make test
}

component_build_psa_config_file () {
    msg "build: make with MBEDTLS_PSA_CRYPTO_CONFIG_FILE" # ~40s
    scripts/config.py set MBEDTLS_PSA_CRYPTO_CONFIG
    cp "$CRYPTO_CONFIG_H" psa_test_config.h
    echo '#error "MBEDTLS_PSA_CRYPTO_CONFIG_FILE is not working"' >"$CRYPTO_CONFIG_H"
    make CFLAGS="-I '$PWD' -DMBEDTLS_PSA_CRYPTO_CONFIG_FILE='\"psa_test_config.h\"'"
    # Make sure this feature is enabled. We'll disable it in the next phase.
    programs/test/query_compile_time_config MBEDTLS_CMAC_C
    make clean

    msg "build: make with MBEDTLS_PSA_CRYPTO_CONFIG_FILE + MBEDTLS_PSA_CRYPTO_USER_CONFIG_FILE" # ~40s
    # In the user config, disable one feature and its dependencies, which will
    # reflect on the mbedtls configuration so we can query it with
    # query_compile_time_config.
    echo '#undef PSA_WANT_ALG_CMAC' >psa_user_config.h
    echo '#undef PSA_WANT_ALG_PBKDF2_AES_CMAC_PRF_128' >> psa_user_config.h
    scripts/config.py unset MBEDTLS_CMAC_C
    make CFLAGS="-I '$PWD' -DMBEDTLS_PSA_CRYPTO_CONFIG_FILE='\"psa_test_config.h\"' -DMBEDTLS_PSA_CRYPTO_USER_CONFIG_FILE='\"psa_user_config.h\"'"
    not programs/test/query_compile_time_config MBEDTLS_CMAC_C

    rm -f psa_test_config.h psa_user_config.h
}

component_build_psa_alt_headers () {
    msg "build: make with PSA alt headers" # ~20s

    # Generate alternative versions of the substitutable headers with the
    # same content except different include guards.
    make -C tests include/alt-extra/psa/crypto_platform_alt.h include/alt-extra/psa/crypto_struct_alt.h

    # Build the library and some programs.
    # Don't build the fuzzers to avoid having to go through hoops to set
    # a correct include path for programs/fuzz/Makefile.
    make CFLAGS="-I ../tests/include/alt-extra -DMBEDTLS_PSA_CRYPTO_PLATFORM_FILE='\"psa/crypto_platform_alt.h\"' -DMBEDTLS_PSA_CRYPTO_STRUCT_FILE='\"psa/crypto_struct_alt.h\"'" lib
    make -C programs -o fuzz CFLAGS="-I ../tests/include/alt-extra -DMBEDTLS_PSA_CRYPTO_PLATFORM_FILE='\"psa/crypto_platform_alt.h\"' -DMBEDTLS_PSA_CRYPTO_STRUCT_FILE='\"psa/crypto_struct_alt.h\"'"

    # Check that we're getting the alternative include guards and not the
    # original include guards.
    programs/test/query_included_headers | grep -x PSA_CRYPTO_PLATFORM_ALT_H
    programs/test/query_included_headers | grep -x PSA_CRYPTO_STRUCT_ALT_H
    programs/test/query_included_headers | not grep -x PSA_CRYPTO_PLATFORM_H
    programs/test/query_included_headers | not grep -x PSA_CRYPTO_STRUCT_H
}

component_test_min_mpi_window_size () {
    msg "build: Default + MBEDTLS_MPI_WINDOW_SIZE=1 (ASan build)" # ~ 10s
    scripts/config.py set MBEDTLS_MPI_WINDOW_SIZE 1
    CC=$ASAN_CC cmake -D CMAKE_BUILD_TYPE:String=Asan .
    make

    msg "test: MBEDTLS_MPI_WINDOW_SIZE=1 - main suites (inc. selftests) (ASan build)" # ~ 10s
    make test
}
