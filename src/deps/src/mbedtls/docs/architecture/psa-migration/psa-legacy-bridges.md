Bridges between legacy and PSA crypto APIs
==========================================

## Introduction

### Goal of this document

This document explores the needs of applications that use both Mbed TLS legacy crypto interfaces and PSA crypto interfaces. Based on [requirements](#requirements), we [analyze gaps](#gap-analysis) and [API design](#api-design).

This is a design document. The target audience is library maintainers. See the companion document [“Transitioning to the PSA API”](../../psa-transition.md) for a user focus on the same topic.

### Keywords

* [TODO] A part of the analysis that isn't finished.
* [OPEN] Open question: a specific aspect of the design where there are several plausible decisions.
* [ACTION] A finalized part of the design that will need to be carried out.

### Context

Mbed TLS 3.x supports two cryptographic APIs:

* The legacy API `mbedtls_xxx` is inherited from PolarSSL.
* The PSA API `psa_xxx` was introduced in Mbed TLS 2.17.

Mbed TLS is gradually shifting from the legacy API to the PSA API. Mbed TLS 4.0 will be the first version where the PSA API is considered the main API, and large parts of the legacy API will be removed.

In Mbed TLS 4.0, the cryptography will be provided by a separate project [TF-PSA-Crypto](https://github.com/Mbed-TLS/TF-PSA-Crypto). For simplicity, in this document, we just refer to the whole as “Mbed TLS”.

### Document history

This document was originally written when preparing Mbed TLS 3.6. Mbed TLS 3.6 includes both PSA and legacy APIs covering largely overlapping ground. Many legacy APIs will be removed in Mbed TLS 4.0.

## Requirements

### Why mix APIs?

There is functionality that is tied to one API and is not directly available in the other API:

* Only PSA fully supports PSA accelerators and secure element integration.
* Only PSA supports isolating cryptographic material in a secure service.
* The legacy API has features that are not present (yet) in PSA, notably parsing and formatting asymmetric keys.

The legacy API can partially leverage PSA features via `MBEDTLS_USE_PSA_CRYPTO`, but this has limited scope.

In addition, many applications cannot be migrated in a single go. For large projects, it is impractical to rewrite a significant part of the code all at once. (For example, Mbed TLS itself will have taken more than 6 years to transition.) Projects that use one or more library in addition to Mbed TLS must follow the evolution of these libraries, each of which might have its own pace.

### Where mixing happens

Mbed TLS can be, and normally is, built with support for both APIs. Therefore no special effort is necessary to allow an application to use both APIs.

Special effort is necessary to use both APIs as part of the implementation of the same feature. From an informal analysis of typical application requirements, we identify four parts of the use of cryptography which can be provided by different APIs:

* Metadata manipulation: parsing and producing encrypted or signed files, finding mutually supported algorithms in a network protocol negotiation, etc.
* Key management: parsing, generating, deriving and formatting cryptographic keys.
* Data manipulation other than keys. In practice, most data formats within the scope of the legacy crypto APIs are trivial (ciphertexts, hashes, MACs, shared secrets). The one exception is ECDSA signatures.
* Cryptographic operations: hash, sign, encrypt, etc.

From this, we deduce the following requirements:

* Convert between PSA and legacy metadata.
* Creating a key with the legacy API and consuming it in the PSA API.
* Creating a key with the PSA API and consuming it in the legacy API.
* Manipulating data formats, other than keys, where the PSA API is lacking.

### Scope limitations

The goal of this document is to bridge the legacy API and the PSA API. The goal is not to provide a PSA way to do everything that is currently possible with the legacy API. The PSA API is less flexible in some regards, and extending it is out of scope in the present study.

With respect to the legacy API, we do not consider functionality of low-level modules for individual algorithms. Our focus is on applications that use high-level legacy crypto modules (md, cipher, pk) and need to combine that with uses of the PSA APIs.

## Gap analysis

The document [“Transitioning to the PSA API”](../../psa-transition.md) enumerates the public header files in Mbed TLS 3.4 and the API elements (especially enums and functions) that they provide, listing PSA equivalents where they exist. There are gaps in two cases:

* Where the PSA equivalents do not provide the same functionality. A typical example is parsing and formatting asymmetric keys.
* To convert between data representations used by legacy APIs and data representations used by PSA APIs.

Based on “[Where mixing happens](#where-mixing-happens)”, we focus the gap analysis on two topics: metadata and keys. This chapter explores the gaps in each family of cryptographic mechanisms.

### Generic metadata gaps

#### Need for error code conversion

Do we need public functions to convert between `MBEDTLS_ERR_xxx` error codes and `PSA_ERROR_xxx` error codes? We have such functions for internal use.

Mbed TLS needs these conversions because it has many functions that expose one API (legacy/API) but are implemented on top of the other API. Most applications would convert legacy and PSA error code to their own error codes, and converting between `MBEDTLS_ERR_xxx` error codes and `PSA_ERROR_xxx` is not particularly helpful for that. Application code might need such conversion functions when implementing an X.509 or TLS callback (returning `MBEDTLS_ERR_xxx`) on top of PSA functions, but this is a very limited use case.

Conclusion: no need for public error code conversion functions.

### Hash gap analysis

Hashes do not involve keys, and involves no nontrivial data format. Therefore the only gap is with metadata, namely specifying a hash algorithm.

Hashes are often used as building blocks for other mechanisms (HMAC, signatures, key derivation, etc.). Therefore metadata about hashes is relevant not only when calculating hashes, but also when performing many other cryptographic operations.

Gap: functions to convert between `psa_algorithm_t` hash algorithms and `mbedtls_md_type_t`. Such functions exist in Mbed TLS 3.5 (`mbedtls_md_psa_alg_from_type`, `mbedtls_md_type_from_psa_alg`) but they are declared only in private headers.

### MAC gap analysis

[TODO]

### Cipher and AEAD gap analysis

[TODO]

### Key derivation gap analysis

[TODO]

### Random generation gap analysis

[TODO]

### Asymmetric cryptography gap analysis

#### Asymmetric cryptography metadata

The legacy API only has generic support for two key types: RSA and ECC, via the pk module. ECC keys can also be further classified according to their curve. The legacy API also supports DHM (Diffie-Hellman-Merkle = FFDH: finite-field Diffie-Hellman) keys, but those are not integrated in the pk module.

An RSA or ECC key can potentially be used for different algorithms in the scope of the pk module:

* RSA: PKCS#1v1.5 signature, PSS signature, PKCS#1v1.5 encryption, OAEP encryption.
* ECC: ECDSA signature (randomized or deterministic), ECDH key agreement (via `mbedtls_pk_ec`).

ECC keys are also involved in EC-JPAKE, but this happens internally: the EC-JPAKE interface only needs one piece of metadata, namely, to identify a curve.

Since there is no algorithm that can be used with multiple types, and PSA keys have a policy that (for the most part) limits them to one algorithm, there does not seem to be a need to convert between legacy and PSA asymmetric key types on their own. The useful metadata conversions are:

* Selecting an **elliptic curve**.

  This means converting between an `mbedtls_ecp_group_id` and a pair of `{psa_ecc_family_t; size_t}`.

  This is fulfilled by `mbedtls_ecc_group_to_psa` and `mbedtls_ecc_group_from_psa`, which were introduced into the public API between Mbed TLS 3.5 and 3.6 ([#8664](https://github.com/Mbed-TLS/mbedtls/pull/8664)).

* Selecting A **DHM group**.

  PSA only supports predefined groups, whereas legacy only supports ad hoc groups. An existing application referring to `MBEDTLS_DHM_RFC7919_FFDHExxx` values would need to refer to `PSA_DH_FAMILY_RFC7919`; an existing application using arbitrary groups cannot migrate to PSA.

* Simultaneously supporting **a key type and an algorithm**.

  On the legacy side, this is an `mbedtls_pk_type_t` value and more. For ECDSA, the choice between randomized and deterministic is made at compile time. For RSA, the choice of encryption or signature algorithm is made either by configuring the underlying `mbedtls_rsa_context` or when calling the operation function.

  On the PSA side, this is a `psa_key_type_t` value and an algorithm which is normally encoded as policy information in a `psa_key_attributes_t`. The algorithm is also needed in its own right when calling operation functions.

#### Using a legacy key pair or public key with PSA

There are several scenarios where an application has a legacy key pair or public key (`mbedtls_pk_context`) and needs to create a PSA key object (`psa_key_id_t`).

Reasons for first creating a legacy key object, where it's impossible or impractical to directly create a PSA key:

* A very common case where the input is a legacy key object is parsing. PSA does not (yet) have an equivalent of the `mbedtls_pk_parse_xxx` functions.
* The PSA key creation interface is less flexible in some cases. In particular, PSA RSA key generation does not (yet) allow choosing the public exponent.
* The pk object may be created by a part of the application (or a third-party library) that hasn't been migrated to the PSA API yet.

Reasons for needing a PSA key object:

* Using the key with third-party interface that takes a PSA key identifier as input. (Mbed TLS itself has a few TLS functions that take PSA key identifiers, but as of Mbed TLS 3.5, it is always possible to use a legacy key instead.)
* Benefiting from a PSA accelerator, or from PSA's world separation, even without `MBEDTLS_USE_PSA_CRYPTO`. (Not a priority scenario: we generally expect people to activate `MBEDTLS_USE_PSA_CRYPTO` at an early stage of their migration to PSA.)

Gap: a way to create a PSA key object from an `mbedtls_pk_context`. This partially exists in the form of `mbedtls_pk_wrap_as_opaque`, but it is not fully satisfactory, for reasons that are detailed in “[API to create a PSA key from a PK context](#api-to-create-a-psa-key-from-a-pk-context)” below.

#### Using a PSA key as a PK context

There are several scenarios where an application has a PSA key and needs to use it through an interface that wants an `mbedtls_pk_context` object. Typically, there is an existing key in the PSA key store (possibly in a secure element and non-exportable), and the key needs to be used in an interface that requires a `mbedtls_pk_context *` input, such as Mbed TLS's X.509 and TLS APIs or a similar third-party interface, or the `mbedtls_pk_write_xxx` interfaces which do not (yet) have PSA equivalents.

There is a function `mbedtls_pk_setup_opaque` that mostly does this. However, it has several limitations:

* It creates a PK key of type `MBEDTLS_PK_OPAQUE` that wraps the PSA key. This is good enough in some scenarios, but not others. For example, it's ok for pkwrite, because we've upgraded the pkwrite code to handle `MBEDTLS_PK_OPAQUE`. That doesn't help users of third-party libraries that haven't yet been upgraded.
* It ties the lifetime of the PK object to the PSA key, which is error-prone: if the PSA key is destroyed but the PK object isn't, there is no way to reliably detect any subsequent misuse of the PK object.
* It is only available under `MBEDTLS_USE_PSA_CRYPTO`. This is not a priority concern, since we generally expect people to activate `MBEDTLS_USE_PSA_CRYPTO` at an early stage of their migration to PSA. However, this function is useful to use specific PSA keys in X.509/TLS regardless of whether X.509/TLS use the PSA API for all cryptographic operations, so this is a wart in the current API.

It therefore appears that we need two ways to “convert” a PSA key to PK:

* Wrapping, which is what `mbedtls_pk_setup_opaque` does. This works for any PSA key but is limited by the key's lifetime and creates a PK object with limited functionality.
* Copying, which requires a new function. This requires an exportable key but creates a fully independent, fully functional PK object.

Gap: a way to copy a PSA key into a PK context. This can only be expected to work if the PSA key is exportable.

After some discussion, have not identified anything we want to change in the behavior of `mbedtls_pk_setup_opaque`. We only want to generalize it to non-`MBEDTLS_USE_PSA_CRYPTO` and to document it better.

#### Signature formats

The pk module uses signature formats intended for X.509. The PSA module uses the simplest sensible signature format.

* For RSA, the formats are the same.
* For ECDSA, PSA uses a fixed-size concatenation of (r,s), whereas X.509 and pk use an ASN.1 DER encoding of the sequence (r,s).

Gap: We need APIs to convert between these two formats. The conversion code already exists under the hood, but it's in pieces that can't be called directly.

There is a design choice here: do we provide conversions functions for ECDSA specifically, or do we provide conversion functions that take an algorithm as argument and just happen to be a no-op with RSA? One factor is plausible extensions. These conversions functions will remain useful in Mbed TLS 4.x and perhaps beyond. We will at least add EdDSA support, and its signature encoding is the fixed-size concatenation (r,s) even in X.509. We may well also add support for some post-quantum signatures, and their concrete format is still uncertain.

Given the uncertainty, it would be nice to provide a sufficiently generic interface to convert between the PSA and the pk signature format, parametrized by the algorithm. However, it is difficult to predict exactly what parameters are needed. For example, converting from an ASN.1 ECDSA signature to (r,s) requires the knowledge of the curve, or at least the curve's size. Therefore we are not going to add a generic function at this stage.

For ECDSA, there are two plausible APIs: follow the ASN.1/X.509 write/parse APIs, or present an ordinary input/output API. The ASN.1 APIs are the way they are to accommodate nested TLV structures. But ECDSA signatures do not appear nested in TLV structures in either TLS (there's just a signature field) or X.509 (the signature is inside a BITSTRING, not directly in a SEQUENCE). So there does not seem to be a need for an ASN.1-like API for the ASN.1 format, just the format conversion itself in a buffer that just contains the signature.

#### Asymmetric cryptography TODO

[TODO] Other gaps?

## New APIs

This section presents new APIs to implement based on the [gap analysis](#gap-analysis).

### General notes

Each action to implement a function entails:

* Implement the library function.
* Document it precisely, including error conditions.
* Unit-test it.
* Mention it where relevant in the PSA transition guide.

### Hash APIs

Based on the [gap analysis](#hash-gap-analysis):

[ACTION] [#8340](https://github.com/Mbed-TLS/mbedtls/issues/8340) Move `mbedtls_md_psa_alg_from_type` and `mbedtls_md_type_from_psa_alg` from `library/md_psa.h` to `include/mbedtls/md.h`.

### MAC APIs

[TODO]

### Cipher and AEAD APIs

[TODO]

### Key derivation APIs

[TODO]

### Random generation APIs

[TODO]

### Asymmetric cryptography APIs

#### Asymmetric cryptography metadata APIs

Based on the [gap analysis](#asymmetric-cryptography-metadata):

* No further work is needed about RSA specifically. The amount of metadata other than hashes is sufficiently small to be handled in ad hoc ways in applications, and hashes have [their own conversions](#hash-apis).
* No further work is needed about ECC specifically. We have just added adequate functions.
* No further work is needed about DHM specifically. There is no good way to translate the relevant information.
* [OPEN] Is there a decent way to convert between `mbedtls_pk_type_t` plus extra information, and `psa_key_type_t` plus policy information? The two APIs are different in crucial ways, with different splits between key type, policy information and operation algorithm.
  Thinking so far: there isn't really a nice way to present this conversion. For a specific key, `mbedtls_pk_get_psa_attributes` and `mbedtls_pk_copy_from_psa` do the job.

#### API to create a PSA key from a PK context

Based on the [gap analysis](#using-a-legacy-key-pair-or-public-key-with-psa):

Given an `mbedtls_pk_context`, we want a function that creates a PSA key with the same key material and algorithm. “Same key material” is straightforward, but “same algorithm” is not, because a PK context has incomplete algorithm information. For example, there is no way to distinguish between an RSA key that is intended for signature or for encryption. Between algorithms of the same nature, there is no way to distinguish a key intended for PKCS#1v1.5 and one intended for PKCS#1v2.1 (OAEP/PSS): this is indicated in the underlying RSA context, but the indication there is only a default that can be overridden by calling `mbedtls_pk_{sign,verify}_ext`. Also there is no way to distinguish between `PSA_ALG_RSA_PKCS1V15_SIGN(hash_alg)` and `PSA_ALG_RSA_PKCS1V15_SIGN_RAW`: in the legacy interface, this is only determined when actually doing a signature/verification operation. Therefore the function that creates the PSA key needs extra information to indicate which algorithm to put in the key's policy.

When creating a PSA key, apart from the key material, the key is determined by attributes, which fall under three categories:

* Type and size. These are directly related to the key material and can be deduced from it if the key material is in a structured format, which is the case with an `mbedtls_pk_context` input.
* Policy. This includes the chosen algorithm, which as discussed above cannot be fully deduced from the `mbedtls_pk_context` object. Just choosing one algorithm is problematic because it doesn't allow implementation-specific extensions, such as Mbed TLS's enrollment algorithm. The intended usage flags cannot be deduced from the PK context either, but the conversion function could sensibly just enable all the relevant usage flags. Users who want a more restrictive usage can call `psa_copy_key` and `psa_destroy_key` to obtain a PSA key object with a more restrictive usage.
* Persistence and location. This is completely orthogonal to the information from the `mbedtls_pk_context` object. It is convenient, but not necessary, for the conversion function to allow customizing these aspects. If it doesn't, users can call the conversion function and then call `psa_copy_key` and `psa_destroy_key` to move the key to its desired location.

To allow the full flexibility around policies, and make the creation of a persistent key more convenient, the conversion function shall take a `const psa_key_attributes_t *` input, like all other functions that create a PSA key. In addition, there shall be a helper function to populate a `psa_key_attributes_t` with a sensible default. This lets the caller choose a more flexible, or just different usage policy, unlike the default-then-copy approach which only allows restricting the policy.

This is close to the existing function `mbedtls_pk_wrap_as_opaque`, but does not bake in the implementation-specific consideration that a PSA key has exactly two algorithms, and also allows the caller to benefit from default for the policy in more cases.

[ACTION] [#8708](https://github.com/Mbed-TLS/mbedtls/issues/8708) Implement `mbedtls_pk_get_psa_attributes` and `mbedtls_pk_import_into_psa` as described below. These functions are available whenever `MBEDTLS_PK_C` and `MBEDTLS_PSA_CRYPTO_CLIENT` are both defined. Deprecate `mbedtls_pk_wrap_as_opaque`.

```
int mbedtls_pk_get_psa_attributes(const mbedtls_pk_context *pk,
                                  psa_key_usage_flags_t usage,
                                  psa_key_attributes_t *attributes);
int mbedtls_pk_import_into_psa(const mbedtls_pk_context *pk,
                               const psa_key_attributes_t *attributes,
                               mbedtls_svc_key_id_t *key_id);
```

* `mbedtls_pk_get_psa_attributes` does not change the id/lifetime fields of the attributes (which indicate a volatile key by default).
    * [OPEN] Or should it reset them to 0? Resetting is more convenient for the case where the pk key is a `MBEDTLS_PK_OPAQUE`. But that's an uncommon use case. It's probably less surprising if this function leaves the lifetime-related alone, since its job is to set the type-related and policy-related attributes.
* `mbedtls_pk_get_psa_attributes` sets the type and size based on what's in the pk context.
    * The key type is a key pair if the context contains a private key and the indicated usage is a private-key usage. The key type is a public key if the context only contains a public key, in which case a private-key usage is an error.
* `mbedtls_pk_get_psa_attributes` sets the usage flags based on the `usage` parameter. It extends the usage to other usage that is possible:
    * `EXPORT` and `COPY` are always set.
    * If `SIGN_{HASH,MESSAGE}` is set then so is `VERIFY_{HASH,MESSAGE}`.
    * If `DECRYPT` is set then so is `ENCRYPT`.
    * It is an error if `usage` has more than one flag set, or has a usage that is incompatible with the key type.
* `mbedtls_pk_get_psa_attributes` sets the algorithm usage policy based on information in the key object and on `usage`.
    * For an RSA key with the `MBEDTLS_RSA_PKCS_V15` padding mode, the algorithm policy is `PSA_ALG_RSA_PKCS1V15_SIGN(PSA_ALG_ANY_HASH)` for a sign/verify usage, and `PSA_ALG_RSA_PKCS1V15_CRYPT` for an encrypt/decrypt usage.
    * For an RSA key with the `MBEDTLS_RSA_PKCS_V21` padding mode, the algorithm policy is `PSA_ALG_RSA_PSS_ANY_SALT(PSA_ALG_ANY_HASH)` for a sign/verify usage, and `PSA_ALG_RSA_OAEP(hash)` for an encrypt/decrypt usage where `hash` is from the RSA key's parameters. (Note that `PSA_ALG_ANY_HASH` is only allowed in signature algorithms.)
    * For an `MBEDTLS_PK_ECKEY` or `MBEDTLS_PK_ECDSA` with a sign/verify usage, the algorithm policy is `PSA_ALG_DETERMINISTIC_ECDSA` if `MBEDTLS_ECDSA_DETERMINISTIC` is enabled and `PSA_ALG_ECDSA` otherwise. In either case, the hash policy is `PSA_ALG_ANY_HASH`.
    * For an `MBEDTLS_PK_ECKEY` or `MBEDTLS_PK_ECDKEY_DH` with the usage `PSA_KEY_USAGE_DERIVE`, the algorithm is `PSA_ALG_ECDH`.
    * For a `MBEDTLS_PK_OPAQUE`, this function reads the attributes of the existing PK key and copies them (without overriding the lifetime and key identifier in `attributes`), then applies a public-key restriction if needed.
        * Public-key restriction: if `usage` is a public-key usage, change the type to the corresponding public-key type, and remove private-key usage flags from the usage flags read from the existing key.
* `mbedtls_pk_import_into_psa` checks that the type field in the attributes is consistent with the content of the `mbedtls_pk_context` object (RSA/ECC, and availability of the private key).
    * The key type can be a public key even if the private key is available.
* `mbedtls_pk_import_into_psa` does not need to check the bit-size in the attributes: `psa_import_key` will do enough checks.
* `mbedtls_pk_import_into_psa` does not check that the policy in the attributes is sensible. That's on the user.

#### API to copy a PSA key to a PK context

Based on the [gap analysis](#using-a-psa-key-as-a-pk-context):

[ACTION] [#8709](https://github.com/Mbed-TLS/mbedtls/issues/8709) Implement `mbedtls_pk_copy_from_psa` as described below.

```
int mbedtls_pk_copy_from_psa(mbedtls_svc_key_id_t key_id,
                             mbedtls_pk_context *pk);
```

* `pk` must be initialized, but not set up.
* It is an error if the key is neither a key pair nor a public key.
* It is an error if the key is not exportable.
* The resulting pk object has a transparent type, not `MBEDTLS_PK_OPAQUE`. That's `MBEDTLS_PK_RSA` for RSA keys (since pk objects don't use `MBEDTLS_PK_RSASSA_PSS` as a type), and `MBEDTLS_PK_ECKEY` for ECC keys (following the example of pkparse).
* Once this function returns, the pk object is completely independent of the PSA key.
* Calling `mbedtls_pk_sign`, `mbedtls_pk_verify`, `mbedtls_pk_encrypt`, `mbedtls_pk_decrypt` on the resulting pk context will perform an algorithm that is compatible with the PSA key's primary algorithm policy (`psa_get_key_algorithm`) if that is a matching operation type (sign/verify, encrypt/decrypt), but with no restriction on the hash (as if the policy had `PSA_ALG_ANY_HASH` instead of a specific hash, and with `PSA_ALG_RSA_PKCS1V15_SIGN_RAW` merged with `PSA_ALG_RSA_PKCS1V15_SIGN(hash_alg)`).
    * For ECDSA, the choice of deterministic vs randomized will be based on the compile-time setting `MBEDTLS_ECDSA_DETERMINISTIC`, like `mbedtls_pk_sign` today.
    * For an RSA key, the output key will allow both encrypt/decrypt and sign/verify regardless of the original key's policy. The original key's policy determines the output key's padding mode.
    * The primary intent of this requirement is to allow an application to switch to PSA for creating the key material (for example to benefit from a PSA accelerator driver, or to start using a secure element), without modifying the code that consumes the key. For RSA keys, the PSA primary algorithm policy is how one conveys the same information as RSA key padding information in the legacy API. Convey this in the documentation.

#### API to create a PK object that wraps a PSA key

Based on the [gap analysis](#using-a-psa-key-as-a-pk-context):

[ACTION] [#8712](https://github.com/Mbed-TLS/mbedtls/issues/8712) Clarify the documentation of `mbedtls_pk_setup_opaque` regarding which algorithms the resulting key will perform with `mbedtls_pk_sign`, `mbedtls_pk_verify`, `mbedtls_pk_encrypt`, `mbedtls_pk_decrypt`.

[ACTION] [#8710](https://github.com/Mbed-TLS/mbedtls/issues/8710) Provide `mbedtls_pk_setup_opaque` whenever `MBEDTLS_PSA_CRYPTO_CLIENT` is enabled, not just when `MBEDTLS_USE_PSA_CRYPTO` is enabled. This is nice-to-have, not critical. Update `use-psa-crypto.md` accordingly.

[OPEN] What about `mbedtls_pk_sign_ext` and  `mbedtls_pk_verify_ext`?

#### API to convert between signature formats

Based on the [gap analysis](#signature-formats):

[ACTION] [#7765](https://github.com/Mbed-TLS/mbedtls/issues/7765) Implement `mbedtls_ecdsa_raw_to_der` and `mbedtls_ecdsa_der_to_raw` as described below.

```
int mbedtls_ecdsa_raw_to_der(size_t bits,
                             const unsigned char *raw, size_t raw_len,
                             unsigned char *der, size_t der_size, size_t *der_len);
int mbedtls_ecdsa_der_to_raw(size_t bits,
                             const unsigned char *der, size_t der_len,
                             unsigned char *raw, size_t raw_size, size_t *raw_len);
```

* These functions convert between the signature format used by `mbedtls_pk_{sign,verify}{,_ext}` and the signature format used by `psa_{sign,verify}_{hash,message}`.
* The input and output buffers can overlap.
* The `bits` parameter is necessary in the DER-to-raw direction because the DER format lacks leading zeros, so something else needs to convey the size of (r,s). The `bits` parameter is redundant in the raw-to-DER direction, but we have it anyway because [it helps catch errors](https://github.com/Mbed-TLS/mbedtls/pull/8681#discussion_r1445980971), and it isn't a burden on the caller because the information is readily available in practice.
* Should these functions rely on the ASN.1 module? We experimented [calling ASN.1 functions](https://github.com/Mbed-TLS/mbedtls/pull/8681), [reimplementing simpler ASN.1 functions](https://github.com/Mbed-TLS/mbedtls/pull/8696), and [providing the functions from the ASN.1 module](https://github.com/Mbed-TLS/mbedtls/pull/8703). Providing the functions from the ASN.1 module [won on a compromise of code size and simplicity](https://github.com/Mbed-TLS/mbedtls/issues/7765#issuecomment-1893670015).
