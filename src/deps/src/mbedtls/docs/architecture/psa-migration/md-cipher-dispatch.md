PSA migration strategy for hashes and ciphers
=============================================

## Introduction

This document discusses a migration strategy for code that is not subject to `MBEDTLS_USE_PSA_CRYPTO`, is currently using legacy cryptography APIs, and should transition to PSA, without a major version change.

### Relationship with the main strategy document

This is complementary to the main [strategy document](strategy.html) and is intended as a refinement. However, at this stage, there may be contradictions between the strategy proposed here and some of the earlier strategy.

A difference between the original strategy and the current one is that in this work, we are not treating PSA as a black box. We can change experimental features, and we can call internal interfaces.

## Requirements

### User stories

#### Backward compatibility user story

As a developer of an application that uses Mbed TLS's interfaces (including legacy crypto),  
I want Mbed TLS to preserve backward compatibility,  
so that my code keeps working in new minor versions of Mbed TLS.

#### Interface design user story

As a developer of library code that uses Mbed TLS to perform cryptographic operations,  
I want to know which functions to call and which feature macros to check,  
so that my code works in all Mbed TLS configurations.

Note: this is the same problem we face in X.509 and TLS.

#### Hardware accelerator vendor user stories

As a vendor of a platform with hardware acceleration for some crypto,  
I want to build Mbed TLS in a way that uses my hardware wherever relevant,  
so that my customers maximally benefit from my hardware.

As a vendor of a platform with hardware acceleration for some crypto,  
I want to build Mbed TLS without software that replicates what my hardware does,  
to minimize the code size.

#### Maintainer user stories

As a maintainer of Mbed TLS,  
I want to have clear rules for when to use which interface,  
to avoid bugs in “unusual” configurations.

As a maintainer of Mbed TLS,  
I want to avoid duplicating code,  
because this is inefficient and error-prone.

### Use PSA more

In the long term, all code using cryptography should use PSA interfaces, to benefit from PSA drivers, allow eliminating legacy interfaces (less code size, less maintenance). However, this can't be done without breaking [backward compatibility](#backward-compatibility).

The goal of this work is to arrange for more non-PSA interfaces to use PSA interfaces under the hood, without breaking code in the cases where this doesn't work. Using PSA interfaces has two benefits:

* Where a PSA driver is available, it likely has better performance, and sometimes better security, than the built-in software implementation.
* In many scenarios, where a PSA driver is available, this allows removing the software implementation altogether.
* We may be able to get rid of some redundancies, for example the duplication between the implementations of HMAC in `md.c` and in `psa_crypto_mac.c`, and HKDF in `hkdf.c` and `psa_crypto.c`.

### Correct dependencies

Traditionally, to determine whether a cryptographic mechanism was available, you had to check whether the corresponding Mbed TLS module or submodule was present: `MBEDTLS_SHA256_C` for SHA256, `MBEDTLS_AES_C && MBEDTLS_CIPHER_MODE_CBC` for AES-CBC, etc. In code that uses the PSA interfaces, this needs to change to `PSA_WANT_xxx` symbols.

### Backward compatibility

All documented behavior must be preserved, except for interfaces currently described as experimental or unstable. Those interfaces can change, but we should minimize disruption by providing a transition path for reasonable use cases.

#### Changeable configuration options

The following configuration options are described as experimental, and are likely to change at least marginally:

