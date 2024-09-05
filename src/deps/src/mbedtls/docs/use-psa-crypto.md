This document describes the compile-time configuration option
`MBEDTLS_USE_PSA_CRYPTO` from a user's perspective.

This option:
- makes the X.509 and TLS libraries use PSA for cryptographic operations as
  much as possible, see "Internal changes" below;
- enables new APIs for using keys handled by PSA Crypto, such as
  `mbedtls_pk_setup_opaque()` and `mbedtls_ssl_conf_psk_opaque()`, see
"New APIs / API extensions" below.

General considerations
----------------------

**Application code:** when this option is enabled, you need to call
`psa_crypto_init()` before calling any function from the SSL/TLS, X.509 or PK
modules, except for the various mbedtls_xxx_init() functions which can be called
at any time.

**Why enable this option:** to fully take advantage of PSA drivers in PK,
X.509 and TLS. For example, enabling this option is what allows use of drivers
for ECDSA, ECDH and EC J-PAKE in those modules. However, note that even with
this option disabled, some code in PK, X.509, TLS or the crypto library might
still use PSA drivers, if it can determine it's safe to do so; currently
that's the case for hashes.

**Relationship with other options:** This option depends on
`MBEDTLS_PSA_CRYPTO_C`. These two options differ in the following way:
- `MBEDTLS_PSA_CRYPTO_C` enables the implementation of the PSA Crypto API.
  When it is enabled, `psa_xxx()` APIs are available and you must call
`psa_crypto_init()` before you call any other `psa_xxx()` function. Other
modules in the library (non-PSA crypto APIs, X.509, TLS) may or may not use
PSA Crypto but you're not required to call `psa_crypto_init()` before calling
non-PSA functions, unless explicitly documented (TLS 1.3).
- `MBEDTLS_USE_PSA_CRYPTO` means that X.509 and TLS will use PSA Crypto as
  much as possible (that is, everywhere except for features that are not
supported by PSA Crypto, see "Internal Changes" below for a complete list of
exceptions). When it is enabled, you need to call `psa_crypto_init()` before
calling any function from PK, X.509 or TLS; however it doesn't change anything
for the rest of the library.

**Scope:** `MBEDTLS_USE_PSA_CRYPTO` has no effect on modules other than PK,
X.509 and TLS. It also has no effect on most of the TLS 1.3 code, which always
uses PSA crypto. The parts of the TLS 1.3 code that will use PSA Crypto or not
depending on this option being set or not are:
- record protection;
- running handshake hash;
- asymmetric signature verification & generation;
- X.509 certificate chain verification.
You need to enable `MBEDTLS_USE_PSA_CRYPTO` if you want TLS 1.3 to use PSA
everywhere.

**Historical note:** This option was introduced at a time when PSA Crypto was
still beta and not ready for production, so we made its use in X.509 and TLS
opt-in: by default, these modules would keep using the stable,
production-ready legacy (pre-PSA) crypto APIs. So, the scope of was X.509 and
TLS, as well as some of PK for technical reasons. Nowadays PSA Crypto is no
longer beta, and production quality, so there's no longer any reason to make
its use in other modules opt-in. However, PSA Crypto functions require that
`psa_crypto_init()` has been called before their use, and for backwards
compatibility reasons we can't impose this requirement on non-PSA functions
that didn't have such a requirement before. So, nowadays the main meaning of
`MBEDTLS_USE_PSA_CRYPTO` is that the user promises to call `psa_crypto_init()`
before calling any PK, X.509 or TLS functions. For the same compatibility
reasons, we can't extend its scope. However, new modules in the library, such
as TLS 1.3, can be introduced with a requirement to call `psa_crypto_init()`.

New APIs / API extensions
-------------------------

### PSA-held (opaque) keys in the PK layer

**New API function:** `mbedtls_pk_setup_opaque()` - can be used to
wrap a PSA key pair into a PK context. The key can be used for private-key
operations and its public part can be exported.

**Benefits:** isolation of long-term secrets, use of PSA Crypto drivers.

**Limitations:** please refer to the documentation of `mbedtls_pk_setup_opaque()`
for a full list of supported operations and limitations.

**Use in X.509 and TLS:** opt-in. The application needs to construct the PK context
using the new API in order to get the benefits; it can then pass the
resulting context to the following existing APIs:

- `mbedtls_ssl_conf_own_cert()` or `mbedtls_ssl_set_hs_own_cert()` to use the
  key together with a certificate for certificate-based key exchanges;
- `mbedtls_x509write_csr_set_key()` to generate a CSR (certificate signature
  request);
- `mbedtls_x509write_crt_set_issuer_key()` to generate a certificate.

### PSA-held (opaque) keys for TLS pre-shared keys (PSK)

**New API functions:** `mbedtls_ssl_conf_psk_opaque()` and
`mbedtls_ssl_set_hs_psk_opaque()`. Call one of these from an application to
register a PSA key for use with a PSK key exchange.

**Benefits:** isolation of long-term secrets.

**Limitations:** none.

**Use in TLS:** opt-in. The application needs to register the key using one of
the new APIs to get the benefits.

### PSA-held (opaque) keys for TLS 1.2 EC J-PAKE key exchange

**New API function:** `mbedtls_ssl_set_hs_ecjpake_password_opaque()`.
Call this function from an application to register a PSA key for use with the
TLS 1.2 EC J-PAKE key exchange.

**Benefits:** isolation of long-term secrets.

**Limitations:** none.

**Use in TLS:** opt-in. The application needs to register the key using one of
the new APIs to get the benefits.

### PSA-based operations in the Cipher layer

There is a new API function `mbedtls_cipher_setup_psa()` to set up a context
that will call PSA to store the key and perform the operations.

This function only worked for a small number of ciphers. It is now deprecated
and it is recommended to use `psa_cipher_xxx()` or `psa_aead_xxx()` functions
directly instead.

**Warning:** This function will be removed in a future version of Mbed TLS. If
you are using it and would like us to keep it, please let us know about your
use case.

Internal changes
----------------

All of these internal changes are active as soon as `MBEDTLS_USE_PSA_CRYPTO`
is enabled, no change required on the application side.

### TLS: most crypto operations based on PSA

Current exceptions:

- Finite-field (non-EC) Diffie-Hellman (used in key exchanges: DHE-RSA,
  DHE-PSK).
- Restartable operations when `MBEDTLS_ECP_RESTARTABLE` is also enabled (see
  the documentation of that option).

Other than the above exceptions, all crypto operations are based on PSA when
`MBEDTLS_USE_PSA_CRYPTO` is enabled.

### X.509: most crypto operations based on PSA

Current exceptions:

- Restartable operations when `MBEDTLS_ECP_RESTARTABLE` is also enabled (see
  the documentation of that option).

Other than the above exception, all crypto operations are based on PSA when
`MBEDTLS_USE_PSA_CRYPTO` is enabled.

### PK layer: most crypto operations based on PSA

Current exceptions:

- Verification of RSA-PSS signatures with an MGF hash that's different from
  the message hash.
- Restartable operations when `MBEDTLS_ECP_RESTARTABLE` is also enabled (see
  the documentation of that option).

Other than the above exceptions, all crypto operations are based on PSA when
`MBEDTLS_USE_PSA_CRYPTO` is enabled.

