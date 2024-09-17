This document explains the strategy that was used so far in starting the
migration to PSA Crypto and mentions future perspectives and open questions.

Goals
=====

Several benefits are expected from migrating to PSA Crypto:

G1. Use PSA Crypto drivers when available.
G2. Allow isolation of long-term secrets (for example, private keys).
G3. Allow isolation of short-term secrets (for example, TLS session keys).
G4. Have a clean, unified API for Crypto (retire the legacy API).
G5. Code size: compile out our implementation when a driver is available.

As of Mbed TLS 3.2, most of (G1) and all of (G2) is implemented when
`MBEDTLS_USE_PSA_CRYPTO` is enabled. For (G2) to take effect, the application
needs to be changed to use new APIs. For a more detailed account of what's
implemented, see `docs/use-psa-crypto.md`, where new APIs are about (G2), and
internal changes implement (G1).

As of early 2023, work towards G5 is in progress: Mbed TLS 3.3 and 3.4 saw
some improvements in this area, and more will be coming in future releases.

Generally speaking, the numbering above doesn't mean that each goal requires
the preceding ones to be completed.


Compile-time options
====================

We currently have a few compile-time options that are relevant to the migration:

- `MBEDTLS_PSA_CRYPTO_C` - enabled by default, controls the presence of the PSA
  Crypto APIs.
- `MBEDTLS_USE_PSA_CRYPTO` - disabled by default (enabled in "full" config),
  controls usage of PSA Crypto APIs to perform operations in X.509 and TLS
(G1 above), as well as the availability of some new APIs (G2 above).
- `PSA_CRYPTO_CONFIG` - disabled by default, supports builds with drivers and
  without the corresponding software implementation (G5 above).

The reasons why `MBEDTLS_USE_PSA_CRYPTO` is optional and disabled by default
are:
- it's not fully compatible with `MBEDTLS_ECP_RESTARTABLE`: you can enable
  both, but then you won't get the full effect of RESTARTBLE (see the
documentation of this option in `mbedtls_config.h`);
- to avoid a hard/default dependency of TLS, X.509 and PK on
  `MBEDTLS_PSA_CRYPTO_C`, for backward compatibility reasons:
  - When `MBEDTLS_PSA_CRYPTO_C` is enabled and used, applications need to call
    `psa_crypto_init()` before TLS/X.509 uses PSA functions. (This prevents us
from even enabling the option by default.)
  - `MBEDTLS_PSA_CRYPTO_C` has a hard dependency on `MBEDTLS_ENTROPY_C ||
    MBEDTLS_PSA_CRYPTO_EXTERNAL_RNG` but it's
    currently possible to compile TLS and X.509 without any of the options.
    Also, we can't just auto-enable `MBEDTLS_ENTROPY_C` as it doesn't build
    out of the box on all platforms, and even less
    `MBEDTLS_PSA_CRYPTO_EXTERNAL_RNG` as it requires a user-provided RNG
    function.

The downside of this approach is that until we are able to make
`MBDEDTLS_USE_PSA_CRYPTO` non-optional (always enabled), we have to maintain
two versions of some parts of the code: one using PSA, the other using the
legacy APIs. However, see next section for strategies that can lower that
cost. The rest of this section explains the reasons for the
incompatibilities mentioned above.

At the time of writing (early 2022) it is unclear what could be done about the
backward compatibility issues, and in particular if the cost of implementing
solutions to these problems would be higher or lower than the cost of
maintaining dual code paths until the next major version. (Note: these
solutions would probably also solve other problems at the same time.)

### `MBEDTLS_ECP_RESTARTABLE`

Currently this option controls not only the presence of restartable APIs in
the crypto library, but also their use in the TLS and X.509 layers. Since PSA
Crypto does not support restartable operations, there's a clear conflict: the
TLS and X.509 layers can't both use only PSA APIs and get restartable
behaviour.

Support for restartable (aka interruptible) ECDSA sign/verify operation was
added to PSA in Mbed TLS 3.4, but support for ECDH is not present yet.

It will then require follow-up work to make use of the new PSA APIs in
PK/X.509/TLS in all places where we currently allow restartable operations.

### Backward compatibility issues with making `MBEDTLS_USE_PSA_CRYPTO` always on

1. Existing applications may not be calling `psa_crypto_init()` before using
   TLS, X.509 or PK. We can try to work around that by calling (the relevant
part of) it ourselves under the hood as needed, but that would likely require
splitting init between the parts that can fail and the parts that can't (see
<https://github.com/ARM-software/psa-crypto-api/pull/536> for that).
2. It's currently not possible to enable `MBEDTLS_PSA_CRYPTO_C` in
   configurations that don't have `MBEDTLS_ENTROPY_C`, and we can't just