* `MBEDTLS_PSA_CRYPTO_CLIENT`: “This interface is experimental and may change or be removed without notice.” In practice we don't want to remove this, but we may constrain how it's used.
* `MBEDTLS_PSA_CRYPTO_DRIVERS`: “This interface is experimental. We intend to maintain backward compatibility with application code that relies on drivers, but the driver interfaces may change without notice.” In practice, this may mean constraints not only on how to write drivers, but also on how to integrate drivers into code that is platform code more than application code.
* `MBEDTLS_PSA_CRYPTO_CONFIG`: “This feature is still experimental and is not ready for production since it is not completed.” We may want to change this, for example, to automatically enable more mechanisms (although this wouldn't be considered a backward compatibility break anyway, since we don't promise that you will not get a feature if you don't enable its `PSA_WANT_xxx`).

### Non-goals

It is not a goal at this stage to make more code directly call `psa_xxx` functions. Rather, the goal is to make more code call PSA drivers where available. How dispatch is done is secondary.

## Problem analysis

### Scope analysis

#### Limitations of `MBEDTLS_USE_PSA_CRYPTO`

The option `MBEDTLS_USE_PSA_CRYPTO` causes parts of the library to call the PSA API instead of legacy APIs for cryptographic calculations. `MBEDTLS_USE_PSA_CRYPTO` only applies to `pk.h`, X.509 and TLS. When this option is enabled, applications must call `psa_crypto_init()` before calling any of the functions in these modules.

In this work, we want two things:

* Make non-covered modules call PSA, but only [when this will actually work](#why-psa-is-not-always-possible). This effectively brings those modules to a partial use-PSA behavior (benefiting from PSA accelerators when they're usable) regardless of whether the option is enabled.
* Call PSA when a covered module calls a non-covered module which calls another module, for example X.509 calling pk for PSS verification which calls RSA which calculates a hash ([see issue \#6497](https://github.com/Mbed-TLS/mbedtls/issues/6497)). This effectively extends the option to modules that aren't directly covered.

#### Classification of callers

We can classify code that implements or uses cryptographic mechanisms into several groups:

* Software implementations of primitive cryptographic mechanisms. These are not expected to change.
* Software implementations of constructed cryptographic mechanisms (e.g. HMAC, CTR_DRBG, RSA (calling a hash for PSS/OAEP, and needing to know the hash length in PKCS1v1.5 sign/verify), …). These need to keep working whenever a legacy implementation of the auxiliary mechanism is available, regardless of whether a PSA implementation is also available.
* Code implementing the PSA crypto interface. This is not expected to change, except perhaps to expose some internal functionality to overhauled glue code.
* Code that's subject to `MBEDTLS_USE_PSA_CRYPTO`: `pk.h`, X.509, TLS (excluding parts specific TLS 1.3).
* Code that always uses PSA for crypto: TLS 1.3 (except things common with 1.2), LMS.

For the purposes of this work, three domains emerge:

* **Legacy domain**: does not interact with PSA. Implementations of hashes, of cipher primitives, of arithmetic.
* **Mixed domain**: does not currently use PSA, but should [when possible](#why-psa-is-not-always-possible). This consists of the constructed cryptographic primitives (except LMS), as well as pk, X.509 and TLS when `MBEDTLS_USE_PSA_CRYPTO` is disabled.
* **PSA domain**: includes pk, X.509 and TLS when `MBEDTLS_USE_PSA_CRYPTO` is enabled. Also TLS 1.3, LMS.

#### Non-use-PSA modules

The following modules in Mbed TLS call another module to perform cryptographic operations which, in the long term, will be provided through a PSA interface, but cannot make any PSA-related assumption.

Hashes and HMAC (after the work on driver-only hashes):

* entropy (hashes via MD-light)
* ECDSA (HMAC\_DRBG; `md.h` exposed through API)
* ECJPAKE (hashes via MD-light; `md.h` exposed through API)
* MD (hashes and HMAC)
* HKDF (HMAC via `md.h`; `md.h` exposed through API)
* HMAC\_DRBG (hashes and HMAC via `md.h`; `md.h` exposed through API)
* PKCS12 (hashes via MD-light)
* PKCS5 (HMAC via `md.h`; `md.h` exposed through API)
* PKCS7 (hashes via MD)
* RSA (hash via MD-light for PSS and OAEP; `md.h` exposed through API)
* PEM (MD5 hash via MD-light)

Symmetric ciphers and AEADs (before work on driver-only cipher):

* PEM:
  * AES, DES or 3DES in CBC mode without padding, decrypt only (!).
  * Currently using low-level non-generic APIs.
  * No hard dependency, features guarded by `AES_C` resp. `DES_C`.
  * Functions called: `setkey_dec()` + `crypt_cbc()`.
* PKCS12:
  * In practice: 2DES or 3DES in CBC mode with PKCS7 padding, decrypt only
    (when called from pkparse).
  * In principle: any cipher-mode (default padding), passed an
    `mbedtls_cipher_type_t` as an argument, no documented restriction.
  * Cipher, generically, selected from ASN.1 or function parameters;
    no documented restriction but in practice TODO (inc. padding and
    en/decrypt, look at standards and tests)
  * Unconditional dependency on `CIPHER_C` in `check_config.h`.
  * Note: `cipher.h` exposed through API.
  * Functions called: `setup`, `setkey`, `set_iv`, `reset`, `update`, `finish` (in sequence, once).
* PKCS5 (PBES2, `mbedtls_pkcs5_pbes2()`):
  * 3DES or DES in CBC mode with PKCS7 padding, both encrypt and decrypt.
  * Note: could also be AES in the future, see #7038.
  * Unconditional dependency on `CIPHER_C` in `check_config.h`.
  * Functions called: `setup`, `setkey`, `crypt`.
* CTR\_DRBG:
  * AES in ECB mode, encrypt only.
  * Currently using low-level non-generic API (`aes.h`).
  * Unconditional dependency on `AES_C` in `check_config.h`.
  * Functions called: `setkey_enc`, `crypt_ecb`.
* CCM:
  * AES, Camellia or Aria in ECB mode, encrypt only.
  * Unconditional dependency on `AES_C || CAMELLIA_C || ARIA_C` in `check_config.h`.
  * Unconditional dependency on `CIPHER_C` in `check_config.h`.
  * Note: also called by `cipher.c` if enabled.
  * Functions called: `info`, `setup`, `setkey`, `update` (several times) - (never finish)
* CMAC:
  * AES or DES in ECB mode, encrypt only.
  * Unconditional dependency on `AES_C || DES_C` in `check_config.h`.
  * Unconditional dependency on `CIPHER_C` in `check_config.h`.
  * Note: also called by `cipher.c` if enabled.
  * Functions called: `info`, `setup`, `setkey`, `update` (several times) - (never finish)
* GCM:
  * AES, Camellia or Aria in ECB mode, encrypt only.
  * Unconditional dependency on `AES_C || CAMELLIA_C || ARIA_C` in `check_config.h`.
  * Unconditional dependency on `CIPHER_C` in `check_config.h`.
  * Note: also called by `cipher.c` if enabled.
  * Functions called: `info`, `setup`, `setkey`, `update` (several times) - (never finish)
* NIST\_KW:
  * AES in ECB mode, both encryt and decrypt.
  * Unconditional dependency on `AES_C || DES_C` in `check_config.h`.
  * Unconditional dependency on `CIPHER_C` in `check_config.h`.
  * Note: also called by `cipher.c` if enabled.
  * Note: `cipher.h` exposed through API.
  * Functions called: `info`, `setup`, `setkey`, `update` (several times) - (never finish)
* Cipher:
  * potentially any cipher/AEAD in any mode and any direction

Note: PSA cipher is built on Cipher, but PSA AEAD directly calls the underlying AEAD modules (GCM, CCM, ChachaPoly).

### Difficulties

#### Why PSA is not always possible

Here are some reasons why calling `psa_xxx()` to perform a hash or cipher calculation might not be desirable in some circumstances, explaining why the application would arrange to call the legacy software implementation instead.

* `MBEDTLS_PSA_CRYPTO_C` is disabled.
* There is a PSA driver which has not been initialized (this happens in `psa_crypto_init()`).
* For ciphers, the keystore is not initialized yet, and Mbed TLS uses a custom implementation of PSA ITS where the file system is not accessible yet (because something else needs to happen first, and the application takes care that it happens before it calls `psa_crypto_init()`). A possible workaround may be to dispatch to the internal functions that are called after the keystore lookup, rather than to the PSA API functions (but this is incompatible with `MBEDTLS_PSA_CRYPTO_CLIENT`).
* The requested mechanism is enabled in the legacy interface but not in the PSA interface. This was not really intended, but is possible, for example, if you enable `MBEDTLS_MD5_C` for PEM decoding with PBKDF1 but don't want `PSA_ALG_WANT_MD5` because it isn't supported for `PSA_ALG_RSA_PSS` and `PSA_ALG_DETERMINISTIC_ECDSA`.
* `MBEDTLS_PSA_CRYPTO_CLIENT` is enabled, and the client has not yet activated the connection to the server (this happens in `psa_crypto_init()`).
* `MBEDTLS_PSA_CRYPTO_CLIENT` is enabled, but the operation is part of the implementation of an encrypted communication with the crypto service, or the local implementation is faster because it avoids a costly remote procedure call.

#### Indirect knowledge

Consider for example the code in `rsa.c` to perform an RSA-PSS signature. It needs to calculate a hash. If `mbedtls_rsa_rsassa_pss_sign()` is called directly by application code, it is supposed to call the built-in implementation: calling a PSA accelerator would be a behavior change, acceptable only if this does not add a risk of failure or performance degradation ([PSA is impossible or undesirable in some circumstances](#why-psa-is-not-always-possible)). Note that this holds regardless of the state of `MBEDTLS_USE_PSA_CRYPTO`, since `rsa.h` is outside the scope of `MBEDTLS_USE_PSA_CRYPTO`. On the other hand, if `mbedtls_rsa_rsassa_pss_sign()` is called from X.509 code, it should use PSA to calculate hashes. It doesn't, currently, which is [bug \#6497](https://github.com/Mbed-TLS/mbedtls/issues/6497).

Generally speaking, modules in the mixed domain:

* must call PSA if called by a module in the PSA domain;
* must not call PSA (or must have a fallback) if their caller is not in the PSA domain and the PSA call is not guaranteed to work.

#### Non-support guarantees: requirements

Generally speaking, just because some feature is not enabled in `mbedtls_config.h` or `psa_config.h` doesn't guarantee that it won't be enabled in the build. We can enable additional features through `build_info.h`.

If `PSA_WANT_xxx` is disabled, this should guarantee that attempting xxx through the PSA API will fail. This is generally guaranteed by the test suite `test_suite_psa_crypto_not_supported` with automatically enumerated test cases, so it would be inconvenient to carve out an exception.

### Technical requirements

Based on the preceding analysis, the core of the problem is: for code in the mixed domain (see [“Classification of callers”](#classification-of-callers)), how do we handle a cryptographic mechanism? This has several related subproblems:

* How the mechanism is encoded (e.g. `mbedtls_md_type_t` vs `const *mbedtls_md_info_t` vs `psa_algorithm_t` for hashes).
* How to decide whether a specific algorithm or key type is supported (eventually based on `MBEDTLS_xxx_C` vs `PSA_WANT_xxx`).
* How to obtain metadata about algorithms (e.g. hash/MAC/tag size, key size).
* How to perform the operation (context type, which functions to call).

We need a way to decide this based on the available information:

* Who's the ultimate caller — see [indirect knowledge](#indirect-knowledge) — which is not actually available.
* Some parameter indicating which algorithm to use.
* The available cryptographic implementations, based on preprocessor symbols (`MBEDTLS_xxx_C`, `PSA_WANT_xxx`, `MBEDTLS_PSA_ACCEL_xxx`, etc.).
* Possibly additional runtime state (for example, we might check whether `psa_crypto_init` has been called).

And we need to take care of the [the cases where PSA is not possible](#why-psa-is-not-always-possible): either make sure the current behavior is preserved, or (where allowed by backward compatibility) document a behavior change and, preferably, a workaround.

### Working through an example: RSA-PSS

Let us work through the example of RSA-PSS which calculates a hash, as in [see issue \#6497](https://github.com/Mbed-TLS/mbedtls/issues/6497).

RSA is in the [mixed domain](#classification-of-callers). So:

* When called from `psa_sign_hash` and other PSA functions, it must call the PSA hash accelerator if there is one.
* When called from user code, it must call the built-in hash implementation if PSA is not available (regardless of whether this is because `MBEDTLS_PSA_CRYPTO_C` is disabled, or because `PSA_WANT_ALG_xxx` is disabled for this hash, or because there is an accelerator driver which has not been initialized yet).

RSA knows which hash algorithm to use based on a parameter of type `mbedtls_md_type_t`. (More generally, all mixed-domain modules that take an algorithm specification as a parameter take it via a numerical type, except HMAC\_DRBG and HKDF which take a `const mbedtls_md_info_t*` instead, and CMAC which takes a `const mbedtls_cipher_info_t *`.)

#### Double encoding solution

A natural solution is to double up the encoding of hashes in `mbedtls_md_type_t`. Pass `MBEDTLS_MD_SHA256` and `md` will dispatch to the legacy code, pass a new constant `MBEDTLS_MD_SHA256_USE_PSA` and `md` will dispatch through PSA.

This maximally preserves backward compatibility, but then no non-PSA code benefits from PSA accelerators, and there's little potential for removing the software implementation.

#### Availability of hashes in RSA-PSS

Here we try to answer the question: As a caller of RSA-PSS via `rsa.h`, how do I know whether it can use a certain hash?

* For a caller in the legacy domain: if e.g. `MBEDTLS_SHA256_C` is enabled, then I want RSA-PSS to support SHA-256. I don't care about negative support. So `MBEDTLS_SHA256_C` must imply support for RSA-PSS-SHA-256. It must work at all times, regardless of the state of PSA (e.g. drivers not initialized).
* For a caller in the PSA domain: if e.g. `PSA_WANT_ALG_SHA_256` is enabled, then I want RSA-PSS to support SHA-256, provided that `psa_crypto_init()` has been called. In some limited cases, such as `test_suite_psa_crypto_not_supported` when PSA implements RSA-PSS in software, we care about negative support: if `PSA_WANT_ALG_SHA_256` is disabled then `psa_verify_hash` must reject `PSA_WANT_ALG_SHA_256`. This can be done at the level of PSA before it calls the RSA module, though, so it doesn't have any implication on the RSA module. As far as `rsa.c` is concerned, what matters is that `PSA_WANT_ALG_SHA_256` implies that SHA-256 is supported after `psa_crypto_init()` has been called.
* For a caller in the mixed domain: requirements depend on the caller. Whatever solution RSA has to determine the availability of algorithms will apply to its caller as well.

Conclusion so far: RSA must be able to do SHA-256 if either `MBEDTLS_SHA256_C` or `PSA_WANT_ALG_SHA_256` is enabled. If only `PSA_WANT_ALG_SHA_256` and not `MBEDTLS_SHA256_C` is enabled (which implies that PSA's SHA-256 comes from an accelerator driver), then SHA-256 only needs to work if `psa_crypto_init()` has been called.

#### More in-depth discussion of compile-time availability determination

The following combinations of compile-time support are possible:

* `MBEDTLS_PSA_CRYPTO_CLIENT`. Then calling PSA may or may not be desirable for performance. There are plausible use cases where only the server has access to an accelerator so it's best to call the server, and plausible use cases where calling the server has overhead that negates the savings from using acceleration, if there are savings at all. In any case, calling PSA only works if the connection to the server has been established, meaning `psa_crypto_init` has been called successfully. In the rest of this case enumeration, assume `MBEDTLS_PSA_CRYPTO_CLIENT` is disabled.
* No PSA accelerator. Then just call `mbedtls_sha256`, it's all there is, and it doesn't matter (from an API perspective) exactly what call chain leads to it.
* PSA accelerator, no software implementation. Then we might as well call the accelerator, unless it's important that the call fails. At the time of writing, I can't think of a case where we would want to guarantee that if `MBEDTLS_xxx_C` is not enabled, but xxx is enabled through PSA, then a request to use algorithm xxx through some legacy interface must fail.
* Both PSA acceleration and the built-in implementation. In this case, we would prefer PSA for the acceleration, but we can only do this if the accelerator driver is working. For hashes, it's enough to assume the driver is initialized; we've [considered requiring hash drivers to work without initialization](https://github.com/Mbed-TLS/mbedtls/pull/6470). For ciphers, this is more complicated because the cipher functions require the keystore, and plausibly a cipher accelerator might want entropy (for side channel countermeasures) which might not be available at boot time.

Note that it's a bit tricky to determine which algorithms are available. In the case where there is a PSA accelerator but no software implementation, we don't want the preprocessor symbols to indicate that the algorithm is available through the legacy domain, only through the PSA domain. What does this mean for the interfaces in the mixed domain? They can't guarantee the availability of the algorithm, but they must try if requested.

### Designing an interface for hashes

In this section, we specify a hash metadata and calculation for the [mixed domain](#classification-of-callers), i.e. code that can be called both from legacy code and from PSA code.

#### Availability of hashes

Generalizing the analysis in [“Availability of hashes in RSA-PSS”](#availability-of-hashes-in-RSA-PSS):

A hash is available through the mixed-domain interface iff either of the following conditions is true:

* A legacy hash interface is available and the hash algorithm is implemented in software.
* PSA crypto is enabled and the hash algorithm is implemented via PSA.

We could go further and make PSA accelerators available to legacy callers that call any legacy hash interface, e.g. `md.h` or `shaX.h`. There is little point in doing this, however: callers should just use the mixed-domain interface.

#### Implications between legacy availability and PSA availability

* When `MBEDTLS_PSA_CRYPTO_CONFIG` is disabled, all legacy mechanisms are automatically enabled through PSA. Users can manually enable PSA mechanisms that are available through accelerators but not through legacy, but this is not officially supported (users are not supposed to manually define PSA configuration symbols when `MBEDTLS_PSA_CRYPTO_CONFIG` is disabled).
* When `MBEDTLS_PSA_CRYPTO_CONFIG` is enabled, there is no mandatory relationship between PSA support and legacy support for a mechanism. Users can configure legacy support and PSA support independently. Legacy support is automatically enabled if PSA support is requested, but only if there is no accelerator.

It is strongly desirable to allow mechanisms available through PSA but not legacy: this allows saving code size when an accelerator is present.

There is no strong reason to allow mechanisms available through legacy but not PSA when `MBEDTLS_PSA_CRYPTO_C` is enabled. This would only save at best a very small amount of code size in the PSA dispatch code. This may be more desirable when `MBEDTLS_PSA_CRYPTO_CLIENT` is enabled (having a mechanism available only locally and not in the crypto service), but we do not have an explicit request for this and it would be entirely reasonable to forbid it.

In this analysis, we have not found a compelling reason to require all legacy mechanisms to also be available through PSA. However, this can simplify both the implementation and the use of dispatch code thanks to some simplifying properties:

* Mixed-domain code can call PSA code if it knows that `psa_crypto_init()` has been called, without having to inspect the specifics of algorithm support.
* Mixed-domain code can assume that PSA buffer calculations work correctly for all algorithms that it supports.

#### Shape of the mixed-domain hash interface

We now need to create an abstraction for mixed-domain hash calculation. (We could not create an abstraction, but that would require every piece of mixed-domain code to replicate the logic here. We went that route in Mbed TLS 3.3, but it made it effectively impossible to get something that works correctly.)

Requirements: given a hash algorithm,

* Obtain some metadata about it (size, block size).
* Calculate the hash.
* Set up a multipart operation to calculate the hash. The operation must support update, finish, reset, abort, clone.

The existing interface in `md.h` is close to what we want, but not perfect. What's wrong with it?

* It has an extra step of converting from `mbedtls_md_type_t` to `const mbedtls_md_info_t *`.
* It includes extra fluff such as names and HMAC. This costs code size.
* The md module has some legacy baggage dating from when it was more open, which we don't care about anymore. This may cost code size.

These problems are easily solvable.

* `mbedtls_md_info_t` can become a very thin type. We can't remove the extra function call from the source code of callers, but we can make it a very thin abstraction that compilers can often optimize.
* We can make names and HMAC optional. The mixed-domain hash interface won't be the full `MBEDTLS_MD_C` but a subset.
* We can optimize `md.c` without making API changes to `md.h`.

### Scope reductions and priorities for 3.x

This section documents things that we chose to temporarily exclude from the scope in the 3.x branch (which will eventually be in scope again after 4.0) as well as things we chose to prioritize if we don't have time to support everything.

#### Don't support PK, X.509 and TLS without `MBEDTLS_USE_PSA_CRYPTO`

We do not need to support driver-only hashes and ciphers in PK. X.509 and TLS without `MBEDTLS_USE_PSA_CRYPTO`. Users who want to take full advantage of drivers will need to enabled this macro.

Note that this applies to TLS 1.3 as well, as some uses of hashes and all uses of ciphers there are common with TLS 1.2, hence governed by `MBEDTLS_USE_PSA_CRYPTO`, see [this macro's extended documentation](../../docs/use-psa-crypto.html).

This will go away naturally in 4.0 when this macros is not longer an option (because it's always on).

#### Don't support for `MBEDTLS_PSA_CRYPTO_CLIENT` without `MBEDTLS_PSA_CRYPTO_C`

We generally don't really support builds with `MBEDTLS_PSA_CRYPTO_CLIENT` without `MBEDTLS_PSA_CRYPTO_C`. For example, both `MBEDTLS_USE_PSA_CRYPTO` and `MBEDTLS_SSL_PROTO_TLS1_3` require `MBEDTLS_PSA_CRYPTO_C`, while in principle they should only require `MBEDTLS_PSA_CRYPTO_CLIENT`.

Considering this existing restriction which we do not plan to lift before 4.0, it is acceptable driver-only hashes and cipher support to have the same restriction in 3.x.

It is however desirable for the design to keep support for `MBEDTLS_PSA_CRYPTO_CLIENT` in mind, in order to avoid making it more difficult to add in the future.

#### For cipher: prioritize constrained devices and modern TLS

The primary target is a configuration like TF-M's medium profile, plus TLS with only AEAD ciphersuites.

This excludes things like:
- Support for encrypted PEM, PKCS5 and PKCS12 encryption, and PKCS8 encrypted keys in PK parse. (Not widely used on highly constrained devices.)
- Support for NIST-KW. (Same justification.)
- Support for CMAC. (Same justification, plus can be directly accelerated.)
- Support for CBC ciphersuites in TLS. (They've been recommended against for a while now.)

### Dual-dispatch for block cipher primitives

Considering the priorities stated above, initially we want to support GCM, CCM and CTR-DRBG. All three of them use the block cipher primitive only in the encrypt direction. Currently, GCM and CCM use the Cipher layer in order to work with AES, Aria and Camellia (DES is excluded by the standards due to its smaller block size) and CTR-DRBG directly uses the low-level API from `aes.h`. In all cases, access to the "block cipher primitive" is done by using "ECB mode" (which for both Cipher and `aes.h` only allows a single block, contrary to PSA which implements actual ECB mode).

The two AEAD modes, GCM and CCM, have very similar needs and positions in the stack, strongly suggesting using the same design for both. On the other hand, there are a number of differences between CTR-DRBG and them.
- CTR-DRBG only uses AES (and there is no plan to extend it to other block ciphers at the moment), while GCM and CCM need to work with 3 block ciphers already.
- CTR-DRBG holds a special position in the stack: most users don't care about it per se, they only care about getting random numbers - in fact PSA users don't even need to know what DRBG is used. In particular, no part of the stack is asking questions like "is CTR-DRBG-AES available?" - an RNG needs to be available and that's it - contrary to similar questions about AES-GCM etc. which are asked for example by TLS.

So, it makes sense to use different designs for CTR-DRBG on one hand, and GCM/CCM on the other hand:
- CTR-DRBG can just check if `AES_C` is present and "fall back" to PSA if not.
- GCM and CCM need an common abstraction layer that allows:
  - Using AES, Aria or Camellia in a uniform way.
  - Dispatching to built-in or driver.

The abstraction layer used by GCM and CCM may either be a new internal module, or a subset of the existing Cipher API, extended with the ability to dispatch to a PSA driver.

Reasons for making this layer's API a subset of the existing Cipher API:
- No need to design, implement and test a new module. (Will need to test the new subset though, as well as the extended behaviour.)
- No code change in GCM and CCM - only need to update dependencies.
- No risk for code duplication between a potential new module and Cipher: source-level, and in in particular in builds that still have `CIPHER_C` enabled. (Compiled-code duplication could be avoided by excluding the new module in such builds, though.)
- If want to support other users of Cipher later (such as NIST-KW, CMAC, PKCS5 and PKCS12), we can just extend dual-dispatch support to other modes/operations in Cipher and keep those extra modules unchanged as well.

Possible costs of re-using (a subset of) the existing Cipher API instead of defining a new one:
- We carry over costs associated with `cipher_info_t` structures. (Currently the info structure is used for 3 things: (1) to check if the cipher is supported, (2) to check its block size, (3) because `setup()` requires it).
- We carry over questionable implementation decisions, like dynamic allocation of context.

Those costs could be avoided by refactoring (parts of) Cipher, but that would probably mean either:
- significant differences in how the `cipher.h` API is implemented between builds with the full Cipher or only a subset;
- or more work to apply the simplifications to all of Cipher.

Prototyping both approaches showed better code size savings and cleaner code with a new internal module (see section "Internal "block cipher" abstraction (Cipher light)" below).

## Specification

### MD light

#### Definition of MD light

MD light is a subset of `md.h` that implements the hash calculation interface described in ”[Designing an interface for hashes](#designing-an-interface-for-hashes)”. It is activated by `MBEDTLS_MD_LIGHT` in `mbedtls_config.h`.

The following things enable MD light automatically in `build_info.h`:

* A [mixed-domain](#classification-of-callers) module that needs to calculate hashes is enabled.
* `MBEDTLS_MD_C` is enabled.

MD light includes the following types:

* `mbedtls_md_type_t`
* `mbedtls_md_info_t`
* `mbedtls_md_context_t`

MD light includes the following functions:

* `mbedtls_md_info_from_type`
* `mbedtls_md_init`
* `mbedtls_md_free`
* `mbedtls_md_setup` — but `hmac` must be 0 if `MBEDTLS_MD_C` is disabled.
* `mbedtls_md_clone`
* `mbedtls_md_get_size`
* `mbedtls_md_get_type`
* `mbedtls_md_starts`
* `mbedtls_md_update`
* `mbedtls_md_finish`
* `mbedtls_md`

Unlike the full MD, MD light does not support null pointers as `mbedtls_md_context_t *`. At least some functions still need to support null pointers as `const mbedtls_md_info_t *` because this arises when you try to use an unsupported algorithm (`mbedtls_md_info_from_type` returns `NULL`).

#### MD algorithm support macros

For each hash algorithm, `md.h` defines a macro `MBEDTLS_MD_CAN_xxx` whenever the corresponding hash is available through MD light. These macros are only defined when `MBEDTLS_MD_LIGHT` is enabled. Per “[Availability of hashes](#availability-of-hashes)”, `MBEDTLS_MD_CAN_xxx` is enabled if:

* the corresponding `MBEDTLS_xxx_C` is defined; or
* one of `MBEDTLS_PSA_CRYPTO_C` or `MBEDTLS_PSA_CRYPTO_CLIENT` is enabled, and the corresponding `PSA_WANT_ALG_xxx` is enabled.

Note that some algorithms have different spellings in legacy and PSA. Since MD is a legacy interface, we'll use the legacy names. Thus, for example:

```
#if defined(MBEDTLS_MD_LIGHT)
#if defined(MBEDTLS_SHA256_C) || \
    (defined(MBEDTLS_PSA_CRYPTO_C) && PSA_WANT_ALG_SHA_256)
#define MBEDTLS_MD_CAN_SHA256
#endif
#endif
```

Note: in the future, we may want to replace `defined(MBEDTLS_PSA_CRYPTO_C)`
with `defined(MBEDTLS_PSA_CRYTO_C) || defined(MBEDTLS_PSA_CRYPTO_CLIENT)` but
for now this is out of scope.

#### MD light internal support macros

* If at least one hash has a PSA driver, define `MBEDTLS_MD_SOME_PSA`.
* If at least one hash has a legacy implementation, defined `MBEDTLS_MD_SOME_LEGACY`.

#### Support for PSA in the MD context

An MD context needs to contain either a legacy module's context (or a pointer to one, as is the case now), or a PSA context (or a pointer to one).

I am inclined to remove the pointer indirection, but this means that an MD context would always be as large as the largest supported hash context. So for the time being, this specification keeps a pointer. For uniformity, PSA will also have a pointer (we may simplify this later).

```
enum {
    MBEDTLS_MD_ENGINE_LEGACY,
    MBEDTLS_MD_ENGINE_PSA,
} mbedtls_md_engine_t; // private type

typedef struct mbedtls_md_context_t {
    mbedtls_md_type_t type;
#if defined(MBEDTLS_MD_SOME_PSA)
    mbedtls_md_engine_t engine;
#endif
    void *md_ctx; // mbedtls_xxx_context or psa_hash_operation
#if defined(MBEDTLS_MD_C)
    void *hmac_ctx;
#endif
} mbedtls_md_context_t;
```

All fields are private.

The `engine` field is almost redundant with knowledge about `type`. However, when an algorithm is available both via a legacy module and a PSA accelerator, we will choose based on the runtime availability of the accelerator when the context is set up. This choice needs to be recorded in the context structure.

#### Inclusion of MD info structures

MD light needs to support hashes that are only enabled through PSA. Therefore the `mbedtls_md_info_t` structures must be included based on `MBEDTLS_MD_CAN_xxx` instead of just the legacy module.

The same criterion applies in `mbedtls_md_info_from_type`.

#### Conversion to PSA encoding

The implementation needs to convert from a legacy type encoding to a PSA encoding.

```
static inline psa_algorithm_t psa_alg_of_md_info(
    const mbedtls_md_info_t *md_info );
```

#### Determination of PSA support at runtime

```
int psa_can_do_hash(psa_algorithm_t hash_alg);
```

The job of this private function is to return 1 if `hash_alg` can be performed through PSA now, and 0 otherwise. It is only defined on algorithms that are enabled via PSA.

As a starting point, return 1 if PSA crypto's driver subsystem has been initialized.

Usage note: for algorithms that are not enabled via PSA, calling `psa_can_do_hash` is generally safe: whether it returns 0 or 1, you can call a PSA hash function on the algorithm and it will return `PSA_ERROR_NOT_SUPPORTED`.

#### Support for PSA dispatch in hash operations

Each function that performs some hash operation or context management needs to know whether to dispatch via PSA or legacy.

If given an established context, use its `engine` field.

If given an algorithm as an `mbedtls_md_type_t type` (possibly being the `type` field of a `const mbedtls_md_info_t *`):

* If there is a PSA accelerator for this hash and `psa_can_do_hash(alg)`, call the corresponding PSA function, and if applicable set the engine to `MBEDTLS_MD_ENGINE_PSA`. (Skip this is `MBEDTLS_MD_SOME_PSA` is not defined.)
* Otherwise dispatch to the legacy module based on the type as currently done. (Skip this is `MBEDTLS_MD_SOME_LEGACY` is not defined.)
* If no dispatch is possible, return `MBEDTLS_ERR_MD_FEATURE_UNAVAILABLE`.

Note that this assumes that an operation that has been started via PSA can be completed. This implies that `mbedtls_psa_crypto_free` must not be called while an operation using PSA is in progress. Document this.

#### Error code conversion

After calling a PSA function, MD light calls `mbedtls_md_error_from_psa` to convert its status code.

### Support all legacy algorithms in PSA

As discussed in [“Implications between legacy availability and PSA availability”](#implications-between-legacy-availability-and-psa-availability), we require the following property:

> If an algorithm has a legacy implementation, it is also available through PSA.

When `MBEDTLS_PSA_CRYPTO_CONFIG` is disabled, this is already the case. When is enabled, we will now make it so as well. Change `include/mbedtls/config_psa.h` accordingly.

### MD light optimizations

This section is not necessary to implement MD light, but will cut down its code size.

#### Split names out of MD light

Remove hash names from `mbedtls_md_info_t`. Use a simple switch-case or a separate list to implement `mbedtls_md_info_from_string` and `mbedtls_md_get_name`.

#### Remove metadata from the info structure

In `mbedtls_md_get_size` and in modules that want a hash's block size, instead of looking up hash metadata in the info structure, call the PSA macros.

#### Optimize type conversions

To allow optimizing conversions between `mbedtls_md_type_t` and `psa_algorithm_t`, renumber the `mbedtls_md_type_t` enum so that the values are the 8 lower bits of the PSA encoding.

With this optimization,
```
static inline psa_algorithm_t psa_alg_of_md_info(
    const mbedtls_md_info_t *md_info )
{
    if( md_info == NULL )
        return( PSA_ALG_NONE );
    return( PSA_ALG_CATEGORY_HASH | md_info->type );
}
```

Work in progress on this conversion is at https://github.com/gilles-peskine-arm/mbedtls/tree/hash-unify-ids-wip-1

#### Unify HMAC with PSA

PSA has its own HMAC implementation. In builds with both `MBEDTLS_MD_C` and `PSA_WANT_ALG_HMAC` not fully provided by drivers, we should have a single implementation. Replace the one in `md.h` by calls to the PSA driver interface. This will also give mixed-domain modules access to HMAC accelerated directly by a PSA driver (eliminating the need to a HMAC interface in software if all supported hashes have an accelerator that includes HMAC support).

### Improving support for `MBEDTLS_PSA_CRYPTO_CLIENT`

So far, MD light only dispatches to PSA if an algorithm is available via `MBEDTLS_PSA_CRYPTO_C`, not if it's available via `MBEDTLS_PSA_CRYPTO_CLIENT`. This is acceptable because `MBEDTLS_USE_PSA_CRYPTO` requires `MBEDTLS_PSA_CRYPTO_C`, hence mixed-domain code never invokes PSA.

The architecture can be extended to support `MBEDTLS_PSA_CRYPTO_CLIENT` with a little extra work. Here is an overview of the task breakdown, which should be fleshed up after we've done the first [migration](#migration-to-md-light):

* Compile-time dependencies: instead of checking `defined(MBEDTLS_PSA_CRYPTO_C)`, check `defined(MBEDTLS_PSA_CRYPTO_C) || defined(MBEDTLS_PSA_CRYPTO_CLIENT)`.
* Implementers of `MBEDTLS_PSA_CRYPTO_CLIENT` will need to provide `psa_can_do_hash()` (or a more general function `psa_can_do`) alongside `psa_crypto_init()`. Note that at this point, it will become a public interface, hence we won't be able to change it at a whim.

### Internal "block cipher" abstraction (previously known as "Cipher light")

#### Definition

The new module is automatically enabled in `config_adjust_legacy_crypto.h` by modules that need
it (namely: CCM, GCM) only when `CIPHER_C` is not available, or the new module
is needed for PSA dispatch (see next section). Note: CCM and GCM currently
depend on the full `CIPHER_C` (enforced by `check_config.h`); this hard
dependency would be replaced by the above auto-enablement.

The following API functions are offered:
```
void mbedtls_block_cipher_init(mbedtls_block_cipher_context_t *ctx);
void mbedtls_block_cipher_free(mbedtls_block_cipher_context_t *ctx);
int mbedtls_block_cipher_setup(mbedtls_block_cipher_context_t *ctx,
                               mbedtls_cipher_id_t cipher_id);
int mbedtls_block_cipher_setkey(mbedtls_block_cipher_context_t *ctx,
                                const unsigned char *key,
                                unsigned key_bitlen);
int mbedtls_block_cipher_encrypt(mbedtls_block_cipher_context_t *ctx,
                                 const unsigned char input[16],
                                 unsigned char output[16]);
```

The only supported ciphers are AES, ARIA and Camellia. They are identified by
an `mbedtls_cipher_id_t` in the `setup()` function, because that's how they're
identifed by callers (GCM/CCM).

#### Block cipher dual dispatch

Support for dual dispatch in the new internal module `block_cipher` is extremely similar to that in MD light.

A block cipher context contains either a legacy module's context (AES, ARIA, Camellia) or a PSA key identifier; it has a field indicating which one is in use. All fields are private.

The `engine` field is almost redundant with knowledge about `type`. However, when an algorithm is available both via a legacy module and a PSA accelerator, we will choose based on the runtime availability of the accelerator when the context is set up. This choice needs to be recorded in the context structure.

Support is determined at runtime using the new internal function
```
int psa_can_do_cipher(psa_key_type_t key_type, psa_algorithm_t cipher_alg);
```

The job of this private function is to return 1 if `hash_alg` can be performed through PSA now, and 0 otherwise. It is only defined on algorithms that are enabled via PSA. As a starting point, return 1 if PSA crypto's driver subsystem has been initialized.

Each function in the module needs to know whether to dispatch via PSA or legacy. All functions consult the context's `engine` field, except `setup()` which will set it according to the key type and the return value of `psa_can_do_cipher()` as discussed above.

Note that this assumes that an operation that has been started via PSA can be completed. This implies that `mbedtls_psa_crypto_free` must not be called while an operation using PSA is in progress.

After calling a PSA function, `block_cipher` functions call `mbedtls_cipher_error_from_psa` to convert its status code.