auto-enable the latter, as it won't build or work out of the box on all
platforms. There are two kinds of things we'd need to do if we want to work
around that:
   1. Make it possible to enable the parts of PSA Crypto that don't require an
      RNG (typically, public key operations, symmetric crypto, some key
management functions (destroy etc)) in configurations that don't have
`ENTROPY_C`. This requires going through the PSA code base to adjust
dependencies. Risk: there may be annoying dependencies, some of which may be
surprising.
   2. For operations that require an RNG, provide an alternative function
      accepting an explicit `f_rng` parameter (see #5238), that would be
available in entropy-less builds. (Then code using those functions still needs
to have one version using it, for entropy-less builds, and one version using
the standard function, for driver support in build with entropy.)

See <https://github.com/Mbed-TLS/mbedtls/issues/5156>.

Taking advantage of the existing abstractions layers - or not
=============================================================

The Crypto library in Mbed TLS currently has 3 abstraction layers that offer
algorithm-agnostic APIs for a class of algorithms:

- MD for messages digests aka hashes (including HMAC)
- Cipher for symmetric ciphers (included AEAD)
- PK for asymmetric (aka public-key) cryptography (excluding key exchange)

Note: key exchange (FFDH, ECDH) is not covered by an abstraction layer.

These abstraction layers typically provide, in addition to the API for crypto
operations, types and numerical identifiers for algorithms (for
example `mbedtls_cipher_mode_t` and its values). The
current strategy is to keep using those identifiers in most of the code, in
particular in existing structures and public APIs, even when
`MBEDTLS_USE_PSA_CRYPTO` is enabled. (This is not an issue for G1, G2, G3
above, and is only potentially relevant for G4.)

The are multiple strategies that can be used regarding the place of those
layers in the migration to PSA.

Silently call to PSA from the abstraction layer
-----------------------------------------------

- Provide a new definition (conditionally on `USE_PSA_CRYPTO`) of wrapper
  functions in the abstraction layer, that calls PSA instead of the legacy
crypto API.
- Upside: changes contained to a single place, no need to change TLS or X.509
  code anywhere.
- Downside: tricky to implement if the PSA implementation is currently done on
  top of that layer (dependency loop).

This strategy is currently (early 2023) used for all operations in the PK
layer; the MD layer uses a variant where it dispatches to PSA if a driver is
available and the driver subsystem has been initialized, regardless of whether
`USE_PSA_CRYPTO` is enabled; see `md-cipher-dispatch.md` in the same directory
for details.

This strategy is not very well suited to the Cipher layer, as the PSA
implementation is currently done on top of that layer.

This strategy will probably be used for some time for the PK layer, while we
figure out what the future of that layer is: parts of it (parse/write, ECDSA
signatures in the format that X.509 & TLS want) are not covered by PSA, so
they will need to keep existing in some way. (Also, the PK layer is a good
place for dispatching to either PSA or `mbedtls_xxx_restartable` while that
part is not covered by PSA yet, if we decide to do that.)

Replace calls for each operation
--------------------------------

- For every operation that's done through this layer in TLS or X.509, just
  replace function call with calls to PSA (conditionally on `USE_PSA_CRYPTO`)
- Upside: conceptually simple, and if the PSA implementation is currently done
  on top of that layer, avoids concerns about dependency loops.
- Upside: opens the door to building TLS/X.509 without that layer, saving some
  code size.
- Downside: TLS/X.509 code has to be done for each operation.

This strategy is currently (early 2023) used for the MD layer and the Cipher
layer in X.509 and TLS. Crypto modules however always call to MD which may
then dispatch to PSA, see `md-cipher-dispatch.md`.

Opt-in use of PSA from the abstraction layer
--------------------------------------------

- Provide a new way to set up a context that causes operations on that context
  to be done via PSA.
- Upside: changes mostly contained in one place, TLS/X.509 code only needs to
  be changed when setting up the context, but not when using it. In
  particular, no changes to/duplication of existing public APIs that expect a
  key to be passed as a context of this layer (eg, `mbedtls_pk_context`).
- Upside: avoids dependency loop when PSA implemented on top of that layer.
- Downside: when the context is typically set up by the application, requires
  changes in application code.

This strategy is not useful when no context is used, for example with the
one-shot function `mbedtls_md()`.

There are two variants of this strategy: one where using the new setup
function also allows for key isolation (the key is only held by PSA,
supporting both G1 and G2 in that area), and one without isolation (the key is
still stored outside of PSA most of the time, supporting only G1).

This strategy, with support for key isolation, is currently (early 2022) used for
private-key operations in the PK layer - see `mbedtls_pk_setup_opaque()`. This
allows use of PSA-held private ECDSA keys in TLS and X.509 with no change to
the TLS/X.509 code, but a contained change in the application.

This strategy, without key isolation, was also previously used (until 3.1
included) in the Cipher layer - see `mbedtls_cipher_setup_psa()`. This allowed
use of PSA for cipher operations in TLS with no change to the application
code, and a contained change in TLS code. (It only supported a subset of
ciphers.)

Note: for private key operations in the PK layer, both the "silent" and the
"opt-in" strategy can apply, and can complement each other, as one provides
support for key isolation, but at the (unavoidable) code of change in
application code, while the other requires no application change to get
support for drivers, but fails to provide isolation support.

Summary
-------

Strategies currently (early 2022) used with each abstraction layer:

- PK (for G1): silently call PSA
- PK (for G2): opt-in use of PSA (new key type)
- Cipher (G1): replace calls at each call site
- MD (G1, X.509 and TLS): replace calls at each call site (depending on
  `USE_PSA_CRYPTO`)
- MD (G5): silently call PSA when a driver is available, see
  `md-cipher-dispatch.md`.


Supporting builds with drivers without the software implementation
==================================================================

This section presents a plan towards G5: save code size by compiling out our
software implementation when a driver is available.

Let's expand a bit on the definition of the goal: in such a configuration
(driver used, software implementation and abstraction layer compiled out),
we want:

a. the library to build in a reasonably-complete configuration,
b. with all tests passing,
c. and no more tests skipped than the same configuration with software
   implementation.

Criterion (c) ensures not only test coverage, but that driver-based builds are
at feature parity with software-based builds.

We can roughly divide the work needed to get there in the following steps:

0. Have a working driver interface for the algorithms we want to replace.
1. Have users of these algorithms call to PSA or an abstraction layer than can
   dispatch to PSA, but not the low-level legacy API, for all operations.
(This is G1, and for PK, X.509 and TLS this is controlled by
`MBEDTLS_USE_PSA_CRYPTO`.) This needs to be done in the library and tests.
2. Have users of these algorithms not depend on the legacy API for information
   management (getting a size for a given algorithm, etc.)
3. Adapt compile-time guards used to query availability of a given algorithm;
   this needs to be done in the library (for crypto operations and data) and
tests.

Note: the first two steps enable use of drivers, but not by themselves removal
of the software implementation.

Note: the fact that step 1 is not achieved for all of libmbedcrypto (see
below) is the reason why criterion (a) has "a reasonably-complete
configuration", to allow working around internal crypto dependencies when
working on other parts such as X.509 and TLS - for example, a configuration
without RSA PKCS#1 v2.1 still allows reasonable use of X.509 and TLS.

Note: this is a conceptual division that will sometimes translate to how the
work is divided into PRs, sometimes not. For example, in situations where it's
not possible to achieve good test coverage at the end of step 1 or step 2, it
is preferable to group with the next step(s) in the same PR until good test
coverage can be reached.

**Status as of end of March 2023 (shortly after 3.4):**

- Step 0 is achieved for most algorithms, with only a few gaps remaining.
- Step 1 is achieved for most of PK, X.509, and TLS when
  `MBEDTLS_USE_PSA_CRYPTO` is enabled with only a few gaps remaining (see
  docs/use-psa-crypto.md).
- Step 1 is achieved for the crypto library regarding hashes: everything uses
  MD (not low-level hash APIs), which then dispatches to PSA if applicable.
- Step 1 is not achieved for all of the crypto library when it come to
  ciphers. For example,`ctr_drbg.c` calls the legacy API `mbedtls_aes`.
- Step 2 is achieved for most of X.509 and TLS (same gaps as step 1) when
  `MBEDTLS_USE_PSA_CRYPTO` is enabled.
- Step 3 is done for hashes and top-level ECC modules (ECDSA, ECDH, ECJPAKE).

**Strategy for step 1:**

Regarding PK, X.509, and TLS, this is mostly achieved with only a few gaps.
(The strategy was outlined in the previous section.)

Regarding libmbedcrypto:
- for hashes and ciphers, see `md-cipher-dispatch.md` in the same directory;
- for ECC, we have no internal uses of the top-level algorithms (ECDSA, ECDH,
  ECJPAKE), however they all depend on `ECP_C` which in turn depends on
`BIGNUM_C`. So, direct calls from TLS, X.509 and PK to ECP and Bignum will
need to be replaced; see <https://github.com/Mbed-TLS/mbedtls/issues/6839> and
linked issues for a summary of intermediate steps and open points.

**Strategy for step 2:**

The most satisfying situation here is when we can just use the PSA Crypto API
for information management as well. However sometimes it may not be
convenient, for example in parts of the code that accept old-style identifiers
(such as `mbedtls_md_type_t`) in their API and can't assume PSA to be
compiled in (such as `rsa.c`).

When using an existing abstraction layer such as MD, it can provide
information management functions. In other cases, information that was in a
low-level module but logically belongs in a higher-level module can be moved
to that module (for example, TLS identifiers of curves and there conversion
to/from PSA or legacy identifiers belongs in TLS, not `ecp.c`).

**Strategy for step 3:**

There are currently two (complementary) ways for crypto-using code to check if a
particular algorithm is supported: using `MBEDTLS_xxx` macros, and using
`PSA_WANT_xxx` macros. For example, PSA-based code that want to use SHA-256
will check for `PSA_WANT_ALG_SHA_256`, while legacy-based code that wants to
use SHA-256 will check for `MBEDTLS_SHA256_C` if using the `mbedtls_sha256`
API, or for `MBEDTLS_MD_C && MBEDTLS_SHA256_C` if using the `mbedtls_md` API.

Code that obeys `MBEDTLS_USE_PSA_CRYPTO` will want to use one of the two
dependencies above depending on whether `MBEDTLS_USE_PSA_CRYPTO` is defined:
if it is, the code want the algorithm available in PSA, otherwise, it wants it
available via the legacy API(s) is it using (MD and/or low-level).

As much as possible, we're trying to create for each algorithm a single new
macro that can be used to express dependencies everywhere (except pure PSA
code that should always use `PSA_WANT`). For example, for hashes this is the
`MBEDTLS_MD_CAN_xxx` family. For ECC algorithms, we have similar
`MBEDTLS_PK_CAN_xxx` macros.

Note that in order to achieve that goal, even for code that obeys
`USE_PSA_CRYPTO`, it is useful to impose that all algorithms that are
available via the legacy APIs are also available via PSA.

Executing step 3 will mostly consist of using the right dependency macros in
the right places (once the previous steps are done).

**Note on testing**

Since supporting driver-only builds is not about adding features, but about
supporting existing features in new types of builds, testing will not involve
adding cases to the test suites, but instead adding new components in `all.sh`
that build and run tests in newly-supported configurations. For example, if
we're making some part of the library work with hashes provided only by
drivers when `MBEDTLS_USE_PSA_CRYPTO` is defined, there should be a place in
`all.sh` that builds and run tests in such a configuration.

There is however a risk, especially in step 3 where we change how dependencies
are expressed (sometimes in bulk), to get things wrong in a way that would
result in more tests being skipped, which is easy to miss. Care must be
taken to ensure this does not happen. The following criteria can be used:

1. The sets of tests skipped in the default config and the full config must be
  the same before and after the PR that implements step 3. This is tested
manually for each PR that changes dependency declarations by using the script
`outcome-analysis.sh` in the present directory.
2. The set of tests skipped in the driver-only build is the same as in an
  equivalent software-based configuration. This is tested automatically by the
CI in the "Results analysis" stage, by running
`tests/scripts/analyze_outcomes.py`. See the
`analyze_driver_vs_reference_xxx` actions in the script and the comments above
their declaration for how to do that locally.


Migrating away from the legacy API
==================================

This section briefly introduces questions and possible plans towards G4,
mainly as they relate to choices in previous stages.

The role of the PK/Cipher/MD APIs in user migration
---------------------------------------------------

We're currently taking advantage of the existing PK layer in order
to reduce the number of places where library code needs to be changed. It's
only natural to consider using the same strategy (with the PK, MD and Cipher
layers) for facilitating migration of application code.

Note: a necessary first step for that would be to make sure PSA is no longer
implemented of top of the concerned layers

### Zero-cost compatibility layer?

The most favourable case is if we can have a zero-cost abstraction (no
runtime, RAM usage or code size penalty), for example just a bunch of
`#define`s, essentially mapping `mbedtls_` APIs to their `psa_` equivalent.

Unfortunately that's unlikely to fully work. For example, the MD layer uses the
same context type for hashes and HMACs, while the PSA API (rightfully) has
distinct operation types. Similarly, the Cipher layer uses the same context
type for unauthenticated and AEAD ciphers, which again the PSA API
distinguishes.

It is unclear how much value, if any, a zero-cost compatibility layer that's
incomplete (for example, for MD covering only hashes, or for Cipher covering
only AEAD) or differs significantly from the existing API (for example,
introducing new context types) would provide to users.

### Low-cost compatibility layers?

Another possibility is to keep most or all of the existing API for the PK, MD
and Cipher layers, implemented on top of PSA, aiming for the lowest possible
cost. For example, `mbedtls_md_context_t` would be defined as a (tagged) union
of `psa_hash_operation_t` and `psa_mac_operation_t`, then `mbedtls_md_setup()`
would initialize the correct part, and the rest of the functions be simple
wrappers around PSA functions. This would vastly reduce the complexity of the
layers compared to the existing (no need to dispatch through function
pointers, just call the corresponding PSA API).

Since this would still represent a non-zero cost, not only in terms of code
size, but also in terms of maintenance (testing, etc.) this would probably
be a temporary solution: for example keep the compatibility layers in 4.0 (and
make them optional), but remove them in 5.0.

Again, this provides the most value to users if we can manage to keep the
existing API unchanged. Their might be conflicts between this goal and that of
reducing the cost, and judgment calls may need to be made.

Note: when it comes to holding public keys in the PK layer, depending on how
the rest of the code is structured, it may be worth holding the key data in
memory controlled by the PK layer as opposed to a PSA key slot, moving it to a
slot only when needed (see current `ecdsa_verify_wrap` when
`MBEDTLS_USE_PSA_CRYPTO` is defined)  For example, when parsing a large
number, N, of X.509 certificates (for example the list of trusted roots), it
might be undesirable to use N PSA key slots for their public keys as long as
the certs are loaded. OTOH, this could also be addressed by merging the "X.509
parsing on-demand" (#2478), and then the public key data would be held as
bytes in the X.509 CRT structure, and only moved to a PK context / PSA slot
when it's actually used.

Note: the PK layer actually consists of two relatively distinct parts: crypto
operations, which will be covered by PSA, and parsing/writing (exporting)
from/to various formats, which is currently not fully covered by the PSA
Crypto API.

### Algorithm identifiers and other identifiers

It should be easy to provide the user with a bunch of `#define`s for algorithm
identifiers, for example `#define MBEDTLS_MD_SHA256 PSA_ALG_SHA_256`; most of
those would be in the MD, Cipher and PK compatibility layers mentioned above,
but there might be some in other modules that may be worth considering, for
example identifiers for elliptic curves.

### Lower layers

Generally speaking, we would retire all of the low-level, non-generic modules,
such as AES, SHA-256, RSA, DHM, ECDH, ECP, bignum, etc, without providing
compatibility APIs for them. People would be encouraged to switch to the PSA
API. (The compatibility implementation of the existing PK, MD, Cipher APIs
would mostly benefit people who already used those generic APis rather than
the low-level, alg-specific ones.)

### APIs in TLS and X.509

Public APIs in TLS and X.509 may be affected by the migration in at least two
ways:

1. APIs that rely on a legacy `mbedtls_` crypto type: for example
   `mbedtls_ssl_conf_own_cert()` to configure a (certificate and the
associated) private key. Currently the private key is passed as a
`mbedtls_pk_context` object, which would probably change to a `psa_key_id_t`.
Since some users would probably still be using the compatibility PK layer, it
would need a way to easily extract the PSA key ID from the PK context.

2. APIs the accept list of identifiers: for example
   `mbedtls_ssl_conf_curves()` taking a list of `mbedtls_ecp_group_id`s. This
could be changed to accept a list of pairs (`psa_ecc_family_t`, size) but we
should probably take this opportunity to move to a identifier independent from
the underlying crypto implementation and use TLS-specific identifiers instead
(based on IANA values or custom enums), as is currently done in the new
`mbedtls_ssl_conf_groups()` API, see #4859).

Testing
-------

An question that needs careful consideration when we come around to removing
the low-level crypto APIs and making PK, MD and Cipher optional compatibility
layers is to be sure to preserve testing quality. A lot of the existing test
cases use the low level crypto APIs; we would need to either keep using that
API for tests, or manually migrate tests to the PSA Crypto API. Perhaps a
combination of both, perhaps evolving gradually over time.
